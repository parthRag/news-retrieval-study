import copy
import importlib.util
import io
import json
import runpy
from pathlib import Path

import pytest

from news_ir.assessment import validate_assessments, write_jsonl
from news_ir.custom_depth20 import check_pool, check_seed, evaluate_depth20_study
from news_ir.data import sha256_file
from test_custom_top5 import make_pool_and_labels


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_complete_pool_native_metrics_and_earlier_labels(tiny_index, tmp_path):
    pool, labels, rows = make_pool_and_labels(tiny_index, tmp_path)
    output = tmp_path / "evaluation"
    result = evaluate_depth20_study(pool, labels, labels, tiny_index["index"], output, samples=100)
    assert result["aggregate"]["dense"]["ap_at_1000"] == 1
    assert result["aggregate"]["bm25"]["ap_at_1000"] == .5
    assert result["independent_metric_comparisons"] == 56
    assert "1-query" in result["paired"]["unit"]
    manifest = json.loads((output / "manifest.json").read_text())
    assert all(sha256_file(output / f) == digest for f, digest in manifest["files"].items())
    with pytest.raises(FileExistsError):
        evaluate_depth20_study(pool, labels, labels, tiny_index["index"], output)


def test_incomplete_pool_cannot_publish_map(tiny_index, tmp_path):
    pool, labels, rows = make_pool_and_labels(tiny_index, tmp_path)
    write_jsonl(labels, rows[:1])
    with pytest.raises(ValueError, match="complete designated pool"):
        evaluate_depth20_study(pool, labels, labels, tiny_index["index"], tmp_path / "partial")
    assert not (tmp_path / "partial").exists()


def test_failed_native_check_leaves_no_partial_result(tiny_index, tmp_path, monkeypatch):
    pool, labels, _ = make_pool_and_labels(tiny_index, tmp_path)
    def fail(*a, **kw):
        raise ValueError("simulated native failure")
    monkeypatch.setattr("news_ir.custom_depth20.crosscheck", fail)
    with pytest.raises(ValueError, match="simulated"):
        evaluate_depth20_study(pool, labels, labels, tiny_index["index"], tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".failed.evaluating-*"))


def test_pool_ranks_priority_and_seed_cannot_drift():
    ranked = {"bm25": {"q": ["a", "b"]}, "dense": {"q": ["b", "c"]}}
    provenance = [{"query_id": "q", "doc_id": d, "component_ranks": rs, "priority_top5": True}
                  for d, rs in (("a", {"bm25": 1}), ("b", {"bm25": 2, "dense": 1}), ("c", {"dense": 2}))]
    check_pool(provenance, ranked, 20)
    wrong = copy.deepcopy(provenance)
    wrong[0]["component_ranks"]["bm25"] = 2
    with pytest.raises(ValueError, match="equal-depth"):
        check_pool(wrong, ranked, 20)
    wrong = copy.deepcopy(provenance)
    wrong[0]["priority_top5"] = False
    with pytest.raises(ValueError, match="priority"):
        check_pool(wrong, ranked, 20)
    with pytest.raises(ValueError, match="Duplicate"):
        check_pool(provenance + provenance[:1], ranked, 20)
    seed = [{"query_id": "q", "doc_id": "a", "grade": 2, "rationale": "Earlier evidence"}]
    check_seed(seed, seed)
    revised = copy.deepcopy(seed)
    revised[0]["rationale"] = "Rewritten"
    with pytest.raises(ValueError, match="Earlier"):
        check_seed(revised, seed)


def install_reading_fixture(tiny_index, tmp_path):
    pool, labels, rows = make_pool_and_labels(tiny_index, tmp_path)
    destination = tmp_path / "artifacts/assessments/custom20-v1"
    destination.parent.mkdir(parents=True)
    pool.rename(destination)
    annotation = tmp_path / "annotations/ai_study_v1"
    annotation.mkdir(parents=True)
    packets = list(map(json.loads, (destination / "articles.blinded.jsonl").read_text().splitlines()))
    lookup = {r["doc_id"]: r for r in rows}
    write_jsonl(annotation / "assessments.top5.jsonl", [lookup[packets[0]["doc_id"]]])
    return destination, annotation, packets


