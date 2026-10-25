import json

import numpy as np
import pytest

from news_ir.assessment import write_jsonl
from news_ir.data import sha256_file
from news_ir.evaluation import load_run, paired_comparison
from news_ir.expanded_study import clustered_comparison, join_saved_runs


def saved_part(root, qid, *, index, corpus="a" * 64, k1=.9):
    root.mkdir()
    queries = root / "source.jsonl"
    rows = [{"_id": qid, "text": "cricket insect"}]
    write_jsonl(queries, rows)
    write_jsonl(root / "queries.jsonl", rows)
    hits = [{"doc_id": "d2", "rank": 1, "score": .81234567891},
            {"doc_id": "d1", "rank": 2, "score": .81234567891}]
    write_jsonl(root / "results.jsonl", [{"query_id": qid, "query": rows[0]["text"], "hits": hits}])
    (root / "run.trec").write_text("".join(f"{qid} Q0 {h['doc_id']} {h['rank']} {h['score']:.9g} source\n" for h in hits))
    manifest = {"engine": "lucene-bm25", "run_tag": "source", "coverage": "full", "top_k": 1000,
                "query_count": 1, "total_hits": 2, "corpus_sha256": corpus,
                "index_manifest_sha256": sha256_file(index / "manifest.json"),
                "retrieval_config": {"k1": k1, "b": .4}, "analyzer": {"stemming": False},
                "query_source_sha256": sha256_file(queries),
                **{key: sha256_file(root / name) for name, key in
                   [("queries.jsonl", "query_snapshot_sha256"), ("results.jsonl", "results_sha256"),
                    ("run.trec", "run_sha256")]}}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return queries, root


@pytest.fixture
def parts(tmp_path):
    index = tmp_path / "index"
    index.mkdir()
    (index / "manifest.json").write_text('{"indexed_documents": 2}')
    first = saved_part(tmp_path / "old", "q1", index=index)
    second = saved_part(tmp_path / "new", "q2", index=index)
    combined = tmp_path / "combined.jsonl"
    combined.write_bytes(first[0].read_bytes() + second[0].read_bytes())
    return dict(queries_path=combined, components=[first, second], index_dir=index,
                eligible_ids={"d1", "d2"}, output=tmp_path / "joined")


def test_join_preserves_tied_ranks_scores_and_records_lineage(parts):
    before = {str(p): sha256_file(p) for _, root in parts["components"] for p in root.iterdir()}
    manifest = join_saved_runs(**parts)
    ranked, _ = load_run(parts["output"], parts["queries_path"], parts["eligible_ids"],
                         expected_source_sha256="a" * 64)
    assert ranked == {"q1": ["d2", "d1"], "q2": ["d2", "d1"]}
    rows = list(map(json.loads, (parts["output"] / "results.jsonl").read_text().splitlines()))
    assert rows[0]["hits"][0]["score"] == .81234567891
    assert manifest["components"][0]["query_count"] == 1
    assert "No combined timing" in manifest["latency_protocol"]
    assert all(sha256_file(p) == digest for p, digest in before.items())
    with pytest.raises(FileExistsError):
        join_saved_runs(**parts)


@pytest.mark.parametrize("change", ["overlap", "text", "missing", "config", "corpus", "index", "corrupt"])
def test_join_rejects_invalid_source_without_publishing(parts, change):
    queries, root = parts["components"][1]
    if change == "overlap":
        parts["components"][1] = parts["components"][0]
    elif change in {"text", "missing"}:
        rows = list(map(json.loads, parts["queries_path"].read_text().splitlines()))
        if change == "text":
            rows[1]["text"] = "different need"
        else:
            rows.pop()
        write_jsonl(parts["queries_path"], rows)
    elif change == "index":
        (parts["index_dir"] / "manifest.json").write_text("changed")
    elif change == "corrupt":
        (root / "run.trec").write_text("bad ranking")
    else:
        p = root / "manifest.json"
        manifest = json.loads(p.read_text())
        if change == "config":
            manifest["retrieval_config"]["k1"] = 1.2
        else:
            manifest["corpus_sha256"] = "b" * 64
        p.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        join_saved_runs(**parts)
    assert not parts["output"].exists()


def evaluations():
    first = {"per_query": {q: {"ndcg_at_5": 0., "ap_at_1000": 0.} for q in ["a", "b", "c"]}}
    second = {"per_query": {q: {"ndcg_at_5": v, "ap_at_1000": v / 2}
                            for q, v in zip(["a", "b", "c"], [1., -1., 1.])}}
    return first, second


def test_singleton_family_bootstrap_matches_query_bootstrap():
    first, second = evaluations()
    ordinary = paired_comparison(first, second, samples=300, seed=7)
    clustered = clustered_comparison(first, second, {q: q for q in first["per_query"]}, samples=300, seed=7)
    assert clustered["family_count"] == 3
    for m in ordinary["metrics"]:
        assert clustered["metrics"][m]["cluster_bootstrap_95_percentile_ci"] == ordinary["metrics"][m]["paired_bootstrap_95_percentile_ci"]


def test_unequal_family_sizes_keep_query_weighted_estimand():
    first, second = evaluations()
    actual = clustered_comparison(first, second, {"a": "x", "b": "x", "c": "y"}, samples=500, seed=3)
    draws = np.random.default_rng(3).integers(0, 2, size=(500, 2))
    expected = np.array([0., 1.])[draws].sum(axis=1) / np.array([2, 1])[draws].sum(axis=1)
    assert actual["metrics"]["ndcg_at_5"]["mean_dense_minus_bm25"] == pytest.approx(1 / 3)
    assert actual["metrics"]["ndcg_at_5"]["cluster_bootstrap_95_percentile_ci"] == np.quantile(expected, [.025, .975]).tolist()
    assert actual["metrics"]["ap_at_1000"]["mean_dense_minus_bm25"] == pytest.approx(1 / 6)


@pytest.mark.parametrize("families,samples", [({}, 100), ({"a": "", "b": "b", "c": "c"}, 100),
                                               ({"a": "x", "b": "x", "c": "y"}, 0)])
def test_cluster_bootstrap_rejects_missing_families_or_invalid_draws(families, samples):
    with pytest.raises(ValueError):
        clustered_comparison(*evaluations(), families, samples=samples)
