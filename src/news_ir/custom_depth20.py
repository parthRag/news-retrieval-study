"""Evaluate frozen custom runs only after completing their designated joint pool."""

import csv
import json
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .assessment import validate_assessments, write_jsonl
from .benchmark import crosscheck
from .data import DocumentStore, sha256_file
from .evaluation import METRICS, evaluate_rankings, load_run, paired_comparison


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_seed(assessments, seed):
    """Every earlier record must survive verbatim, including rationale and evidence."""
    lookup = {(r["query_id"], r["doc_id"]): r for r in assessments}
    if any(lookup.get((r["query_id"], r["doc_id"])) != r for r in seed):
        raise ValueError("Earlier top-five assessment changed or disappeared")


def check_pool(provenance, rankings, depth):
    """Reconstruct equal-depth membership, component ranks and top-five priority."""
    expected = {}
    for engine, run in rankings.items():
        for qid, ids in run.items():
            for rank, doc in enumerate(ids[:depth], 1):
                expected.setdefault((qid, doc), {})[engine] = rank
    observed = {}
    for row in provenance:
        pair = row["query_id"], row["doc_id"]
        if pair in observed or not row["component_ranks"]:
            raise ValueError("Duplicate or empty pool provenance")
        observed[pair] = row["component_ranks"]
        if row["priority_top5"] != any(r <= 5 for r in row["component_ranks"].values()):
            raise ValueError("Pool top-five priority does not match component ranks")
    if observed != expected:
        raise ValueError("Frozen pool differs from the equal-depth union of saved runs")


