"""Strict source records and random access through a compact byte-offset store."""

import hashlib
import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path


def valid_id(value):
    return isinstance(value, str) and bool(value) and not any(c.isspace() for c in value)


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    text: str

    @property
    def contents(self):
        return (self.title + "\n" + self.text).strip()

    @property
    def eligible(self):
        return bool(self.contents)

    def to_dict(self):
        return asdict(self)


def decode_document(raw, location="record"):
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"{location}: invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"{location}: expected a JSON object")
    if not valid_id(obj.get("_id")):
        raise ValueError(f"{location}: _id must be a nonempty string without whitespace")
    for field in ("title", "text"):
        if not isinstance(obj.get(field), str):
            raise ValueError(f"{location}: {field} must be a string")
    return Document(obj["_id"], obj["title"], obj["text"])


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_queries(path):
    queries, seen = [], set()
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: invalid query JSON") from exc
            if not isinstance(row, dict) or not valid_id(row.get("_id")):
                raise ValueError(f"{path}:{number}: invalid query _id")
            if not isinstance(row.get("text"), str):
                raise ValueError(f"{path}:{number}: query text must be a string")
            if row["_id"] in seen:
                raise ValueError(f"{path}:{number}: duplicate query ID {row['_id']}")
            seen.add(row["_id"])
            queries.append({"_id": row["_id"], "text": row["text"]})
    if not queries:
        raise ValueError("Query file is empty")
    return queries


class DocumentStore:
    def __init__(self, index_dir, corpus=None):
        self.root = Path(index_dir).resolve()
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        source = self.manifest["source"]
        self.corpus = Path(corpus or source["path"]).resolve()
        stat = self.corpus.stat()
        if stat.st_size != source["bytes"]:
            raise ValueError("Corpus size differs from indexed source; rebuild the index")
        if self.corpus == Path(source["path"]) and stat.st_mtime_ns != source["mtime_ns"]:
            raise ValueError("Corpus modification time changed; rebuild or verify a relocated copy")
        if self.corpus != Path(source["path"]) and sha256_file(self.corpus) != source["sha256"]:
            raise ValueError("Relocated corpus hash differs from indexed source")
        self._db = sqlite3.connect(
            (self.root / "documents.sqlite3").as_uri() + "?mode=ro", uri=True,
            check_same_thread=False,
        )
        self._fd = os.open(self.corpus, os.O_RDONLY)
        self._lock = threading.RLock()
        self._closed = False

    def get(self, doc_id):
        with self._lock:
            if self._closed:
                raise ValueError("Document store is closed")
            row = self._db.execute(
                "SELECT byte_offset, line_bytes FROM documents WHERE doc_id = ?", (doc_id,),
            ).fetchone()
            if row is None:
                return None
            raw = os.pread(self._fd, row[1], row[0])
        doc = decode_document(raw, f"offset {row[0]}")
        if doc.doc_id != doc_id:
            raise ValueError("Corpus/document offsets disagree; source may have changed")
        return doc

    def counts(self):
        with self._lock:
            return self._db.execute("SELECT COUNT(*), SUM(eligible) FROM documents").fetchone()

    def close(self):
        with self._lock:
            if not self._closed:
                self._db.close()
                os.close(self._fd)
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
