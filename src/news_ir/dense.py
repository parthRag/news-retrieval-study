"""Resumable E5 encoding and exact cosine search, tied to the BM25 corpus policy."""

import json
import logging
import math
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .data import DocumentStore, decode_document, sha256_file, valid_id
from .embedding import E5Encoder, validate_vectors
from .retrieval import SearchHit
from .vector_worker import VectorWorker, build_faiss


LOGGER = logging.getLogger(__name__)


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def read_shards(root, config, *, verify=True):
    count, offset = 0, 0
    shards = []
    for folder in sorted((Path(root) / "shards").glob("shard-*")):
        if folder.name != f"shard-{len(shards):06d}":
            raise ValueError("Encoding shards are missing or out of sequence")
        info = json.loads((folder / "manifest.json").read_text())
        if info["start_offset"] != offset or info["start_row"] != count or info["count"] <= 0:
            raise ValueError("Shard offsets/row counts are inconsistent")
        if verify:
            for name in ("vectors.npy", "ids.jsonl"):
                if sha256_file(folder / name) != info["sha256"][name]:
                    raise ValueError(f"Corrupt encoding shard: {folder.name}/{name}")
            matrix = np.load(folder / "vectors.npy", allow_pickle=False)
            validate_vectors(matrix, dimension=config["model"]["dimension"], rows=info["count"])
            ids = [json.loads(line) for line in (folder / "ids.jsonl").read_text().splitlines()]
            if len(ids) != info["count"] or len(set(ids)) != len(ids) or not all(valid_id(x) for x in ids):
                raise ValueError("Invalid shard document IDs")
        count += info["count"]
        offset = info["end_offset"]
        shards.append((folder, info))
    if count > config["target_documents"]:
        raise ValueError("Encoded more than the configured document count")
    return shards, count, offset


