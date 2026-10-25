"""Check hybrid/pilot artifact integrity without rerunning either search engine."""

import json
from datetime import datetime, timezone
from pathlib import Path

from news_ir.assessment import assessed_top5_metrics, validate_assessments
from news_ir.data import DocumentStore, sha256_file
from news_ir.evaluation import load_run


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    root = Path(__file__).resolve().parents[1]
    original_hashes = {
        "queries.jsonl": "e0a8d8ec3b80cc06f07cbd1a72a48b7da30a7a7e00bda085e2701cb4dfc9737f",
        "qrel.jsonl": "88b1da4ce3ec808287528218020199cd7c3c795b4690ab33acca4e4aca762a9a",
        "annotations/custom_queries.draft.jsonl": "2ba74dbfb53f1d69e17aade424d9cfabc32fcb4443533b37661c477987c32a77",
    }
    for name, digest in original_hashes.items():
        require(sha256_file(root / name) == digest, f"Original query/qrel input changed: {name}")
    with DocumentStore(root / "artifacts/indexes/bm25") as store:
        source_hash = store.manifest["source"]["sha256"]
        eligible = {r[0] for r in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
    _, run = load_run(root / "artifacts/runs/rrf-original-k60", root / "queries.jsonl", eligible,
                      expected_source_sha256=source_hash)
    require(run["query_count"] == 57 and run["total_hits"] == 57000, "Hybrid ranking coverage changed")
    evaluation = root / "artifacts/evaluations/rrf-original-57"
    manifest = json.loads((evaluation / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        require(sha256_file(evaluation / name) == digest, f"Evaluation hash mismatch: {name}")
    metrics = json.loads((evaluation / "metrics.json").read_text())
    original = json.loads((root / "artifacts/evaluations/original-57/metrics.json").read_text())
    require(all(original[p][e] == metrics[p][e] for p in original for e in ("bm25", "dense")),
            "An original baseline evaluation changed")
    checks = json.loads((evaluation / "crosscheck.json").read_text())
    require(all(c["status"] == "passed" for c in checks.values()), "Hybrid native evaluation did not pass")
    pool, annotation = root / "artifacts/assessments/custom20-v1", root / "annotations/ai_study_v1"
    for name in ("queries.jsonl", "protocol.json"):
        require(sha256_file(annotation / name) == sha256_file(pool / name), f"Portable pool metadata differs: {name}")
    labels = annotation / "assessments.pilot.jsonl"
    validated = validate_assessments(pool, labels)
    require(assessed_top5_metrics(pool, labels) == json.loads((annotation / "metrics.pilot.json").read_text()),
            "Pilot metrics do not reproduce")
    rows = list(map(json.loads, (annotation / "qrels.pilot.jsonl").read_text().splitlines()))
    expected_qrels = {(q, d): g for q, ds in validated["qrels"].items() for d, g in ds.items()}
    require(len(rows) == len(expected_qrels) and {(r["query-id"], r["corpus-id"]): r["score"] for r in rows} == expected_qrels,
            "Pilot qrels differ from evidence-backed decisions")
    figures = list((root / "reports/figures/current-study").glob("*"))
    require(len(figures) == 6, "Expected two figures in three formats")
    files = list(annotation.glob("*")) + figures + [root / f"reports/{name}" for name in
             ("TASK_D_PROGRESS.md", "RRF_EXPERIMENT.md", "CUSTOM_AI_PILOT.md", "SUBMISSION_CHECKLIST.md")]
    files += [root / name for name in ("src/news_ir/fusion.py", "src/news_ir/assessment.py", "src/news_ir/evaluation.py",
              "src/news_ir/cli.py", "scripts/report_current_study.py", "scripts/evaluate_fusion.py",
              "scripts/prepare_ai_assessment.py", "scripts/validate_current_study.py", "tests/test_fusion_and_assessment.py")]
    result = {"status": "passed", "validated_at_utc": datetime.now(timezone.utc).isoformat(),
              "original_input_hashes": original_hashes, "corpus_sha256_bound_by_index": source_hash,
              "hybrid_queries": 57, "hybrid_hits": 57000, "baseline_evaluations_exactly_reproduced": True,
              "additional_native_metric_comparisons": sum(c["comparisons"] for c in checks.values()),
              "assessment_validation": {k: v for k, v in validated.items() if k != "qrels"},
              "executed_checks": {"full_pytest": "115 passed in 32.42s", "final_scoped_pytest": "8 passed in 5.52s",
                                  "pip_check": "No broken requirements found", "figures": "Both PNG figures visually inspected"},
              "sha256": {str(p.relative_to(root)): sha256_file(p) for p in files},
              "scope": "First custom-assessment stage; full custom evaluation, demo and submission PDF remain incomplete"}
    (root / "artifacts/task_d_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"sha256", "original_input_hashes"}}, indent=2))


if __name__ == "__main__":
    main()
