"""Recheck published pooled artifacts without rerunning retrieval or changing labels."""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from news_ir.assessment import validate_assessments
from news_ir.custom_depth20 import check_pool, check_seed, dump
from news_ir.data import sha256_file
from news_ir.demo import DemoService
from news_ir.evaluation import evaluate_rankings


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    folder = ROOT / "artifacts/evaluations/custom20-depth20-v1"
    ann = ROOT / "annotations/ai_study_v1"
    pool = ROOT / "artifacts/assessments/custom20-v1"
    manifest = json.loads((folder / "manifest.json").read_text())
    for path, digest in manifest["input_hashes"].items():
        require(sha256_file(path) == digest, f"Input changed: {path}")
    for path, digest in manifest["files"].items():
        require(sha256_file(folder / path) == digest, f"Output changed: {path}")
    validated = validate_assessments(pool, ann / "assessments.depth20.jsonl")
    require(validated["complete_pool"] and validated["pooled_pairs"] == 737, "Incomplete pool")
    labels = list(map(json.loads, (ann / "assessments.depth20.jsonl").read_text().splitlines()))
    earlier = list(map(json.loads, (ann / "assessments.top5.jsonl").read_text().splitlines()))
    check_seed(labels, earlier)
    require(len(earlier) == 188, "Earlier snapshot count changed")
    service = DemoService(ROOT)  # Checks all saved run/evaluation/query/qrels hashes and eligible IDs.
    try:
        rankings = {e: {q: [h["doc_id"] for h in hits] for q, hits in rows.items()}
                    for e, rows in service.runs["custom"].items()}
        provenance = list(map(json.loads, (pool / "pool.provenance.jsonl").read_text().splitlines()))
        check_pool(provenance, rankings, 20)
        metrics = json.loads((folder / "metrics.json").read_text())
        for mode, engines in metrics.items():
            for engine, result in engines.items():
                require(evaluate_rankings(rankings[engine], validated["qrels"], gain_mode=mode) == result,
                        f"Recomputed metrics differ: {mode}/{engine}")
        visibility = json.loads((ann / "evidence_visibility.depth20.json").read_text())
        require(len(visibility["documents"]) == 737 and len(service.visibility) >= 737, "Visibility coverage")
        seen, hashes = set(), defaultdict(set)
        for row in labels:
            pair = row["query_id"], row["doc_id"]
            doc = service.document(row["doc_id"], "custom", row["query_id"])
            digest = hashlib.sha256(doc["contents"].encode()).hexdigest()
            require(digest == row["contents_sha256"], "Assessment/source text mismatch")
            audit = service.visibility[pair]
            require(audit["grade"] == row["grade"] and audit["evidence"] == [
                {**e, "fully_visible_to_e5": e["end"] <= audit["retained_contents_end_exclusive"]}
                for e in row["evidence"]], "Visibility/evidence mismatch")
            require(0 <= doc["e5_input_end"] <= len(doc["contents"]), "Invalid input offset")
            seen.add(pair)
            hashes[(row["query_id"], digest)].add(row["grade"])
        require(len(seen) == 737 and all(len(g) == 1 for g in hashes.values()), "Duplicate grade conflict")
    finally:
        service.close()
    checks = json.loads((folder / "crosscheck.json").read_text())
    require(all(c["status"] == "passed" for es in checks.values() for c in es.values()), "Native check failure")
    comparisons = sum(c["comparisons"] for es in checks.values() for c in es.values())
    require(comparisons == 588, "Native comparison count")
    figures = sorted((ROOT / "reports/figures/custom20-depth20").glob("*"))
    require(len(figures) == 6 and all(f.stat().st_size > 0 for f in figures), "Missing research figures")
    report = {"status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "assessed_pairs": len(labels), "preserved_top5_pairs": len(earlier),
              "saved_queries_bound_to_demo": 77, "recomputed_metric_policies": ["linear", "exp2"],
              "independent_native_comparisons": comparisons, "same_query_content_grade_conflicts": 0,
              "source_and_visibility_checks": len(seen), "research_figures": len(figures),
              "evaluation_manifest_sha256": sha256_file(folder / "manifest.json")}
    output = ROOT / "artifacts/custom20_depth20_validation.json"
    dump(output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
