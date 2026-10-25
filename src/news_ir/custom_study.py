"""Complete top-five custom-query analysis; deeper-pool MAP is deliberately withheld."""

import importlib.resources
import itertools
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .assessment import assessed_top5_metrics, validate_assessments, write_jsonl
from .data import sha256_file
from .evaluation import evaluate_query, gain


def crosscheck_top5(qrels, rankings, metrics, output, *, name, gain_mode="linear"):
    """Check just nDCG@5 and P@5; do not expose AP from incomplete judgments."""
    from .runtime import configure_java

    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    labels, run = folder / f"{name}.qrels", folder / f"{name}.run"
    labels.write_text("".join(f"{q} 0 {d} {gain(g, gain_mode)}\n" for q, ds in qrels.items() for d, g in ds.items()))
    run.write_text("".join(f"{q} Q0 {d} {r} {1001-r} top5-check\n" for q, ds in rankings.items() for r, d in enumerate(ds[:5], 1)))
    configure_java()
    java = str(Path(os.environ["JAVA_HOME"]) / "bin/java") if os.environ.get("JAVA_HOME") else "java"
    jars = [p for p in importlib.resources.files("pyserini.resources.jars").iterdir() if p.name.endswith(".jar")]
    if len(jars) != 1:
        raise ValueError("Expected a single installed evaluator JAR")
    result = subprocess.run([java, "-cp", str(jars[0]), "trec_eval", "-q", "-c", "-m", "ndcg_cut.5", "-m", "P.5",
                             str(labels), str(run)], check=True, capture_output=True, text=True)
    (folder / f"{name}.trec_eval.txt").write_text(result.stdout)
    observed = {(q, m): float(v) for m, q, v in (line.split() for line in result.stdout.splitlines())}
    checked, max_error = 0, 0.0
    aggregate = {key: sum(row[key] for row in metrics.values()) / len(metrics) for key in ("ndcg_at_5", "precision_at_5")}
    for qid, row in {**metrics, "all": aggregate}.items():
        for ours, theirs in (("ndcg_at_5", "ndcg_cut_5"), ("precision_at_5", "P_5")):
            if (qid, theirs) not in observed:
                if qid != "all" and not rankings[qid] and row[ours] == 0:
                    continue
                raise ValueError(f"Native evaluator omitted {qid}/{theirs}")
            error = abs(row[ours] - observed[qid, theirs])
            if error > .000051:
                raise ValueError(f"Native top-five disagreement: {name}/{qid}/{ours}")
            checked, max_error = checked + 1, max(max_error, error)
    return {"status": "passed", "comparisons": checked, "max_absolute_difference": max_error,
            "measures": ["ndcg_cut_5", "P_5"], "gain_mode": gain_mode,
            "policy": "Only top-five metrics; ordinal scores preserve published order; zero-positive topics retained"}


def uncertainty_bounds(qrels, rankings, assessments):
    """Extreme bounds when every medium-confidence grade can independently be 0/1/2.

    These are robustness scenarios, not new labels or probabilistic intervals.
    """
    report = {}
    for qid, labels in qrels.items():
        uncertain = [r["doc_id"] for r in assessments if r["query_id"] == qid and r["confidence"] == "medium"]
        if len(uncertain) > 8:
            raise ValueError("Too many uncertain grades for exhaustive bounds; choose a specified sampling protocol")
        differences = []
        for grades in itertools.product((0, 1, 2), repeat=len(uncertain)):
            alternative = {**labels, **dict(zip(uncertain, grades, strict=True))}
            scores = {e: evaluate_query(ranks[qid], alternative)["ndcg_at_5"] for e, ranks in rankings.items()}
            differences.append(scores["dense"] - scores["bm25"])
        lo, hi = min(differences), max(differences)
        report[qid] = {"medium_confidence_pairs": len(uncertain), "scenarios": len(differences),
                       "minimum_dense_minus_bm25": lo, "maximum_dense_minus_bm25": hi,
                       "winner_stable": "dense" if lo > 1e-12 else "bm25" if hi < -1e-12 else "not_strictly_stable"}
    return {"interpretation": "Extreme grade-uncertainty scenarios, not confidence intervals or adjudicated relevance labels",
            "per_query": report,
            "macro_difference_bounds": [sum(r[key] for r in report.values()) / len(report)
                                        for key in ("minimum_dense_minus_bm25", "maximum_dense_minus_bm25")]}


