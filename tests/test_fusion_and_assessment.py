import copy
import json

import pytest

from news_ir.assessment import assessed_top5_metrics, prepare_pool, text_hash, validate_assessments, write_jsonl
from news_ir.data import sha256_file
from news_ir.fusion import evaluate_fusion, fuse_runs, reciprocal_rank_fusion


def test_rrf_hand_computed_overlap_and_ties():
    hits = reciprocal_rank_fusion([["a", "b", "x"], ["b", "a", "y"]], k=60)
    assert [h["doc_id"] for h in hits] == ["a", "b", "x", "y"]
    assert hits[0]["score"] == pytest.approx(1 / 61 + 1 / 62)
    assert hits[2]["score"] == pytest.approx(1 / 63)
    assert [h["rank"] for h in hits] == [1, 2, 3, 4]
    assert reciprocal_rank_fusion([[], ["z"]], depth=1)[0]["doc_id"] == "z"
    # Component scores are deliberately absent: incompatible BM25/cosine scales cannot leak in.
    with pytest.raises(ValueError, match="Duplicate"):
        reciprocal_rank_fusion([["a", "a"], []])
    with pytest.raises(ValueError, match="two"):
        reciprocal_rank_fusion([["a"]])


@pytest.mark.parametrize("kwargs", [{"k": 0}, {"k": True}, {"depth": -1}, {"depth": 1.5}])
def test_rrf_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[], []], **kwargs)


def fixture_runs(tiny_index, tmp_path):
    """Write tiny saved runs without importing PyTorch/FAISS or encoding a model."""
    queries = tmp_path / "queries.jsonl"
    write_jsonl(queries, [{"_id": "q", "text": "cricket insect", "category": "homonym",
                           "relevant_if": "insect", "exclude_if": "sport", "grade_0": "wrong",
                           "grade_1": "partial", "grade_2": "direct"}])
    source_hash = tiny_index["manifest"]["source"]["sha256"]
    dense_index = tmp_path / "dense-index"
    dense_index.mkdir()
    (dense_index / "manifest.json").write_text(json.dumps({"indexed_documents": 9}))
    paths = {}
    for name, engine, index, ids in (("bm25", "lucene-bm25", tiny_index["index"], ["sport", "insect"]),
                                     ("dense", "e5-cosine", dense_index, ["insect", "sport"])):
        path = tmp_path / name
        path.mkdir()
        paths[name] = path
        hits = [{"doc_id": doc, "rank": rank, "score": 3.0 - rank} for rank, doc in enumerate(ids, 1)]
        write_jsonl(path / "results.jsonl", [{"query_id": "q", "query": "cricket insect", "hits": hits}])
        write_jsonl(path / "queries.jsonl", [{"_id": "q", "text": "cricket insect"}])
        (path / "run.trec").write_text("".join(f"q Q0 {h['doc_id']} {h['rank']} {h['score']:.9g} {name}\n" for h in hits))
        (path / "manifest.json").write_text(json.dumps({
            "engine": engine, "coverage": "full", "run_tag": name, "top_k": 1000,
            "query_count": 1, "total_hits": 2, "corpus_sha256": source_hash,
            "query_source_sha256": sha256_file(queries), "index_path": str(index),
            "index_manifest_sha256": sha256_file(index / "manifest.json"),
            **{key: sha256_file(path / file) for file, key in
               (("queries.jsonl", "query_snapshot_sha256"), ("results.jsonl", "results_sha256"), ("run.trec", "run_sha256"))}}))
    return dict(queries_path=queries, bm25_run=paths["bm25"], dense_run=paths["dense"], document_index=tiny_index["index"])


