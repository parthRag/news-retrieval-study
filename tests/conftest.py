import json

import pytest

from news_ir.indexing import build_index


def write_corpus(path, rows):
    # Deliberately no trailing newline: offsets must still find the final record.
    path.write_bytes(b"\n".join(json.dumps(row, ensure_ascii=False).encode("utf-8") for row in rows))


@pytest.fixture(scope="session")
def tiny_index(tmp_path_factory):
    root = tmp_path_factory.mktemp("news-ir")
    corpus = root / "corpus.jsonl"
    rows = [
        {"_id": "sport", "title": "Cricket sport", "text": "cricket match bat championship"},
        {"_id": "insect", "title": "Cricket insect", "text": "cricket insect lifecycle antennae"},
        {"_id": "negative", "title": "Policy", "text": "The policy does not ban drones without review."},
        {"_id": "positive", "title": "Policy", "text": "The policy does ban drones after review."},
        {"_id": "title-only", "title": "Quasar astronomy", "text": ""},
        {"_id": "body-only", "title": "", "text": "Running marathon athletes in 2016"},
        {"_id": "empty", "title": " \t", "text": "\n"},
        {"_id": "tie-z", "title": "Tieprobe", "text": "identical content"},
        {"_id": "tie-a", "title": "Tieprobe", "text": "identical content"},
        {"_id": "0007-é", "title": "Montréal — café", "text": "Unicode café 日本語 and punctuation."},
    ]
    write_corpus(corpus, rows)
    index = root / "index"
    manifest = build_index(corpus, index, threads=1, batch_size=2)
    return {"root": root, "corpus": corpus, "index": index, "rows": rows, "manifest": manifest}
