import json
import math

import pytest

from news_ir.benchmark import crosscheck
from news_ir.evaluation import evaluate_query, evaluate_rankings, gain, load_qrels, load_run, paired_comparison


def test_hand_computed_graded_ndcg_and_all_positive_ap_denominator():
    qrels = {"a": 3, "b": 2, "c": 1, "missing": 2, "z": 0}
    actual = evaluate_query(["unjudged", "b", "a"], qrels)
    ideal = 3 + 2 / math.log2(3) + 2 / math.log2(4) + 1 / math.log2(5)
    dcg = 2 / math.log2(3) + 3 / math.log2(4)
    assert actual["ndcg_at_5"] == pytest.approx(dcg / ideal, abs=1e-12)
    assert actual["ap_at_1000"] == pytest.approx((1 / 2 + 2 / 3) / 4)
    assert actual["recall_at_1000"] == 0.5
    assert actual["precision_at_5"] == 0.4
    assert actual["judged_at_5"] == 2 / 3
    assert actual["reciprocal_rank_at_1000"] == 0.5


@pytest.mark.parametrize("mode,expected", [("linear", 3), ("exp2", 7), ("news2019", 8)])
def test_explicit_gain_conventions(mode, expected):
    assert gain(3, mode) == expected and gain(0, mode) == 0
    assert evaluate_query(["a"], {"a": 3}, gain_mode=mode)["ndcg_at_5"] == 1


def test_empty_and_zero_relevant_queries_remain_in_average():
    scores = evaluate_rankings({"q1": ["a"], "q2": [], "q3": ["u"]},
                               {"q1": {"a": 1}, "q2": {"b": 1}, "q3": {"z": 0}})
    assert scores["query_count"] == 3
    assert scores["aggregate"]["ap_at_1000"] == pytest.approx(1 / 3)
    assert scores["zero_relevant_queries"] == ["q3"]
    assert scores["per_query"]["q2"]["ndcg_at_5"] == 0
    with pytest.raises(ValueError, match="query sets"):
        evaluate_rankings({"q1": []}, {"q2": {"a": 1}})
    with pytest.raises(ValueError, match="empty query"):
        evaluate_rankings({}, {})


def test_cutoff_and_missing_positive_policy():
    ranking = [f"u{i}" for i in range(1000)] + ["a"]
    assert evaluate_query(ranking, {"a": 2})["ap_at_1000"] == 0
    full = evaluate_query(["a"], {"a": 1, "unavailable": 2})
    available = evaluate_query(["a"], {"a": 1})
    assert full["ap_at_1000"] == 0.5 and available["ap_at_1000"] == 1
    assert full["ndcg_at_5"] < available["ndcg_at_5"]
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate_query(["a", "a"], {"a": 1})


@pytest.mark.parametrize("grade", [True, "1.5", -1, 5, None])
def test_bad_qrel_grades_are_rejected(tmp_path, grade):
    path = tmp_path / "qrels.jsonl"
    path.write_text(json.dumps({"query-id": "q", "corpus-id": "d", "score": grade}))
    with pytest.raises(ValueError):
        load_qrels(path, ["q"])


def test_qrel_pairs_and_expected_query_coverage(tmp_path):
    path = tmp_path / "qrels.jsonl"
    row = {"query-id": "q", "corpus-id": "d", "score": "1"}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row))
    with pytest.raises(ValueError, match="Duplicate"):
        load_qrels(path, ["q"])
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="Every query"):
        load_qrels(path, ["q", "missing"])
    with pytest.raises(ValueError, match="Invalid"):
        load_qrels(path, ["other"])


def test_paired_bootstrap_is_reproducible_and_preserves_pairs():
    qrels = {"q1": {"a": 1}, "q2": {"b": 1}}
    first = evaluate_rankings({"q1": [], "q2": []}, qrels)
    second = evaluate_rankings({"q1": ["a"], "q2": ["b"]}, qrels)
    result = paired_comparison(first, second, samples=100, seed=1)
    assert result == paired_comparison(first, second, samples=100, seed=1)
    for values in result["metrics"].values():
        assert values["dense_wins"] == 2 and values["bm25_wins"] == values["ties"] == 0
        assert values["paired_bootstrap_95_percentile_ci"] == [1, 1]


