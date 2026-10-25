"""Symmetric post-hoc filtering within each engine's fully judged top 20."""
import argparse
import csv
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from news_ir.assessment import validate_assessments
from news_ir.custom_depth20 import dump
from news_ir.data import sha256_file
from news_ir.demo import DemoService
from news_ir.quality import filter_candidates, quality_scores

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evaluations/quality-top20-v1")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new ablation output directory")
    pool = ROOT / "artifacts/assessments/custom20-v1"
    labels = ROOT / "annotations/ai_study_v1/assessments.depth20.jsonl"
    valid = validate_assessments(pool, labels)
    if not valid["complete_pool"]:
        raise ValueError("Complete candidate judgments required")
    source = pool / "articles.blinded.jsonl"
    articles, input_hashes = {}, {str(p.relative_to(ROOT)): sha256_file(p) for p in (source, labels)}
    for row in map(json.loads, source.read_text().splitlines()):
        articles.setdefault(row["query_id"], {})[row["doc_id"]] = row
    variants = {"baseline": (False, False), "no_empty_body": (True, False),
                "deduplicate": (False, True), "no_empty_body_and_deduplicate": (True, True)}
    service = DemoService(ROOT)
    metrics, rows, outputs = {}, [], []
    try:
        for variant, (empty, deduplicate) in variants.items():
            metrics[variant] = {}
            for engine, run in service.runs["custom"].items():
                per_query = {}
                for qid, hits in run.items():
                    candidates = [h["doc_id"] for h in hits[:20]]
                    selected = filter_candidates(candidates, articles[qid], empty=empty, deduplicate=deduplicate)
                    scores = quality_scores(selected, articles[qid], valid["qrels"][qid])
                    if variant == "baseline":
                        if scores["fixed_reference_ndcg_at_5"] != service.scores["custom"][engine]["per_query"][qid]["ndcg_at_5"]:
                            raise ValueError("Ablation baseline differs from frozen evaluation")
                    per_query[qid] = scores
                    rows.append({"variant": variant, "engine": engine, "query_id": qid, **scores})
                    outputs.append({"variant": variant, "engine": engine, "query_id": qid,
                                    "candidate_ids": candidates, "retained_ids": selected,
                                    "removed": len(candidates)-len(selected)})
                metrics[variant][engine] = {"per_query": per_query, "aggregate": {
                    m: sum(s[m] for s in per_query.values()) / len(per_query) for m in next(iter(per_query.values()))}}
    finally:
        service.close()
    if any(sha256_file(ROOT / p) != h for p, h in input_hashes.items()):
        raise ValueError("Ablation inputs changed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=".quality-evaluating-", dir=args.output.parent))
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "query_count": 20,
                "candidate_depth": 20, "assessor_type": "AI", "input_hashes": input_hashes,
                "baseline_manifest_sha256": sha256_file(ROOT / "artifacts/evaluations/custom20-depth20-v1/manifest.json"),
                "policy": "Post-hoc symmetric rules; preserve rank order; full-body whitespace empty check; exact title+body SHA256 deduplication; no score or label threshold; no refilling beyond original top 20",
                "metrics": "Fixed-reference nDCG@5 and P@5 use unchanged original pool labels/IDCG; unique-content nDCG@5 gives gain only to first occurrence and uses all unique pool contents for IDCG. These are separate measures. No MAP reported.",
                "limitations": "Exploratory analysis motivated by observed errors, not held-out tuning validation. Candidate horizon is fixed at 20; fewer than five retained results receive no padding credit. No corpus reindexing or new judgments.",
                "files": {}}
    try:
        dump(working / "metrics.json", metrics)
        (working / "rankings.jsonl").write_text("".join(json.dumps(r)+"\n" for r in outputs))
        with (working / "per_query.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        manifest["files"] = {p.name: sha256_file(p) for p in working.iterdir() if p.is_file()}
        dump(working / "manifest.json", manifest)
        working.rename(args.output)
    except BaseException:
        shutil.rmtree(working)
        raise
    print(json.dumps({v: {e: r["aggregate"] for e, r in es.items()} for v, es in metrics.items()}, indent=2))


if __name__ == "__main__":
    main()
