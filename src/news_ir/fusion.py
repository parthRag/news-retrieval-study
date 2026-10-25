"""Fixed reciprocal-rank fusion of validated saved full-corpus runs."""

import json
import platform
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .data import DocumentStore, read_queries, sha256_file
from .evaluation import load_run


def reciprocal_rank_fusion(rankings, *, k=60, depth=1000):
    """One contribution per component/document, with deterministic ID tie breaks."""
    if type(k) is not int or k < 1 or type(depth) is not int or depth < 1:
        raise ValueError("k and depth must be positive integers")
    if len(rankings) < 2:
        raise ValueError("Fusion requires at least two component rankings")
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, doc_id in enumerate(ranking, 1):
            if doc_id in seen:
                raise ValueError("Duplicate document in component ranking")
            seen.add(doc_id)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (k + rank)
    return [{"doc_id": doc_id, "rank": rank, "score": score}
            for rank, (doc_id, score) in enumerate(
                sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:depth], 1)]


def fuse_runs(*, queries_path, bm25_run, dense_run, document_index, output, k=60):
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError("Fusion output exists; choose a new directory")
    with DocumentStore(document_index) as store:
        source_hash = store.manifest["source"]["sha256"]
        eligible = {row[0] for row in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
    components = {}
    for name, path, engine in (("bm25", bm25_run, "lucene-bm25"), ("dense", dense_run, "e5-cosine")):
        rankings, manifest = load_run(path, queries_path, eligible, expected_source_sha256=source_hash)
        if manifest["engine"] != engine:
            raise ValueError("Fusion component engine arguments are swapped or incorrect")
        index_manifest = Path(manifest["index_path"]) / "manifest.json"
        if sha256_file(index_manifest) != manifest["index_manifest_sha256"]:
            raise ValueError("Component index manifest changed since retrieval")
        metadata = json.loads(index_manifest.read_text())
        count = metadata["documents"]["indexed"] if name == "bm25" else metadata["indexed_documents"]
        if count != len(eligible):
            raise ValueError("Component index does not cover the shared eligible corpus")
        components[name] = (rankings, manifest, Path(path))
    queries = read_queries(queries_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.fusing-", dir=target.parent))
    try:
        total, elapsed = 0, []
        with (working / "run.trec").open("w") as trec, (working / "results.jsonl").open("w") as results:
            for query in queries:
                started = time.perf_counter()
                hits = reciprocal_rank_fusion([value[0][query["_id"]] for value in components.values()], k=k)
                duration = (time.perf_counter() - started) * 1000
                elapsed.append(duration)
                total += len(hits)
                for hit in hits:
                    trec.write(f"{query['_id']} Q0 {hit['doc_id']} {hit['rank']} {hit['score']:.9g} rrf-k{k}\n")
                results.write(json.dumps({"query_id": query["_id"], "query": query["text"],
                                          "latency_ms": duration, "analyzed_terms": None, "hits": hits},
                                         ensure_ascii=False) + "\n")
        shutil.copyfile(next(iter(components.values()))[2] / "queries.jsonl", working / "queries.jsonl")
        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "engine": "rrf", "run_tag": f"rrf-k{k}",
            "coverage": "full", "corpus_sha256": source_hash, "eligible_documents": len(eligible),
            "query_source_sha256": sha256_file(queries_path), "query_count": len(queries),
            "top_k": 1000, "total_hits": total, "runtime_python": platform.python_version(),
            "retrieval_config": {"k": k, "component_depth": 1000, "weights": [1, 1],
                                 "tie_break": "ascending document ID", "tuning": "none"},
            "components": {name: {"path": str(path.resolve()), "manifest_sha256": sha256_file(path / "manifest.json"),
                                   "run_sha256": meta["run_sha256"], "engine": meta["engine"]}
                           for name, (_, meta, path) in components.items()},
            "latency_ms": {"mean": sum(elapsed) / len(elapsed), "min": min(elapsed), "max": max(elapsed)},
            "latency_protocol": "Fusion computation over saved rankings only; excludes both engine searches, file loading and startup",
            "evaluation": f"No relevance labels used in fusion; k={k} (default 60), not fitted by this command",
            **{key: sha256_file(working / filename) for filename, key in
               (("run.trec", "run_sha256"), ("results.jsonl", "results_sha256"), ("queries.jsonl", "query_snapshot_sha256"))},
        }
        # Bind the output to the same inputs that passed validation.
        if any(sha256_file(path / "manifest.json") != manifest["components"][name]["manifest_sha256"]
               or sha256_file(path / "run.trec") != meta["run_sha256"]
               or sha256_file(queries_path) != meta["query_source_sha256"]
               for name, (_, meta, path) in components.items()):
            raise ValueError("Fusion inputs changed during computation")
        (working / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        load_run(working, queries_path, eligible, expected_source_sha256=source_hash)
        working.rename(target)
        return manifest
    except BaseException:
        shutil.rmtree(working)
        raise


def evaluate_fusion(*, queries_path, qrels_path, bm25_run, dense_run, fusion_run, document_index, output,
                    samples=10000, seed=20261025):
    """Evaluate all three runs; independently cross-check every hybrid metric."""
    import csv
    import numpy as np

    from .benchmark import crosscheck, write_json
    from .evaluation import METRICS, evaluate_rankings, load_qrels

    if type(samples) is not int or samples < 1:
        raise ValueError("Bootstrap samples must be positive")
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError("Fusion evaluation exists; choose a new directory")
    queries = read_queries(queries_path)
    qrels_hash, queries_hash = sha256_file(qrels_path), sha256_file(queries_path)
    qrels = load_qrels(qrels_path, [q["_id"] for q in queries])
    with DocumentStore(document_index) as store:
        source_hash = store.manifest["source"]["sha256"]
        eligible = {row[0] for row in store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
    runs, metas = {}, {}
    paths = {"bm25": Path(bm25_run), "dense": Path(dense_run), "rrf": Path(fusion_run)}
    for name, engine in (("bm25", "lucene-bm25"), ("dense", "e5-cosine"), ("rrf", "rrf")):
        runs[name], metas[name] = load_run(paths[name], queries_path, eligible, expected_source_sha256=source_hash)
        if metas[name]["engine"] != engine:
            raise ValueError("Evaluation run engine arguments are incorrect")
    for name in ("bm25", "dense"):
        component = metas["rrf"]["components"][name]
        if (component["manifest_sha256"] != sha256_file(paths[name] / "manifest.json")
                or component["run_sha256"] != metas[name]["run_sha256"]):
            raise ValueError("Evaluated baselines differ from fusion components")
    available = {q: {d: g for d, g in labels.items() if d in eligible} for q, labels in qrels.items()}
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.evaluating-", dir=target.parent))
    try:
        evaluations, checks = {}, {}
        for policy, labels, mode in (("primary", qrels, "linear"), ("exp2_gain", qrels, "exp2"),
                                     ("news2019_gain", qrels, "news2019"), ("available_corpus", available, "linear")):
            evaluations[policy] = {name: evaluate_rankings(run, labels, gain_mode=mode) for name, run in runs.items()}
            checks[policy] = crosscheck(labels, runs["rrf"], evaluations[policy]["rrf"], working / "crosscheck",
                                        name=f"{policy}-rrf", gain_mode=mode)
        primary, paired = evaluations["primary"], {}
        qids = [q["_id"] for q in queries]
        draws = np.random.default_rng(seed).integers(0, len(qids), size=(samples, len(qids)))
        for baseline in ("bm25", "dense"):
            paired[baseline] = {}
            for metric in ("ndcg_at_5", "ap_at_1000"):
                delta = np.array([primary["rrf"]["per_query"][q][metric] - primary[baseline]["per_query"][q][metric]
                                  for q in qids])
                paired[baseline][metric] = {
                    "direction": f"rrf minus {baseline}", "mean_difference": float(delta.mean()),
                    "paired_bootstrap_95_percentile_ci": np.quantile(delta[draws].mean(axis=1), [.025, .975]).tolist(),
                    "rrf_wins": int((delta > 1e-12).sum()), "baseline_wins": int((delta < -1e-12).sum()),
                    "ties": int((abs(delta) <= 1e-12).sum()),
                }
        write_json(working / "metrics.json", evaluations)
        write_json(working / "paired_comparison.json", {"samples": samples, "seed": seed,
                   "interpretation": "Descriptive paired query bootstrap; exploratory third-system comparison", "comparisons": paired})
        write_json(working / "crosscheck.json", checks)
        with (working / "per_query.csv").open("w", newline="") as stream:
            columns = ["query_id", "query"] + [f"{e}_{m}" for e in runs for m in METRICS]
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for query in queries:
                writer.writerow({"query_id": query["_id"], "query": query["text"],
                                 **{f"{e}_{m}": primary[e]["per_query"][query["_id"]][m] for e in runs for m in METRICS}})
        for name, path in paths.items():
            if sha256_file(path / "run.trec") != metas[name]["run_sha256"]:
                raise ValueError("Run changed during evaluation")
        if sha256_file(qrels_path) != qrels_hash or sha256_file(queries_path) != queries_hash:
            raise ValueError("Evaluation inputs changed during computation")
        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "query_count": len(queries),
            "corpus_sha256": source_hash, "queries_sha256": queries_hash, "qrels_sha256": qrels_hash,
            "bootstrap_samples": samples, "seed": seed, "independent_crosscheck": "passed for RRF under all four policies",
            "policy": "Same original-57 policies: linear primary gains, exp2/NIST sensitivity, available-corpus sensitivity; grade>0 binary AP; unjudged retained at zero contribution; all known positives in AP denominator",
            "scope": "Original benchmark only; no custom AI labels used; fixed RRF k, no parameter search",
            "runs": {name: {"path": str(path.resolve()), "manifest_sha256": sha256_file(path / "manifest.json"),
                            "run_sha256": metas[name]["run_sha256"]} for name, path in paths.items()},
            "files": {p.name: sha256_file(p) for p in working.iterdir() if p.is_file()},
        }
        write_json(working / "manifest.json", manifest)
        working.rename(target)
        return {"output": str(target), "primary": {name: values["aggregate"] for name, values in primary.items()},
                "paired": paired, "independent_comparisons": sum(c["comparisons"] for c in checks.values())}
    except BaseException:
        shutil.rmtree(working)
        raise