@pytest.mark.parametrize("mode", ["linear", "exp2", "news2019"])
def test_independent_trec_eval_with_unjudged_missing_and_empty_query(tmp_path, mode):
    qrels = {"q1": {"a": 3, "b": 1, "missing": 2, "z": 0}, "q2": {"x": 1}}
    rankings = {"q1": ["unjudged", "b", "a", "z"], "q2": []}
    expected = evaluate_rankings(rankings, qrels, gain_mode=mode)
    result = crosscheck(qrels, rankings, expected, tmp_path, name="fixture", gain_mode=mode)
    assert result["status"] == "passed" and result["comparisons"] == 14
    assert result["empty_query_zero_metrics_checked"] == 7


def test_run_loader_rejects_corruption(tiny_index, tmp_path):
    from news_ir.experiments import run_queries

    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps({"_id": "q", "text": "cricket"}) + "\n")
    output = tmp_path / "run"
    run_queries(tiny_index["index"], queries, output, top_k=1000)
    eligible = {r["_id"] for r in tiny_index["rows"] if r["_id"] != "empty"}
    rankings, _ = load_run(output, queries, eligible, expected_source_sha256=tiny_index["manifest"]["source"]["sha256"])
    assert len(rankings["q"]) == 2
    with (output / "run.trec").open("a") as stream:
        stream.write("invalid")
    with pytest.raises(ValueError, match="hash"):
        load_run(output, queries, eligible, expected_source_sha256=tiny_index["manifest"]["source"]["sha256"])


def test_complete_comparison_publishes_only_after_independent_checks(tiny_index, tmp_path, monkeypatch):
    import news_ir.benchmark
    import news_ir.dense
    from news_ir.dense import build_dense_index, encode_corpus
    from news_ir.experiments import run_queries
    from test_dense import FixtureEncoder

    class Encoder(FixtureEncoder):
        def __init__(self, *args, **kwargs):
            super().__init__()
    monkeypatch.setattr(news_ir.dense, "E5Encoder", Encoder)
    queries, qrels = tmp_path / "queries.jsonl", tmp_path / "qrels.jsonl"
    queries.write_text('\n'.join(json.dumps(row) for row in [
        {"_id": "q1", "text": "cricket insect"}, {"_id": "q2", "text": "quasar"}]))
    qrels.write_text('\n'.join(json.dumps({"query-id": qid, "corpus-id": doc, "score": grade})
                              for qid, doc, grade in [("q1", "insect", 2), ("q1", "sport", 1),
                                                      ("q1", "absent", 3), ("q2", "title-only", 3)]))
    encode_corpus(tiny_index["index"], "unused", tmp_path / "encodings", encoder=Encoder())
    build_dense_index(tmp_path / "encodings", tmp_path / "dense", document_index=tiny_index["index"], model_dir="unused")
    run_queries(tiny_index["index"], queries, tmp_path / "bm25-run", top_k=1000)
    run_queries(tmp_path / "dense", queries, tmp_path / "dense-run", engine_type="dense", top_k=1000,
                document_index=tiny_index["index"], model_dir="unused")
    arguments = dict(queries_path=queries, qrels_path=qrels, bm25_run=tmp_path / "bm25-run",
                     dense_run=tmp_path / "dense-run", document_index=tiny_index["index"], bootstrap_samples=100)
    output = tmp_path / "evaluation"
    result = news_ir.benchmark.compare_benchmark(**arguments, output=output)
    assert result["query_count"] == 2 and result["independent_crosscheck"] == "passed"
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["unavailable_positive_judgments"] == 1
    metrics = json.loads((output / "metrics.json").read_text())
    assert metrics["available_corpus"]["dense"]["aggregate"]["ap_at_1000"] > metrics["primary"]["dense"]["aggregate"]["ap_at_1000"]
    with pytest.raises(FileExistsError):
        news_ir.benchmark.compare_benchmark(**arguments, output=output)
    def fail(*args, **kwargs):
        raise ValueError("simulated independent check failure")
    monkeypatch.setattr(news_ir.benchmark, "crosscheck", fail)
    with pytest.raises(ValueError, match="independent"):
        news_ir.benchmark.compare_benchmark(**arguments, output=tmp_path / "failed")
    assert not (tmp_path / "failed").exists() and not list(tmp_path.glob(".failed.evaluating-*"))
