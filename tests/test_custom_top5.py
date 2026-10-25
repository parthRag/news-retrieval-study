import io
import json
import runpy
from pathlib import Path

import pytest

from news_ir.assessment import prepare_pool, write_jsonl
from news_ir.custom_study import crosscheck_top5, evaluate_top5_study, uncertainty_bounds
from news_ir.evaluation import evaluate_query
from test_fusion_and_assessment import fixture_runs


@pytest.mark.parametrize("mode", ["linear", "exp2"])
def test_native_top5_check_retains_zero_positive_query(tmp_path, mode):
    labels = {"q1": {"a": 2, "b": 1}, "q2": {"z": 0}}
    ranked = {"q1": ["b", "a"], "q2": ["z"]}
    measured = {q: evaluate_query(ds, labels[q], gain_mode=mode) for q, ds in ranked.items()}
    checked = crosscheck_top5(labels, ranked, measured, tmp_path, name="fixture", gain_mode=mode)
    assert checked["comparisons"] == 6
    assert "map" not in (tmp_path / "fixture.trec_eval.txt").read_text()
    assert ["ndcg_cut_5", "q2", "0.0000"] in [line.split() for line in (tmp_path / "fixture.trec_eval.txt").read_text().splitlines()]


def test_grade_bounds_are_extreme_scenarios_not_new_labels():
    labels = {"q": {"a": 2, "b": 0}}
    result = uncertainty_bounds(labels, {"bm25": {"q": ["a"]}, "dense": {"q": ["b"]}},
                                [{"query_id": "q", "doc_id": "b", "confidence": "medium"}])
    assert result["per_query"]["q"]["scenarios"] == 3
    assert result["macro_difference_bounds"][0] == -1
    assert result["macro_difference_bounds"][1] == 0
    assert labels["q"]["b"] == 0


def make_pool_and_labels(tiny_index, tmp_path):
    args = fixture_runs(tiny_index, tmp_path)
    pool = tmp_path / "pool"
    prepare_pool(**args, output=pool)
    rows = []
    for a in map(json.loads, (pool / "articles.blinded.jsonl").read_text().splitlines()):
        rows.append({"query_id": "q", "doc_id": a["doc_id"], "grade": 2 if a["doc_id"] == "insect" else 0,
                     "assessor_type": "AI", "full_article_read": True, "confidence": "high",
                     "assessed_at_utc": "2026-10-25T00:00:00Z", "rationale": "Fixture",
                     "contents_sha256": a["contents_sha256"],
                     "evidence": [{"start": 0, "end": len(a["title"]), "quote": a["title"]}]})
    labels = tmp_path / "labels.jsonl"
    write_jsonl(labels, rows)
    return pool, labels, rows


def test_complete_top5_evaluation_does_not_publish_map(tiny_index, tmp_path):
    pool, labels, rows = make_pool_and_labels(tiny_index, tmp_path)
    result = evaluate_top5_study(pool, labels, tmp_path / "evaluation", samples=100)
    assert result["query_count"] == 1
    assert result["independent_metric_comparisons"] == 16
    assert result["aggregate"]["dense"]["ndcg_at_5"] == 1
    metrics = json.loads((tmp_path / "evaluation/metrics.json").read_text())
    assert "Withheld" in metrics["map_status"]
    assert "ap_at_1000" not in json.dumps(metrics)
    assert metrics["by_category"]["homonym"]["query_count"] == 1
    with pytest.raises(FileExistsError):
        evaluate_top5_study(pool, labels, tmp_path / "evaluation")
    write_jsonl(labels, rows[:1])
    with pytest.raises(ValueError, match="every query"):
        evaluate_top5_study(pool, labels, tmp_path / "partial")
    assert not (tmp_path / "partial").exists()


def test_failed_native_custom_check_is_not_published(tiny_index, tmp_path, monkeypatch):
    import news_ir.custom_study

    pool, labels, _ = make_pool_and_labels(tiny_index, tmp_path)
    def fail(*args, **kwargs):
        raise ValueError("simulated native check failure")
    monkeypatch.setattr(news_ir.custom_study, "crosscheck_top5", fail)
    with pytest.raises(ValueError, match="simulated"):
        evaluate_top5_study(pool, labels, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".failed.evaluating-*"))


def test_decision_recorder_validates_quotes_and_preserves_existing_decisions(tiny_index, tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/record_top5_decisions.py"
    pool, labels, rows = make_pool_and_labels(tiny_index, tmp_path)
    destination = tmp_path / "artifacts/assessments/custom20-v1"
    destination.parent.mkdir(parents=True)
    pool.rename(destination)
    annotation = tmp_path / "annotations/ai_study_v1"
    annotation.mkdir(parents=True)
    write_jsonl(annotation / "assessments.pilot.jsonl", [])
    articles = list(map(json.loads, (destination / "articles.blinded.jsonl").read_text().splitlines()))
    request = {"query_id": "q", "decisions": [{"position": 0, "grade": 2, "rationale": "Explicit fixture decision",
               "confidence": "high", "full_article_read": True, "quotes": [articles[0]["title"]]}]}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", [str(script)])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    runpy.run_path(str(script), run_name="__main__")
    original = (annotation / "assessments.top5.jsonl").read_bytes()
    request["decisions"][0]["quotes"] = ["fabricated evidence"]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    with pytest.raises(ValueError, match="Evidence absent"):
        runpy.run_path(str(script), run_name="__main__")
    assert (annotation / "assessments.top5.jsonl").read_bytes() == original
    request["decisions"][0]["quotes"] = [articles[0]["title"]]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    with pytest.raises(ValueError, match="Duplicate"):
        runpy.run_path(str(script), run_name="__main__")
    assert (annotation / "assessments.top5.jsonl").read_bytes() == original