def evaluate_depth20_study(pool_dir, assessments_path, seed_path, document_index, output,
                           *, samples=10000, seed=20261025):
    pool, target = Path(pool_dir), Path(output).resolve()
    if target.exists():
        raise FileExistsError("Custom evaluation exists; choose a new directory")
    if type(samples) is not int or samples < 1:
        raise ValueError("Bootstrap samples must be positive")
    validated = validate_assessments(pool, assessments_path)
    if not validated["complete_pool"]:
        raise ValueError("Pooled MAP requires the complete designated pool")
    protocol = json.loads((pool / "protocol.json").read_text())
    queries = list(map(json.loads, (pool / "queries.jsonl").read_text().splitlines()))
    qids = [q["_id"] for q in queries]
    if (protocol["pool_depth_per_engine"] != 20 or protocol["query_count"] != len(qids)
            or protocol["pooled_pairs"] != validated["pooled_pairs"]
            or protocol["priority_top5_pairs"] != validated["priority_top5_pairs"]
            or set(validated["qrels"]) != set(qids)):
        raise ValueError("Protocol, complete labels and query coverage disagree")
    assessments = list(map(json.loads, Path(assessments_path).read_text().splitlines()))
    earlier = list(map(json.loads, Path(seed_path).read_text().splitlines()))
    check_seed(assessments, earlier)
    provenance = list(map(json.loads, (pool / "pool.provenance.jsonl").read_text().splitlines()))
    priority = {(r["query_id"], r["doc_id"]) for r in provenance if r["priority_top5"]}
    if {(r["query_id"], r["doc_id"]) for r in earlier} != priority:
        raise ValueError("Earlier labels must be exactly the frozen top-five union")
    # Bind all frozen source files and run bytes before computing any score.
    inputs = [Path(assessments_path), Path(seed_path), pool / "protocol.json"]
    inputs += [pool / name for name in protocol["files"]]
    with DocumentStore(document_index) as store:
        if store.manifest["source"]["sha256"] != protocol["corpus_sha256"]:
            raise ValueError("Corpus identity differs from the assessment protocol")
        eligible = {r[0] for r in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
    if len(eligible) != protocol["eligible_documents"]:
        raise ValueError("Shared eligible corpus count changed")
    rankings, run_metadata = {}, {}
    for engine, component in protocol["runs"].items():
        root = Path(component["path"])
        if sha256_file(root / "manifest.json") != component["manifest_sha256"]:
            raise ValueError("Frozen run manifest changed")
        ranked, meta = load_run(root, pool / "queries.jsonl", eligible,
                                expected_source_sha256=protocol["corpus_sha256"])
        if meta["engine"] != {"bm25": "lucene-bm25", "dense": "e5-cosine"}[engine]:
            raise ValueError("Frozen engine identity differs")
        if meta["run_sha256"] != component["run_sha256"]:
            raise ValueError("Frozen run identity differs")
        rankings[engine], run_metadata[engine] = ranked, component
        inputs += [root / f for f in ("manifest.json", "run.trec", "results.jsonl", "queries.jsonl")]
    if set(rankings) != {"bm25", "dense"}:
        raise ValueError("Both frozen baseline engines are required")
    check_pool(provenance, rankings, 20)
    hashes = {str(p.resolve()): sha256_file(p) for p in inputs}
    labels = {q: validated["qrels"][q] for q in qids}
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.evaluating-", dir=target.parent))
    try:
        metrics, checks = {}, {}
        for mode in ("linear", "exp2"):
            metrics[mode], checks[mode] = {}, {}
            for engine, ranked in rankings.items():
                result = evaluate_rankings(ranked, labels, gain_mode=mode)
                metrics[mode][engine] = result
                checks[mode][engine] = crosscheck(labels, ranked, result, working / "crosscheck",
                                                    name=f"{mode}-{engine}", gain_mode=mode)
        primary = metrics["linear"]
        paired = paired_comparison(primary["bm25"], primary["dense"], samples=samples, seed=seed)
        paired["interpretation"] = "Descriptive bootstrap of a small AI-assessed suite; related needs/shared documents limit query independence. Not label-accuracy intervals."
        categories = {}
        for category in dict.fromkeys(q["category"] for q in queries):
            ids = [q["_id"] for q in queries if q["category"] == category]
            categories[category] = {"query_ids": ids, "query_count": len(ids), **{
                e: {m: sum(primary[e]["per_query"][q][m] for q in ids) / len(ids) for m in METRICS}
                for e in rankings}}
        scenarios = {}
        for scenario in ("medium_as_zero", "grade2_only"):
            alternative = {q: dict(ds) for q, ds in labels.items()}
            for row in assessments:
                if (scenario == "medium_as_zero" and row["confidence"] == "medium"
                        or scenario == "grade2_only" and row["grade"] == 1):
                    alternative[row["query_id"]][row["doc_id"]] = 0
            scenarios[scenario] = {e: evaluate_rankings(r, alternative)["aggregate"] for e, r in rankings.items()}
        uncertainty = {"interpretation": "Specified sensitivity scenarios, not exhaustive bounds, new judgments, or confidence intervals. High-confidence AI judgments may also be wrong.",
                       "definitions": {"medium_as_zero": "Set every medium-confidence grade to zero, including existing zeros; retain all queries.",
                                       "grade2_only": "Treat limited-detail grade 1 as nonrelevant; keep grade 2 and all queries."},
                       "scenarios": scenarios}
        write_jsonl(working / "qrels.depth20.jsonl", [{"query-id": q, "corpus-id": d, "score": g}
                                                       for q, ds in labels.items() for d, g in ds.items()])
        for name, value in (("metrics.json", metrics), ("by_category.json", categories),
                            ("paired_comparison.json", paired), ("crosscheck.json", checks),
                            ("sensitivity.json", uncertainty),
                            ("validation.json", {k: v for k, v in validated.items() if k != "qrels"})):
            dump(working / name, value)
        columns = ["query_id", "category", "query", "known_pool_positives"]
        columns += [f"{e}_{m}" for e in rankings for m in METRICS]
        with (working / "per_query.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for query in queries:
                q = query["_id"]
                writer.writerow({"query_id": q, "category": query["category"], "query": query["text"],
                                 "known_pool_positives": sum(g > 0 for g in labels[q].values()),
                                 **{f"{e}_{m}": primary[e]["per_query"][q][m] for e in rankings for m in METRICS}})
        if any(sha256_file(path) != digest for path, digest in hashes.items()):
            raise ValueError("Frozen evaluation inputs changed during computation")
        manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "query_count": len(qids),
                    "assessment_pairs": len(assessments), "preserved_top5_pairs": len(earlier),
                    "assessor_type": "AI", "judgment_scope": "Complete union of both engines' top 20; saved runs evaluated to 1000",
                    "corpus_sha256": protocol["corpus_sha256"], "query_source_sha256": protocol["query_source_sha256"],
                    "assessments_sha256": sha256_file(assessments_path), "protocol_sha256": sha256_file(pool / "protocol.json"),
                    "grade_distribution": dict(Counter(r["grade"] for r in assessments)),
                    "confidence_distribution": dict(Counter(r["confidence"] for r in assessments)),
                    "runs": run_metadata, "input_hashes": hashes,
                    "independent_metric_comparisons": sum(c["comparisons"] for v in checks.values() for c in v.values()),
                    "policies": {"primary_gain": "linear 0,1,2", "gain_sensitivity": "exp2: 0,1,3",
                                 "binary_relevance": "grade > 0", "map": "Pooled MAP@1000; denominator is every known positive in the complete designated shallow pool, not all corpus positives",
                                 "unjudged": "Zero metric contribution at original rank; not confirmed irrelevant",
                                 "zero_positive": "Keep all queries in macro average with zero scores",
                                 "baseline": "Frozen queries, labels and rankings; no filtering, deduplication or tuning"},
                    "files": {str(p.relative_to(working)): sha256_file(p) for p in working.rglob("*") if p.is_file()}}
        dump(working / "manifest.json", manifest)
        working.rename(target)
        return {"output": str(target), "assessment_pairs": len(assessments),
                "aggregate": {e: v["aggregate"] for e, v in primary.items()},
                "paired": paired, "independent_metric_comparisons": manifest["independent_metric_comparisons"]}
    except BaseException:
        shutil.rmtree(working)
        raise
