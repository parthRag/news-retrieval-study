import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from news_ir.data import DocumentStore, decode_document, read_queries, sha256_file


@pytest.mark.parametrize("value", [None, [], {}, {"_id": 1}, {"_id": " "},
    {"_id": "x", "title": None, "text": "a"}, {"_id": "x", "title": "a", "text": 3}])
def test_reject_invalid_document_fields(value):
    with pytest.raises(ValueError):
        decode_document(json.dumps(value))


@pytest.mark.parametrize("raw", [b"", b"\n", b"broken", b"\xff"])
def test_reject_malformed_document(raw):
    with pytest.raises(ValueError):
        decode_document(raw)


def test_roundtrip_all_records_with_unicode_and_empty_articles(tiny_index):
    with DocumentStore(tiny_index["index"]) as store:
        assert store.counts() == (10, 9)
        for row in tiny_index["rows"]:
            doc = store.get(row["_id"])
            assert (doc.doc_id, doc.title, doc.text) == (row["_id"], row["title"], row["text"])
        assert store.get("does-not-exist") is None
        assert store.get("' OR 1=1 --") is None


def test_concurrent_document_reads(tiny_index):
    with DocumentStore(tiny_index["index"]) as store:
        ids = [row["_id"] for row in tiny_index["rows"]] * 20
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(lambda doc_id: store.get(doc_id).doc_id, ids)) == ids


def test_closed_store_is_explicit(tiny_index):
    store = DocumentStore(tiny_index["index"])
    store.close()
    store.close()
    with pytest.raises(ValueError, match="closed"):
        store.get("sport")


def test_relocated_corpus_is_hashed(tiny_index, tmp_path):
    copy = tmp_path / "copy.jsonl"
    copy.write_bytes(tiny_index["corpus"].read_bytes())
    with DocumentStore(tiny_index["index"], corpus=copy) as store:
        assert store.get("sport").doc_id == "sport"
    copy.write_bytes(copy.read_bytes().replace(b"sport", b"spurt", 1))
    with pytest.raises(ValueError, match="hash differs"):
        DocumentStore(tiny_index["index"], corpus=copy)


@pytest.mark.parametrize("rows", [[], [{"_id": "x", "text": 1}],
    [{"_id": "bad id", "text": "q"}], [{"_id": "x", "text": "a"}, {"_id": "x", "text": "b"}]])
def test_reject_invalid_query_suites(tmp_path, rows):
    path = tmp_path / "queries.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError):
        read_queries(path)


def test_manifest_source_hash(tiny_index):
    assert sha256_file(tiny_index["corpus"]) == tiny_index["manifest"]["source"]["sha256"]
