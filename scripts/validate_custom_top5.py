"""Validate the 20-query top-five milestone and record reproducibility hashes."""

import json
from datetime import datetime, timezone
from pathlib import Path

from news_ir.assessment import assessed_top5_metrics, validate_assessments
from news_ir.data import sha256_file


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    root = Path(__file__).resolve().parents[1]
    annotation = root / "annotations/ai_study_v1"
    pool = root / "artifacts/assessments/custom20-v1"
    evaluation = root / "artifacts/evaluations/custom20-top5-v1"
    assessments = annotation / "assessments.top5.jsonl"
    frozen = json.loads((annotation / "protocol.json").read_text())
    original_hashes = {"queries.jsonl": "e0a8d8ec3b80cc06f07cbd1a72a48b7da30a7a7e00bda085e2701cb4dfc9737f",
                       "qrel.jsonl": "88b1da4ce3ec808287528218020199cd7c3c795b4690ab33acca4e4aca762a9a"}
    for name, digest in original_hashes.items():
        require(sha256_file(root / name) == digest, f"Original data changed: {name}")
    require(sha256_file(annotation / "queries.jsonl") == frozen["query_source_sha256"], "Frozen queries changed")
    require(sha256_file(annotation / "protocol.json") == sha256_file(pool / "protocol.json"), "Pool protocols differ")
    coverage = validate_assessments(pool, assessments)
    require(len(coverage["complete_top5_query_ids"]) == 20 and coverage["assessed_pairs"] == 188,
            "Expected complete 20-query top-five coverage")
    require(coverage["priority_top5_assessed"] == coverage["priority_top5_pairs"], "Unassessed priority pairs")
    manifest = json.loads((evaluation / "manifest.json").read_text())
    require(manifest["assessments_sha256"] == sha256_file(assessments), "Evaluation uses different decisions")
    for name, digest in manifest["files"].items():
        require(sha256_file(evaluation / name) == digest, f"Evaluation output changed: {name}")
    computed = assessed_top5_metrics(pool, assessments)
    saved = json.loads((evaluation / "metrics.json").read_text())
    for key in ("per_query", "query_ids", "query_count", "macro_over_completed_queries_only", "exp2_gain_sensitivity_ndcg_at_5"):
        require(computed[key] == saved[key], f"Top-five scores do not reproduce: {key}")
    require("ap_at_1000" not in json.dumps(saved), "Incomplete-pool AP must not be published")
    original_pilot = list(map(json.loads, (annotation / "assessments.pilot.jsonl").read_text().splitlines()))
    expanded = {(r["query_id"], r["doc_id"]): r for r in map(json.loads, assessments.read_text().splitlines())}
    require(all(expanded[r["query_id"], r["doc_id"]] == r for r in original_pilot), "Original pilot decisions changed")
    exported = list(map(json.loads, (evaluation / "qrels.top5.jsonl").read_text().splitlines()))
    require(len(exported) == 188 and {(r["query-id"], r["corpus-id"]): r["score"] for r in exported}
            == {pair: row["grade"] for pair, row in expanded.items()}, "Exported qrels differ from decisions")
    checks = json.loads((evaluation / "crosscheck.json").read_text())
    require(all(c["status"] == "passed" for modes in checks.values() for c in modes.values()), "Native metric check failed")
    comparisons = sum(c["comparisons"] for modes in checks.values() for c in modes.values())
    require(comparisons == 168, "Native check coverage changed")
    live_path = root / "artifacts/analysis/custom20-top5/local_h02_search.json"
    live = json.loads(live_path.read_text())
    cloud = next(r for r in map(json.loads, (root / "artifacts/runs/dense-custom-draft/results.jsonl").read_text().splitlines()) if r["query_id"] == "H02")
    require(live["query"] == cloud["query"] and live["coverage"] == "full", "Local smoke query differs")
    require([h["doc_id"] for h in live["hits"]] == [h["doc_id"] for h in cloud["hits"][:5]], "Local H02 IDs/order differ")
    max_score_difference = max(abs(a["score"] - b["score"]) for a, b in zip(live["hits"], cloud["hits"][:5], strict=True))
    require(max_score_difference < 1e-5, "Local H02 scores differ beyond float32 tolerance")
    figures = list((root / "reports/figures/custom20-top5").glob("*"))
    require(len(figures) == 6, "Expected two figures in PNG/SVG/PDF")
    files = [p for p in evaluation.rglob("*") if p.is_file()] + figures + [assessments, live_path]
    files += [annotation / n for n in ("content_quality.top5.json", "evidence_visibility.top5.json", "queries.jsonl", "protocol.json")]
    files += [root / p for p in ("src/news_ir/custom_study.py", "scripts/read_assessment_batch.py", "scripts/record_top5_decisions.py",
              "scripts/evaluate_custom_top5.py", "scripts/report_custom_top5.py", "scripts/validate_custom_top5.py",
              "tests/test_custom_top5.py", "reports/CUSTOM_20_TOP5.md", "reports/CUSTOM_20_ASSESSMENT_EVIDENCE.md", "reports/TASK_E_PROGRESS.md")]
    result = {"status": "passed", "validated_at_utc": datetime.now(timezone.utc).isoformat(),
              "original_query_qrel_hashes": original_hashes,
              "coverage": {k: v for k, v in coverage.items() if k != "qrels"},
              "independent_metric_comparisons": comparisons, "pilot_decisions_preserved": True,
              "local_h02_reproduction": {"same_ids_and_order": True, "maximum_score_difference": max_score_difference},
              "recorded_stage_checks": {"pytest": "121 passed in 29.09s; not rerun by this artifact verifier",
                                        "figures": "Both PNGs visually inspected"},
              "sha256": {str(p.relative_to(root)): sha256_file(p) for p in files},
              "scope": "All 20 top-five unions; deeper pool, MAP and demo incomplete; AI assessments disclosed"}
    (root / "artifacts/custom20_top5_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "sha256"}, indent=2))


if __name__ == "__main__":
    main()