def test_saved_fusion_evaluation_and_provenance(tiny_index, tmp_path):
    arguments = fixture_runs(tiny_index, tmp_path)
    output = tmp_path / "rrf"
    manifest = fuse_runs(**arguments, output=output)
    assert manifest["engine"] == "rrf" and manifest["total_hits"] == 2
    assert "excludes both engine" in manifest["latency_protocol"]
    with pytest.raises(FileExistsError):
        fuse_runs(**arguments, output=output)
    qrels = tmp_path / "qrels.jsonl"
    write_jsonl(qrels, [{"query-id": "q", "corpus-id": "insect", "score": 2},
                       {"query-id": "q", "corpus-id": "sport", "score": 0}])
    result = evaluate_fusion(**arguments, qrels_path=qrels, fusion_run=output, output=tmp_path / "eval", samples=100)
    assert result["independent_comparisons"] == 56
    assert result["primary"]["dense"]["ndcg_at_5"] == 1
    assert result["primary"]["rrf"]["ndcg_at_5"] == 1  # ID tie-break puts insect first.
    with pytest.raises(FileExistsError):
        evaluate_fusion(**arguments, qrels_path=qrels, fusion_run=output, output=tmp_path / "eval")
    meta = json.loads((output / "manifest.json").read_text())
    meta["components"]["dense"]["run_sha256"] = "wrong"
    (output / "manifest.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="components"):
        evaluate_fusion(**arguments, qrels_path=qrels, fusion_run=output, output=tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_pool_membership_blinding_and_evidence_validation(tiny_index, tmp_path):
    arguments = fixture_runs(tiny_index, tmp_path)
    pool = tmp_path / "pool"
    protocol = prepare_pool(**arguments, output=pool)
    assert protocol["pooled_pairs"] == protocol["priority_top5_pairs"] == 2
    with pytest.raises(FileExistsError):
        prepare_pool(**arguments, output=pool)
    packets = [json.loads(line) for line in (pool / "articles.blinded.jsonl").read_text().splitlines()]
    assert all(set(p) == {"query_id", "doc_id", "title", "text", "contents_sha256"} for p in packets)
    rows = []
    for packet in packets:
        contents = (packet["title"] + "\n" + packet["text"]).strip()
        rows.append({"query_id": "q", "doc_id": packet["doc_id"], "grade": 2 if packet["doc_id"] == "insect" else 0,
                     "assessor_type": "AI", "full_article_read": True, "confidence": "high",
                     "assessed_at_utc": "2026-10-25T00:00:00Z", "rationale": "Fixture evidence check",
                     "contents_sha256": text_hash(contents),
                     "evidence": [{"start": 0, "end": len(packet["title"]), "quote": packet["title"]}]})
    labels = tmp_path / "labels.jsonl"
    write_jsonl(labels, rows[:1])
    partial = validate_assessments(pool, labels)
    assert partial["remaining_pairs"] == 1 and partial["complete_top5_query_ids"] == []
    with pytest.raises(ValueError, match="No query"):
        assessed_top5_metrics(pool, labels)
    write_jsonl(labels, rows)
    assert validate_assessments(pool, labels)["complete_top5_query_ids"] == ["q"]
    metrics = assessed_top5_metrics(pool, labels)
    assert metrics["per_query"]["q"]["dense"]["ndcg_at_5"] == 1
    assert metrics["per_query"]["q"]["bm25"]["ndcg_at_5"] < 1
    assert not any("ap_at" in key for key in metrics["macro_over_completed_queries_only"]["dense"])
    for mutate in (lambda r: r.update(grade=True), lambda r: r.update(assessor_type="human"),
                   lambda r: r.update(full_article_read=False), lambda r: r.update(doc_id="not-in-pool"),
                   lambda r: r.update(contents_sha256="wrong"),
                   lambda r: r["evidence"][0].update(quote="fabricated")):
        bad = copy.deepcopy(rows)
        mutate(bad[0])
        write_jsonl(labels, bad)
        with pytest.raises(ValueError):
            validate_assessments(pool, labels)
    write_jsonl(labels, rows + rows[:1])
    with pytest.raises(ValueError, match="Duplicate"):
        validate_assessments(pool, labels)
    (pool / "articles.blinded.jsonl").write_text("corrupted")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_assessments(pool, labels)


def test_failed_fusion_is_not_published(tiny_index, tmp_path, monkeypatch):
    import news_ir.fusion

    arguments = fixture_runs(tiny_index, tmp_path)
    def fail(*args, **kwargs):
        raise ValueError("simulated failure")
    monkeypatch.setattr(news_ir.fusion, "reciprocal_rank_fusion", fail)
    with pytest.raises(ValueError, match="simulated"):
        fuse_runs(**arguments, output=tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".failed.fusing-*"))
