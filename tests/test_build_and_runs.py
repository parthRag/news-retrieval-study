import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import write_corpus
from news_ir.data import sha256_file
from news_ir.experiments import run_queries, verify_index
from news_ir.indexing import build_index


def test_never_overwrites_existing_index(tiny_index):
    original_hash = sha256_file(tiny_index["index"] / "manifest.json")
    with pytest.raises(FileExistsError):
        build_index(tiny_index["corpus"], tiny_index["index"])
    assert sha256_file(tiny_index["index"] / "manifest.json") == original_hash


@pytest.mark.parametrize("kind", ["duplicate", "malformed", "empty", "only-empty"])
def test_failed_build_is_not_published(tmp_path, kind):
    corpus, index = tmp_path / "source.jsonl", tmp_path / "index"
    row = {"_id": "same", "title": "valid", "text": "article"}
    if kind == "duplicate":
        write_corpus(corpus, [row, row])
    elif kind == "malformed":
        corpus.write_text(json.dumps(row) + "\nnot-json")
    elif kind == "empty":
        corpus.write_text("")
    else:
        write_corpus(corpus, [{"_id": "empty", "title": "", "text": " "}])
    with pytest.raises(ValueError):
        build_index(corpus, index, threads=1)
    assert not index.exists()
    assert not list(tmp_path.glob(".index.building-*"))


def test_verify_index(tiny_index):
    result = verify_index(tiny_index["index"], sample_size=100)
    assert result["status"] == "passed"
    assert result["lookup_samples"] == 10
    assert result["indexed_documents"] == 9


def test_export_complete_reproducible_trec_runs(tiny_index, tmp_path):
    queries = tmp_path / "queries.jsonl"
    queries.write_text('\n'.join(json.dumps(row) for row in [
        {"_id": "q1", "text": "cricket"}, {"_id": "q2", "text": ""},
        {"_id": "q3", "text": "quasar"}]))
    output = tmp_path / "run"
    result = run_queries(tiny_index["index"], queries, output, top_k=5)
    assert result["query_count"] == 3
    assert result["empty_query_ids"] == ["q2"]
    assert result["total_hits"] == 3
    assert result["run_sha256"] == sha256_file(output / "run.trec")
    assert result["corpus_sha256"] == tiny_index["manifest"]["source"]["sha256"]
    rows = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert [row["query_id"] for row in rows] == ["q1", "q2", "q3"]
    assert rows[1]["hits"] == []
    for line in (output / "run.trec").read_text().splitlines():
        qid, iteration, docid, rank, score, tag = line.split()
        assert iteration == "Q0" and tag == "bm25"
        assert int(rank) > 0 and float(score) > 0
    second = tmp_path / "run2"
    run_queries(tiny_index["index"], queries, second, top_k=5)
    assert (output / "run.trec").read_bytes() == (second / "run.trec").read_bytes()
    with pytest.raises(FileExistsError):
        run_queries(tiny_index["index"], queries, output)


def test_reject_bad_queries_before_publishing_run(tiny_index, tmp_path):
    queries = tmp_path / "bad.jsonl"
    queries.write_text('{"_id":"x", "text":"term"}\n{"_id":"x", "text":"other"}')
    with pytest.raises(ValueError, match="duplicate"):
        run_queries(tiny_index["index"], queries, tmp_path / "bad-run")
    assert not (tmp_path / "bad-run").exists()


def test_cli_search_and_errors(tiny_index):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_ADMIN_KEY", None)
    command = [sys.executable, "-m", "news_ir", "search", "quasar", "--index", str(tiny_index["index"])]
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["hits"][0]["doc_id"] == "title-only"
    result = subprocess.run(command + ["--top-k", "0"], capture_output=True, text=True, env=env)
    assert result.returncode == 2
    assert "top_k" in result.stderr


def test_local_bm25_does_not_import_api_encoders(tiny_index):
    from news_ir.retrieval import BM25Engine
    with BM25Engine(tiny_index["index"]) as engine:
        assert engine.search("cricket")
    assert "pyserini.encode" not in sys.modules
    assert "openai" not in sys.modules


@pytest.mark.parametrize("change", ["analyzer", "count", "schema"])
def test_reject_inconsistent_manifest(tiny_index, tmp_path, change):
    from news_ir.retrieval import BM25Engine
    index = tmp_path / "copy"
    shutil.copytree(tiny_index["index"], index)
    path = index / "manifest.json"
    manifest = json.loads(path.read_text())
    if change == "analyzer":
        manifest["analyzer"]["stemming"] = True
    elif change == "count":
        manifest["documents"]["indexed"] += 1
    else:
        manifest["schema_version"] = 999
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        BM25Engine(index)


def test_source_modification_guard_and_deep_hash_check(tmp_path):
    from news_ir.data import DocumentStore
    corpus = tmp_path / "source.jsonl"
    index = tmp_path / "index"
    write_corpus(corpus, [{"_id": "a", "title": "", "text": "original"}])
    build_index(corpus, index, threads=1)
    before = corpus.stat()
    corpus.write_bytes(corpus.read_bytes().replace(b"original", b"modified"))
    with pytest.raises(ValueError, match="modification time"):
        DocumentStore(index)
    # Deep verification also detects equal-length changes with preserved mtime.
    os.utime(corpus, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(ValueError, match="SHA-256"):
        verify_index(index)


def test_cli_index_outputs_parseable_json_and_missing_document_errors(tmp_path):
    corpus = tmp_path / "source.jsonl"
    index = tmp_path / "index"
    write_corpus(corpus, [{"_id": "a", "title": "Article", "text": "Some text"}])
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-m", "news_ir", "index", "--corpus", str(corpus),
                             "--output", str(index), "--threads", "1"],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["documents"]["indexed"] == 1
    result = subprocess.run([sys.executable, "-m", "news_ir", "document", "absent", "--index", str(index)],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 2
    assert "Unknown document ID" in result.stderr