def encode_corpus(document_index, model_dir, output, *, corpus=None, batch_size=8,
                  shard_size=1024, limit=None, resume=False, device="auto", encoder=None,
                  time_budget_seconds=None):
    for value, name in ((batch_size, "batch_size"), (shard_size, "shard_size")):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be a positive integer")
    if time_budget_seconds is not None and (isinstance(time_budget_seconds, bool)
            or not isinstance(time_budget_seconds, (int, float))
            or not math.isfinite(time_budget_seconds) or time_budget_seconds <= 0):
        raise ValueError("time_budget_seconds must be finite and positive")
    root = Path(output).resolve()
    if root.exists() and not resume:
        raise FileExistsError("Encoding directory exists; use --resume or a new output")
    if resume and not (root / "config.json").is_file():
        raise ValueError("No resumable encoding config found")
    with DocumentStore(document_index, corpus=corpus) as store:
        initial_stat = store.corpus.stat()
        encoder = encoder or E5Encoder(model_dir, device=device)
        eligible = store.manifest["documents"]["indexed"]
        target = min(limit, eligible) if limit is not None else eligible
        config = {
            "schema_version": 1, "engine": "e5-cosine",
            "source_sha256": store.manifest["source"]["sha256"],
            "source_bytes": store.manifest["source"]["bytes"],
            "eligible_documents": eligible, "target_documents": target,
            "coverage": "full" if target == eligible else "pilot",
            "selection": "First eligible documents in source file order; exclude whitespace-empty title and body",
            "contents": store.manifest["contents"], "model": encoder.spec,
            "precision": "float32", "shard_size": shard_size,
        }
        if resume:
            if json.loads((root / "config.json").read_text()) != config:
                raise ValueError("Resume settings, model or corpus differ from the original job")
        else:
            root.mkdir(parents=True, exist_ok=False)
            (root / "shards").mkdir()
            write_json(root / "config.json", config)
        shards, count, offset = read_shards(root, config)
        initial_count, started = count, time.perf_counter()
        with store.corpus.open("rb") as stream:
            stream.seek(offset)
            while count < target:
                start_offset = stream.tell()
                docs = []
                while len(docs) < min(shard_size, target - count):
                    position = stream.tell()
                    raw = stream.readline()
                    if not raw:
                        raise ValueError("Source ended before the expected eligible document count")
                    doc = decode_document(raw, f"offset {position}")
                    if doc.eligible:
                        docs.append(doc)
                matrices = []
                encode_started = time.perf_counter()
                for start in range(0, len(docs), batch_size):
                    texts = [doc.contents for doc in docs[start:start + batch_size]]
                    vectors = encoder.encode(texts, kind="passage")
                    matrices.append(validate_vectors(vectors, dimension=encoder.dimension, rows=len(texts)))
                encoder.synchronize()
                matrix = np.concatenate(matrices)
                pending = Path(tempfile.mkdtemp(prefix=".writing-", dir=root / "shards"))
                try:
                    np.save(pending / "vectors.npy", matrix, allow_pickle=False)
                    (pending / "ids.jsonl").write_text(
                        "".join(json.dumps(doc.doc_id, ensure_ascii=False) + "\n" for doc in docs), encoding="utf-8")
                    info = {"start_row": count, "count": len(docs), "start_offset": start_offset,
                            "end_offset": stream.tell(), "runtime": encoder.runtime,
                            "batch_size": batch_size,
                            "encoding_seconds": time.perf_counter() - encode_started,
                            "sha256": {name: sha256_file(pending / name) for name in ("vectors.npy", "ids.jsonl")}}
                    write_json(pending / "manifest.json", info)
                    pending.rename(root / "shards" / f"shard-{len(shards):06d}")
                except BaseException:
                    shutil.rmtree(pending)
                    raise
                count += len(docs)
                shards.append((None, info))
                source_stat = store.corpus.stat()
                if (source_stat.st_size, source_stat.st_mtime_ns) != (initial_stat.st_size, initial_stat.st_mtime_ns):
                    raise ValueError("Source changed during encoding")
                write_json(root / "progress.json", {"encoded_documents": count, "target_documents": target,
                                                     "completed": count == target, "coverage": config["coverage"]})
                LOGGER.info("Encoded %s / %s documents (%s)", count, target, config["coverage"])
                # Stop only after a complete shard; the full-corpus selection stays unchanged.
                if time_budget_seconds is not None and time.perf_counter() - started >= time_budget_seconds:
                    break
        result = {"completed": count == target, "coverage": config["coverage"], "encoded_documents": count,
                  "target_documents": target,
                  "documents_this_session": count - initial_count,
                  "session_seconds": time.perf_counter() - started,
                  "encoding_seconds": sum(info["encoding_seconds"] for _, info in shards),
                  "runtime": encoder.runtime}
        write_json(root / "progress.json", result)
        return result


def build_dense_index(encodings, output, *, document_index, model_dir, corpus=None, allow_partial=False):
    root, target = Path(encodings).resolve(), Path(output).resolve()
    if target.exists():
        raise FileExistsError("Refusing to overwrite an existing dense index")
    config = json.loads((root / "config.json").read_text())
    if config["coverage"] != "full" and not allow_partial:
        raise ValueError("Pilot encodings require explicit --allow-partial")
    shards, count, _ = read_shards(root, config)
    if count != config["target_documents"] or not count:
        raise ValueError("Encoding is incomplete; resume it before indexing")
    with DocumentStore(document_index, corpus=corpus) as store:
        if store.manifest["source"]["sha256"] != config["source_sha256"]:
            raise ValueError("Document store belongs to a different corpus")
        expected_ids = [row[0] for row in store._db.execute(
            "SELECT doc_id FROM documents WHERE eligible = 1 ORDER BY rowid LIMIT ?", (count,))]
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=f".{target.name}.building-", dir=target.parent))
    try:
        seen = set()
        with (pending / "ids.jsonl").open("w", encoding="utf-8") as output_ids:
            for folder, info in shards:
                ids = [json.loads(line) for line in (folder / "ids.jsonl").read_text().splitlines()]
                if seen.intersection(ids):
                    raise ValueError("Duplicate IDs across encoding shards")
                if ids != expected_ids[len(seen):len(seen) + len(ids)]:
                    raise ValueError("Encoding IDs do not match the shared eligible source documents")
                seen.update(ids)
                output_ids.writelines(json.dumps(doc_id, ensure_ascii=False) + "\n" for doc_id in ids)
        backend = build_faiss(root, pending / "vectors.faiss")
        if backend["count"] != count:
            raise ValueError("FAISS vector count disagrees with source shards")
        manifest = {**config, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "indexed_documents": count, "faiss_type": "IndexFlatIP", "metric": "cosine via normalized inner product",
                    "document_index_path": str(Path(document_index).resolve()),
                    "model_path": str(Path(model_dir).resolve()),
                    "faiss_version": backend["faiss_version"],
                    "vector_backend": "isolated persistent FAISS process; four search threads",
                    "files": {name: sha256_file(pending / name) for name in ("vectors.faiss", "ids.jsonl")}}
        write_json(pending / "manifest.json", manifest)
        pending.rename(target)
        return manifest
    except BaseException:
        shutil.rmtree(pending)
        raise