def evaluate_top5_study(pool_dir, assessments_path, output, *, samples=10000, seed=20261025):
    import numpy as np

    if type(samples) is not int or samples < 1:
        raise ValueError("Bootstrap samples must be positive")
    target, pool = Path(output).resolve(), Path(pool_dir)
    if target.exists():
        raise FileExistsError("Custom evaluation exists; choose a new directory")
    validated = validate_assessments(pool, assessments_path)
    queries = list(map(json.loads, (pool / "queries.jsonl").read_text().splitlines()))
    qids = [q["_id"] for q in queries]
    if set(validated["complete_top5_query_ids"]) != set(qids):
        raise ValueError("Full-suite analysis requires every query's complete top-five union")
    if validated["assessed_pairs"] != validated["priority_top5_pairs"]:
        raise ValueError("This version requires exactly the top-five union; use a separate deeper-pool analysis")
    protocol = json.loads((pool / "protocol.json").read_text())
    for component in protocol["runs"].values():
        root = Path(component["path"])
        if sha256_file(root / "manifest.json") != component["manifest_sha256"]:
            raise ValueError("Frozen component manifest changed")
        manifest = json.loads((root / "manifest.json").read_text())
        if (manifest["corpus_sha256"] != protocol["corpus_sha256"]
                or manifest["query_source_sha256"] != protocol["query_source_sha256"]):
            raise ValueError("Frozen run corpus/query identity changed")
        for file, key in (("run.trec", "run_sha256"), ("results.jsonl", "results_sha256"), ("queries.jsonl", "query_snapshot_sha256")):
            if sha256_file(root / file) != manifest[key]:
                raise ValueError(f"Component run file changed: {file}")
    provenance = list(map(json.loads, (pool / "pool.provenance.jsonl").read_text().splitlines()))
    rankings = {e: {q: [d for _, d in sorted((r["component_ranks"][e], r["doc_id"]) for r in provenance
                                            if r["query_id"] == q and e in r["component_ranks"]
                                            and r["component_ranks"][e] <= 5)] for q in qids} for e in ("bm25", "dense")}
    qrels = {qid: validated["qrels"].get(qid, {}) for qid in qids}
    if any(not labels for labels in qrels.values()):
        raise ValueError("Each query needs an explicit assessed candidate set")
    assessments_hash = sha256_file(assessments_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.evaluating-", dir=target.parent))
    try:
        primary = assessed_top5_metrics(pool, assessments_path)
        checks = {}
        for mode in ("linear", "exp2"):
            checks[mode] = {}
            for engine, ranked in rankings.items():
                measured = {q: evaluate_query(ds, qrels[q], gain_mode=mode) for q, ds in ranked.items()}
                checks[mode][engine] = crosscheck_top5(qrels, ranked, measured, working / "crosscheck",
                                                      name=f"{mode}-{engine}", gain_mode=mode)
        primary["scope"] = "All custom queries; complete top-five union only; depth-20 pool incomplete"
        primary["zero_positive_queries_in_assessed_pool"] = [q for q, ds in qrels.items() if not any(ds.values())]
        primary["zero_positive_policy"] = "Retain these queries with nDCG/P equal to zero; no claim of no relevant articles in the corpus"
        primary["by_category"] = {}
        for category in dict.fromkeys(q["category"] for q in queries):
            ids = [q["_id"] for q in queries if q["category"] == category]
            primary["by_category"][category] = {"query_ids": ids, "query_count": len(ids), **{
                e: {m: sum(primary["per_query"][q][e][m] for q in ids) / len(ids)
                    for m in ("ndcg_at_5", "precision_at_5", "judged_at_5")} for e in rankings}}
        differences = np.array([primary["per_query"][q]["dense"]["ndcg_at_5"] - primary["per_query"][q]["bm25"]["ndcg_at_5"] for q in qids])
        draws = np.random.default_rng(seed).integers(0, len(qids), size=(samples, len(qids)))
        paired = {"direction": "dense minus bm25", "metric": "ndcg_at_5", "mean_difference": float(differences.mean()),
                  "paired_bootstrap_95_percentile_ci": np.quantile(differences[draws].mean(axis=1), [.025, .975]).tolist(),
                  "dense_wins": int((differences > 1e-12).sum()), "bm25_wins": int((differences < -1e-12).sum()),
                  "ties": int((abs(differences) <= 1e-12).sum()), "samples": samples, "seed": seed,
                  "interpretation": "Descriptive query bootstrap on a small AI-assessed suite; related needs and shared documents limit independence"}
        assessments = list(map(json.loads, Path(assessments_path).read_text().splitlines()))
        sensitivity = uncertainty_bounds(qrels, rankings, assessments)
        write_jsonl(working / "qrels.top5.jsonl", [{"query-id": q, "corpus-id": d, "score": g} for q, ds in qrels.items() for d, g in ds.items()])
        for name, value in (("metrics.json", primary), ("paired_comparison.json", paired),
                            ("crosscheck.json", checks), ("grade_uncertainty.json", sensitivity),
                            ("validation.json", {k: v for k, v in validated.items() if k != "qrels"})):
            (working / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        import csv
        with (working / "per_query.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["query_id", "category", "query", "known_pool_positives",
                                     "bm25_ndcg_at_5", "dense_ndcg_at_5", "bm25_precision_at_5", "dense_precision_at_5"])
            writer.writeheader()
            for q in queries:
                writer.writerow({"query_id": q["_id"], "category": q["category"], "query": q["text"],
                                 "known_pool_positives": sum(g > 0 for g in qrels[q["_id"]].values()),
                                 **{f"{e}_{m}": primary["per_query"][q["_id"]][e][m] for e in rankings
                                    for m in ("ndcg_at_5", "precision_at_5")}})
        if sha256_file(assessments_path) != assessments_hash:
            raise ValueError("Assessments changed during evaluation")
        manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "query_count": len(qids),
                    "assessment_pairs": len(assessments), "assessor_type": "AI", "judgment_scope": "top-five union only",
                    "protocol_sha256": sha256_file(pool / "protocol.json"), "assessments_sha256": assessments_hash,
                    "query_source_sha256": protocol["query_source_sha256"], "corpus_sha256": protocol["corpus_sha256"],
                    "independent_metric_comparisons": sum(c["comparisons"] for v in checks.values() for c in v.values()),
                    "map_status": "Withheld until depth-20 pool is complete",
                    "files": {p.name: sha256_file(p) for p in working.iterdir() if p.is_file()}}
        (working / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        working.rename(target)
        return {"output": str(target), "query_count": len(qids), "top5_assessed_pairs": len(assessments),
                "aggregate": primary["macro_over_completed_queries_only"], "paired": paired,
                "independent_metric_comparisons": manifest["independent_metric_comparisons"],
                "zero_positive_queries_in_assessed_pool": primary["zero_positive_queries_in_assessed_pool"],
                "grade_uncertainty_macro_bounds": sensitivity["macro_difference_bounds"]}
    except BaseException:
        shutil.rmtree(working)
        raise
