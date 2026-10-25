"""Stream the source directly to Lucene and SQLite; publish only complete builds."""

import hashlib
import importlib.metadata
import json
import logging
import platform
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .data import decode_document
from .runtime import configure_java, initialize_jvm

LOGGER = logging.getLogger(__name__)
ANALYZER = {"language": "en", "stemming": False, "stopwords_removed": False}


def build_index(corpus, output, *, threads=4, batch_size=256):
    if type(threads) is not int or threads < 1 or type(batch_size) is not int or batch_size < 1:
        raise ValueError("threads and batch_size must be positive integers")
    source, target = Path(corpus).resolve(), Path(output).resolve()
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing index: {target}")
    before = source.stat()
    initialize_jvm()
    from pyserini.index.lucene import LuceneIndexer
    from pyserini.pyclass import autoclass

    SimpleSearcher = autoclass('io.anserini.search.SimpleSearcher')

    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.building-", dir=target.parent))
    started = time.perf_counter()
    db = indexer = None
    try:
        db = sqlite3.connect(working / "documents.sqlite3")
        db.execute("CREATE TABLE documents (doc_id TEXT PRIMARY KEY, byte_offset INTEGER NOT NULL, line_bytes INTEGER NOT NULL, eligible INTEGER NOT NULL CHECK(eligible IN (0,1)))")
        indexer = LuceneIndexer(args=[
            "-index", str(working / "lucene"), "-stemmer", "none", "-keepStopwords",
        ], threads=threads)
        digest = hashlib.sha256()
        total = eligible = empty_body = title_only = offset = 0
        batch = []
        with source.open("rb") as stream:
            for number, raw in enumerate(stream, 1):
                digest.update(raw)
                doc = decode_document(raw, f"{source}:{number}")
                try:
                    db.execute("INSERT INTO documents VALUES (?, ?, ?, ?)",
                               (doc.doc_id, offset, len(raw), int(doc.eligible)))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f"{source}:{number}: duplicate document ID {doc.doc_id}") from exc
                offset += len(raw)
                total += 1
                empty_body += not doc.text.strip()
                title_only += bool(doc.title.strip()) and not doc.text.strip()
                if doc.eligible:
                    batch.append({"id": doc.doc_id, "contents": doc.contents})
                    eligible += 1
                if len(batch) >= batch_size:
                    indexer.add_batch_dict(batch)
                    batch.clear()
                if total % 25000 == 0:
                    db.commit()
                    LOGGER.info("Read %s documents; indexed %s", f"{total:,}", f"{eligible:,}")
        if not total or not eligible:
            raise ValueError("Corpus has no nonempty documents")
        if batch:
            indexer.add_batch_dict(batch)
        indexer.close()
        indexer = None
        db.commit()
        db.close()
        db = None
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Corpus changed while indexing; build rejected")
        searcher = SimpleSearcher(str(working / "lucene"))
        try:
            actual = searcher.get_total_num_docs()
        finally:
            searcher.close()
        if actual != eligible:
            raise ValueError(f"Lucene indexed {actual} documents; expected {eligible}")
        manifest = {
            "schema_version": 1, "engine": "lucene-bm25",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": {"path": str(source), "bytes": before.st_size,
                       "mtime_ns": before.st_mtime_ns, "sha256": digest.hexdigest()},
            "documents": {"total": total, "indexed": eligible, "excluded_empty": total - eligible,
                          "empty_body": empty_body, "title_only": title_only},
            "analyzer": ANALYZER,
            "contents": "(title + newline + full body).strip(); no field boosts",
            "empty_policy": "Exclude only whitespace-empty title AND body; preserve all IDs in offset store",
            "bm25": {"k1": 0.9, "b": 0.4},
            "query_semantics": "Natural-language bag of analyzed terms; no logical NOT/date filters",
            "score_export": "Anserini rounds scores to 1e-4 and perturbs ties; external-ID tie breaking",
            "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                        "java": configure_java(), "pyserini": importlib.metadata.version("pyserini")},
            "build": {"threads": threads, "batch_size": batch_size,
                      "elapsed_seconds": round(time.perf_counter() - started, 3)},
        }
        manifest["build"]["index_bytes"] = sum(p.stat().st_size for p in working.rglob("*") if p.is_file())
        (working / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # rename() refuses a nonempty existing target; never replace a previous build.
        if target.exists():
            raise FileExistsError(f"Index appeared during build: {target}")
        working.rename(target)
        return manifest
    except BaseException:
        if indexer is not None:
            try:
                indexer.close()
            except Exception:
                LOGGER.exception("Could not close failed indexer")
        if db is not None:
            db.close()
        shutil.rmtree(working)
        raise