class DenseEngine:
    def __init__(self, index_dir, *, document_index=None, model_dir=None, corpus=None,
                 device="auto", allow_partial=False, encoder=None):
        self.root = Path(index_dir).resolve()
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        manifest = self.manifest
        if manifest.get("schema_version") != 1 or manifest.get("engine") != "e5-cosine":
            raise ValueError("Unsupported dense index manifest")
        if manifest["coverage"] != "full" and not allow_partial:
            raise ValueError("This is a pilot index; explicitly allow partial coverage to search it")
        for name, digest in manifest["files"].items():
            if Path(name).name != name or sha256_file(self.root / name) != digest:
                raise ValueError(f"Dense index identity check failed: {name}")
        self.ids = [json.loads(line) for line in (self.root / "ids.jsonl").read_text().splitlines()]
        if len(set(self.ids)) != len(self.ids) or not all(valid_id(x) for x in self.ids):
            raise ValueError("Invalid dense document IDs")
        self._worker, self.store, self._closed = None, None, False
        try:
            self._worker = VectorWorker(self.root)
            self._num_docs = self._worker.info["count"]
            if self._num_docs != manifest["indexed_documents"] or self._num_docs != len(self.ids):
                raise ValueError("Dense vector/ID counts disagree")
            if self._worker.info["dimension"] != manifest["model"]["dimension"]:
                raise ValueError("Invalid dense index dimension")
            self.store = DocumentStore(document_index or manifest["document_index_path"], corpus=corpus)
            if self.store.manifest["source"]["sha256"] != manifest["source_sha256"]:
                raise ValueError("Dense and document indexes refer to different corpora")
            self.encoder = encoder or E5Encoder(model_dir or manifest["model_path"], device=device)
            if self.encoder.spec != manifest["model"]:
                raise ValueError("Query encoder differs from the document encoder")
        except BaseException:
            self.close()
            raise

    @property
    def num_docs(self):
        return self._num_docs

    def search(self, query, top_k=10):
        if self._closed:
            raise ValueError("Dense engine is closed")
        if not isinstance(query, str):
            raise TypeError("Query must be a string")
        if type(top_k) is not int or not 1 <= top_k <= 10000:
            raise ValueError("top_k must be an integer between 1 and 10000")
        if not query.strip():
            return []
        vector = validate_vectors(self.encoder.encode([query], kind="query"), dimension=self.manifest["model"]["dimension"], rows=1)
        candidates = self._worker.search(vector[0], top_k)
        return [SearchHit(doc_id, rank, score) for rank, (score, doc_id) in enumerate(candidates, 1)]

    def get_document(self, doc_id):
        return self.store.get(doc_id)

    def close(self):
        if not self._closed:
            try:
                if self._worker is not None:
                    self._worker.close()
            finally:
                if self.store is not None:
                    self.store.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