def test_depth_recorder_seed_atomicity_and_stable_pending_positions(tiny_index, tmp_path, monkeypatch, capsys):
    pool, annotation, packets = install_reading_fixture(tiny_index, tmp_path)
    original = (annotation / "assessments.top5.jsonl").read_bytes()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["read", "q", "--scope", "depth20", "--pending-only"])
    runpy.run_path(str(SCRIPTS / "read_assessment_batch.py"), run_name="__main__")
    shown = capsys.readouterr().out
    assert "ARTICLE 1 " in shown and "ARTICLE 0 " not in shown
    request = {"query_id": "q", "rows": [[1, 0, [packets[1]["title"]], "Explicit manual fixture decision"]]}
    monkeypatch.setattr("sys.argv", ["record", "--scope", "depth20"])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    runpy.run_path(str(SCRIPTS / "record_top5_decisions.py"), run_name="__main__")
    assert (annotation / "assessments.top5.jsonl").read_bytes() == original
    output = annotation / "assessments.depth20.jsonl"
    assert output.read_bytes().startswith(original)
    assert validate_assessments(pool, output)["complete_pool"]
    before = output.read_bytes()
    request["rows"][0][2] = ["fabricated evidence"]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    with pytest.raises(ValueError, match="Evidence absent"):
        runpy.run_path(str(SCRIPTS / "record_top5_decisions.py"), run_name="__main__")
    assert output.read_bytes() == before


def test_reader_stops_before_long_body_and_explicit_chunks(tiny_index, tmp_path, monkeypatch, capsys):
    _, _, packets = install_reading_fixture(tiny_index, tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["read", "q", "--scope", "depth20", "--max-chars", "1"])
    runpy.run_path(str(SCRIPTS / "read_assessment_batch.py"), run_name="__main__")
    assert "long body" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["read", "q", "--scope", "depth20", "--end", "1", "--body-end", "3"])
    runpy.run_path(str(SCRIPTS / "read_assessment_batch.py"), run_name="__main__")
    assert packets[0]["text"][:3] in capsys.readouterr().out


def test_identical_reuse_requires_same_query_and_exact_contents(tiny_index, tmp_path):
    pool, labels, rows = make_pool_and_labels(tiny_index, tmp_path)
    packets = list(map(json.loads, (pool / "articles.blinded.jsonl").read_text().splitlines()))
    source = packets[0]
    identical = {**source, "doc_id": "duplicate"}
    other_query = {**source, "query_id": "different-query", "doc_id": "other-query-copy"}
    write_jsonl(pool / "articles.blinded.jsonl", packets + [identical, other_query])
    protocol = json.loads((pool / "protocol.json").read_text())
    protocol["files"]["articles.blinded.jsonl"] = sha256_file(pool / "articles.blinded.jsonl")
    (pool / "protocol.json").write_text(json.dumps(protocol))
    spec = importlib.util.spec_from_file_location("reuse", SCRIPTS / "reuse_identical_assessments.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "reused.jsonl"
    result = module.reuse_identical(pool, labels, output)
    copied = list(map(json.loads, output.read_text().splitlines()))
    assert result["reused_pairs_added"] == 1
    assert copied[-1]["doc_id"] == "duplicate"
    assert copied[-1]["judgment_reuse"]["source_doc_id"] == source["doc_id"]
    assert not any(r["query_id"] == "different-query" for r in copied)
    before = output.read_bytes()
    bad = copy.deepcopy(rows)
    bad[0]["contents_sha256"] = "wrong"
    write_jsonl(labels, bad)
    with pytest.raises(ValueError, match="hash mismatch"):
        module.reuse_identical(pool, labels, output)
    assert output.read_bytes() == before
