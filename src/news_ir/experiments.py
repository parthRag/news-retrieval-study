"""Versioned batch runs and independent consistency checks for an index."""

import json
import math
import platform
import random
import re
import shutil
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .data import read_queries, sha256_file
from .retrieval import BM25Engine


def run_queries(index_dir, queries_path, output, *, top_k=1000, run_tag=None, corpus=None,
                engine_type="bm25", document_index=None, model_dir=None, device="auto", allow_partial=False):
    if type(top_k) is not int or not 1 <= top_k <= 10000:
        raise ValueError("top_k must be an integer between 1 and 10000")
    if run_tag is None:
        run_tag = engine_type
    if not isinstance(run_tag, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", run_tag):
        raise ValueError("run_tag must contain only letters, numbers, dot, underscore or hyphen")
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing run: {target}")
    queries = read_queries(queries_path)
    if engine_type not in {"bm25", "dense"}:
        raise ValueError("engine_type must be bm25 or dense")
    query_hash = sha256_file(queries_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.running-", dir=target.parent))
    try:
        latencies, total_hits, empty = [], 0, []
        if engine_type == "bm25":
            context = BM25Engine(index_dir, corpus=corpus)
        else:
            from .dense import DenseEngine
            context = DenseEngine(index_dir, document_index=document_index, model_dir=model_dir,
                                   corpus=corpus, device=device, allow_partial=allow_partial)
        with context as engine:
            with (working / "run.trec").open("w") as trec, (working / "results.jsonl").open("w", encoding="utf-8") as results:
                for query in queries:
                    started = time.perf_counter()
                    hits = engine.search(query["text"], top_k)
                    latency = (time.perf_counter() - started) * 1000
                    latencies.append(latency)
                    if not hits:
                        empty.append(query["_id"])
                    previous, seen = math.inf, set()
                    for hit in hits:
                        if hit.doc_id in seen or not math.isfinite(hit.score) or hit.score > previous:
                            raise ValueError("Invalid result ordering, duplicate ID or non-finite score")
                        seen.add(hit.doc_id)
                        previous = hit.score
                        trec.write(f"{query['_id']} Q0 {hit.doc_id} {hit.rank} {hit.score:.9g} {run_tag}\n")
                    total_hits += len(hits)
                    results.write(json.dumps({
                        "query_id": query["_id"], "query": query["text"],
                        "analyzed_terms": engine.analyze(query["text"]) if engine_type == "bm25" else None,
                        "latency_ms": latency, "hits": [hit.to_dict() for hit in hits],
                    }, ensure_ascii=False) + "\n")
            if sha256_file(queries_path) != query_hash:
                raise ValueError("Queries changed while the run was executing")
            (working / "queries.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in queries), encoding="utf-8",
            )
            summary = {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "engine": "lucene-bm25" if engine_type == "bm25" else "e5-cosine", "run_tag": run_tag,
                "index_path": str(engine.store.root if engine_type == "bm25" else engine.root),
                "index_manifest_sha256": sha256_file((engine.store.root if engine_type == "bm25" else engine.root) / "manifest.json"),
                "corpus_sha256": engine.store.manifest["source"]["sha256"],
                "query_source_sha256": query_hash,
                "query_snapshot_sha256": sha256_file(working / "queries.jsonl"),
                "query_count": len(queries), "top_k": top_k, "total_hits": total_hits,
                "empty_query_ids": empty,
                "coverage": "full" if engine_type == "bm25" else engine.manifest["coverage"],
                "retrieval_config": ({"k1": engine.k1, "b": engine.b} if engine_type == "bm25" else
                                     {"model": engine.encoder.spec, "runtime": engine.encoder.runtime}),
                "latency_ms": {"mean": statistics.mean(latencies), "median": statistics.median(latencies),
                               "min": min(latencies), "max": max(latencies)},
                "latency_protocol": ("Sequential search including query analysis; first query is cold; excludes JVM startup and article lookup"
                                     if engine_type == "bm25" else
                                     "Sequential query encoding and FAISS IPC/search; excludes model/index startup and article lookup"),
                "runtime_python": platform.python_version(),
                "run_sha256": sha256_file(working / "run.trec"),
                "results_sha256": sha256_file(working / "results.jsonl"),
                "evaluation": "No relevance metrics computed; this command exports retrieval runs only",
            }
            if engine_type == "bm25":
                summary["bm25"] = {"k1": engine.k1, "b": engine.b}
                summary["analyzer"] = engine.store.manifest["analyzer"]
        (working / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
        if target.exists():
            raise FileExistsError(f"Run appeared while executing: {target}")
        working.rename(target)
        return summary
    except BaseException:
        shutil.rmtree(working)
        raise


def verify_index(index_dir, *, corpus=None, sample_size=1000):
    if type(sample_size) is not int or sample_size < 1:
        raise ValueError("sample_size must be a positive integer")
    with BM25Engine(index_dir, corpus=corpus) as engine:
        store = engine.store
        expected = store.manifest["documents"]
        total, indexed = store.counts()
        if (total, indexed) != (expected["total"], expected["indexed"]):
            raise ValueError("Offset store counts differ from manifest")
        integrity = store._db.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"SQLite integrity check failed: {integrity}")
        actual_hash = sha256_file(store.corpus)
        if actual_hash != store.manifest["source"]["sha256"]:
            raise ValueError("Corpus SHA-256 differs from indexed source")
        # Rowids are contiguous because insertion is append-only and duplicates fail the build.
        rowids = random.Random(42).sample(range(1, total + 1), min(total, sample_size))
        for rowid in rowids:
            doc_id = store._db.execute("SELECT doc_id FROM documents WHERE rowid = ?", (rowid,)).fetchone()[0]
            if store.get(doc_id) is None:
                raise ValueError(f"Sample document lookup failed: {doc_id}")
        tokens = engine.analyze("NOT without running 2016 cricket")
        if tokens != ["not", "without", "running", "2016", "cricket"]:
            raise ValueError(f"Analyzer does not match frozen settings: {tokens}")
        return {"status": "passed", "corpus_sha256": actual_hash,
                "total_records": total, "indexed_documents": indexed,
                "excluded_empty": total - indexed, "lookup_samples": len(rowids),
                "sqlite_integrity": integrity, "analyzer_probe": tokens}
