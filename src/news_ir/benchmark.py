"""Versioned comparison of full-corpus ranked runs against supplied qrels."""

import csv
import importlib.resources
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .data import DocumentStore, read_queries, sha256_file
from .evaluation import METRICS, evaluate_rankings, gain, load_qrels, load_run, paired_comparison


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def crosscheck(qrels, rankings, evaluation, folder, *, name, gain_mode="linear"):
    """Compare every per-topic/aggregate measure to the independent native evaluator.

    trec_eval ignores the supplied rank and breaks equal score ties differently.
    Integer ordinal scores in a DERIVED file preserve our published ranking.
    Original model scores and source run files remain untouched.
    """
    from .runtime import configure_java

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    qrels_path, run_path = folder / f"{name}.qrels", folder / f"{name}.run"
    with qrels_path.open("w") as stream:
        for qid, judgments in qrels.items():
            for doc_id, grade in judgments.items():
                stream.write(f"{qid} 0 {doc_id} {gain(grade, gain_mode)}\n")
    with run_path.open("w") as stream:
        for qid, ids in rankings.items():
            for rank, doc_id in enumerate(ids, 1):
                stream.write(f"{qid} Q0 {doc_id} {rank} {1001-rank} rank-order-check\n")
    configure_java()
    java = str(Path(os.environ["JAVA_HOME"]) / "bin/java") if os.environ.get("JAVA_HOME") else "java"
    jars = [p for p in importlib.resources.files("pyserini.resources.jars").iterdir() if p.name.endswith(".jar")]
    if len(jars) != 1:
        raise ValueError("Expected the single installed Anserini evaluator JAR")
    jar = jars[0]
    command = [java, "-cp", str(jar), "trec_eval", "-q", "-c", "-m", "ndcg_cut.5,10",
               "-m", "map_cut.1000", "-m", "recall.1000", "-m", "P.5,10", "-m", "recip_rank",
               str(qrels_path), str(run_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    (folder / f"{name}.trec_eval.txt").write_text(result.stdout)
    observed = {}
    for line in result.stdout.splitlines():
        metric, qid, value = line.split()
        observed[(qid, metric)] = float(value)
    mapping = {"ndcg_at_5": "ndcg_cut_5", "ndcg_at_10": "ndcg_cut_10", "ap_at_1000": "map_cut_1000",
               "recall_at_1000": "recall_1000", "precision_at_5": "P_5", "precision_at_10": "P_10",
               "reciprocal_rank_at_1000": "recip_rank"}
    comparisons, maximum, omitted_empty = 0, 0.0, 0
    for qid, values in {**evaluation["per_query"], "all": evaluation["aggregate"]}.items():
        for ours, theirs in mapping.items():
            if (qid, theirs) not in observed:
                # Native trec_eval -c includes empty topics in the macro denominator
                # but does not print their per-topic rows. Require zero explicitly;
                # the native aggregate below still independently checks inclusion.
                if qid != "all" and not rankings[qid] and values[ours] == 0:
                    omitted_empty += 1
                    continue
                raise ValueError(f"trec_eval omitted query/metric {qid}/{theirs}")
            difference = abs(values[ours] - observed[(qid, theirs)])
            if difference > 0.000051:
                raise ValueError(f"Independent evaluator disagreement for {name}/{qid}/{ours}: {difference}")
            maximum = max(maximum, difference)
            comparisons += 1
    version = subprocess.run([java, "-cp", str(jar), "trec_eval", "-v"], capture_output=True, text=True, check=True)
    return {"status": "passed", "comparisons": comparisons, "max_absolute_difference": maximum,
            "empty_query_zero_metrics_checked": omitted_empty,
            "tolerance": 0.000051, "precision_note": "trec_eval prints four decimal places",
            "ranking_policy": "Derived scores 1001-rank preserve original published order, including score ties",
            "version": (version.stdout + version.stderr).strip()}


def compare_benchmark(*, queries_path, qrels_path, bm25_run, dense_run, document_index, output,
                      bootstrap_samples=10000, seed=20261024):
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError("Evaluation output exists; choose a new directory")
    queries = read_queries(queries_path)
    qrels = load_qrels(qrels_path, [q["_id"] for q in queries])
    qrels_hash, queries_hash = sha256_file(qrels_path), sha256_file(queries_path)
    with DocumentStore(document_index) as store:
        source_hash = store.manifest["source"]["sha256"]
        eligible = {row[0] for row in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
        source_ids = {row[0] for row in store._db.execute("SELECT doc_id FROM documents")}
    bm25, bm_manifest = load_run(bm25_run, queries_path, eligible, expected_source_sha256=source_hash)
    dense, dense_manifest = load_run(dense_run, queries_path, eligible, expected_source_sha256=source_hash)
    if bm_manifest["engine"] != "lucene-bm25" or dense_manifest["engine"] != "e5-cosine":
        raise ValueError("Engine run arguments are swapped or incorrect")
    for manifest in (bm_manifest, dense_manifest):
        index_manifest = Path(manifest["index_path"]) / "manifest.json"
        if sha256_file(index_manifest) != manifest["index_manifest_sha256"]:
            raise ValueError("Index manifest changed since retrieval")
        metadata = json.loads(index_manifest.read_text())
        count = metadata["documents"]["indexed"] if manifest["engine"] == "lucene-bm25" else metadata["indexed_documents"]
        if count != len(eligible):
            raise ValueError("Ranked index does not cover the complete shared eligible corpus")
    unavailable = [{"query_id": qid, "doc_id": doc_id, "grade": grade,
                    "reason": "absent_from_source" if doc_id not in source_ids else "excluded_empty"}
                   for qid, judgments in qrels.items() for doc_id, grade in judgments.items() if doc_id not in eligible]
    available_qrels = {qid: {doc_id: grade for doc_id, grade in judgments.items() if doc_id in eligible}
                       for qid, judgments in qrels.items()}
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.evaluating-", dir=target.parent))
    try:
        evaluations, checks = {}, {}
        for policy, labels, mode in (("primary", qrels, "linear"), ("exp2_gain", qrels, "exp2"),
                                     ("news2019_gain", qrels, "news2019"),
                                     ("available_corpus", available_qrels, "linear")):
            evaluations[policy], checks[policy] = {}, {}
            for engine, rankings in (("bm25", bm25), ("dense", dense)):
                evaluated = evaluate_rankings(rankings, labels, gain_mode=mode)
                evaluations[policy][engine] = evaluated
                checks[policy][engine] = crosscheck(labels, rankings, evaluated, working / "crosscheck",
                                                   name=f"{policy}-{engine}", gain_mode=mode)
        paired = paired_comparison(evaluations["primary"]["bm25"], evaluations["primary"]["dense"],
                                   samples=bootstrap_samples, seed=seed)
        write_json(working / "metrics.json", evaluations)
        write_json(working / "paired_comparison.json", paired)
        write_json(working / "crosscheck.json", checks)
        write_json(working / "unavailable_judgments.json", unavailable)
        columns = ["query_id", "query", "known_relevant", "unavailable_relevant"]
        columns += [f"{engine}_{metric}" for engine in ("bm25", "dense") for metric in METRICS]
        columns += ["delta_ndcg_at_5", "delta_ap_at_1000"]
        with (working / "per_query.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for query in queries:
                qid = query["_id"]
                bm = evaluations["primary"]["bm25"]["per_query"][qid]
                de = evaluations["primary"]["dense"]["per_query"][qid]
                row = {"query_id": qid, "query": query["text"], "known_relevant": bm["known_relevant"],
                       "unavailable_relevant": sum(j["query_id"] == qid and j["grade"] > 0 for j in unavailable)}
                row.update({f"{engine}_{metric}": values[metric]
                            for engine, values in (("bm25", bm), ("dense", de)) for metric in METRICS})
                row.update(delta_ndcg_at_5=de["ndcg_at_5"] - bm["ndcg_at_5"],
                           delta_ap_at_1000=de["ap_at_1000"] - bm["ap_at_1000"])
                writer.writerow(row)
        policy = {
            "primary_gain": "supplied relevance grade (linear), following BEIR/trec_eval ndcg_cut",
            "exp2_sensitivity_gain": "2^grade - 1; same positive/nonpositive distinction for AP",
            "news2019_sensitivity_gain": "zero for grade 0, else 2^grade; matches original NIST gain-valued qrels",
            "binary_relevance": "grade > 0", "unjudged": "zero contribution; retain positions; not a claim of irrelevance",
            "missing_documents": "original qrels retained in primary AP denominators and nDCG ideal ranking",
            "available_corpus_sensitivity": "same runs; remove only unavailable judgments from denominators/IDCG",
            "zero_relevant_queries": "retain with zero scores", "average": "macro over all supplied queries",
            "retrieval_depth": 1000, "map_label": "MAP@1000: mean AP of depth-1000 runs, denominator is all known positives",
            "ranking_ties": "evaluate published rank order; derived ordinal-score run used only for independent cross-check",
            "filters": "no date filtering or inferred source-article exclusion; no tuning on qrels",
        }
        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "query_count": len(queries),
            "eligible_documents": len(eligible), "corpus_sha256": source_hash,
            "queries_sha256": queries_hash, "qrels_sha256": qrels_hash,
            "judgment_count": sum(len(j) for j in qrels.values()),
            "grade_distribution": dict(sorted(Counter(g for j in qrels.values() for g in j.values()).items())),
            "unavailable_judgments": len(unavailable),
            "unavailable_positive_judgments": sum(j["grade"] > 0 for j in unavailable),
            "unavailable_unique_documents": len({j["doc_id"] for j in unavailable}),
            "unavailable_grade_distribution": dict(sorted(Counter(j["grade"] for j in unavailable).items())),
            "policies": policy, "independent_crosscheck": "passed", "paired_comparison": paired,
            "runs": {engine: {"path": str(Path(path).resolve()), "manifest_sha256": sha256_file(Path(path) / "manifest.json"),
                              "run_sha256": meta["run_sha256"], "total_hits": meta["total_hits"],
                              "runtime_python": meta["runtime_python"], "latency_ms": meta["latency_ms"]}
                     for engine, path, meta in (("bm25", bm25_run, bm_manifest), ("dense", dense_run, dense_manifest))},
            "files": {p.name: sha256_file(p) for p in working.iterdir() if p.is_file()},
            "scope": "Original headline/background-linking queries; separate from the unjudged 20 custom challenges",
        }
        if sha256_file(qrels_path) != qrels_hash or sha256_file(queries_path) != queries_hash:
            raise ValueError("Evaluation inputs changed during computation")
        write_json(working / "manifest.json", manifest)
        working.rename(target)
        return {"output": str(target), "query_count": len(queries), "primary": {
            engine: evaluation["aggregate"] for engine, evaluation in evaluations["primary"].items()},
                "independent_crosscheck": "passed", "paired_comparison": paired}
    except BaseException:
        shutil.rmtree(working)
        raise
