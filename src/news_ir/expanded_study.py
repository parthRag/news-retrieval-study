"""Join disjoint frozen query runs and compare dependent query families.

Joining preserves every source hit and score. It is an export operation, not
another retrieval experiment, and never invents a combined latency measurement.
"""
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .assessment import write_jsonl
from .data import read_queries, sha256_file
from .evaluation import load_run


def _configuration(manifest):
    config = manifest["retrieval_config"]
    if manifest["engine"] == "e5-cosine":
        return {"model": config["model"]}
    return {"bm25": config, "analyzer": manifest.get("analyzer")}


def join_saved_runs(queries_path, components, index_dir, eligible_ids, output):
    """Validate and concatenate nonoverlapping runs in the requested query order."""
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError("Joined run exists; choose a new version")
    queries = read_queries(queries_path)
    source_hashes, rows, sources, reference = {}, {}, [], None
    for source_queries, run_dir in components:
        root = Path(run_dir).resolve()
        manifest_path = root / "manifest.json"
        before = sha256_file(manifest_path)
        manifest = json.loads(manifest_path.read_text())
        _, manifest = load_run(root, source_queries, eligible_ids,
                               expected_source_sha256=manifest["corpus_sha256"])
        identity = (manifest["engine"], manifest["corpus_sha256"],
                    manifest["index_manifest_sha256"], _configuration(manifest))
        if reference is not None and identity != reference:
            raise ValueError("Source runs differ in engine, corpus, index or retrieval configuration")
        reference = identity
        for row in map(json.loads, (root / "results.jsonl").read_text().splitlines()):
            if row["query_id"] in rows:
                raise ValueError("Query IDs overlap between component runs")
            rows[row["query_id"]] = row
        sources.append({"path": str(root), "manifest_sha256": before,
                        "query_source_sha256": manifest["query_source_sha256"],
                        "query_count": manifest["query_count"], "run_sha256": manifest["run_sha256"],
                        "runtime": manifest["retrieval_config"].get("runtime", {})})
        for path in [Path(source_queries), manifest_path, root / "results.jsonl", root / "run.trec", root / "queries.jsonl"]:
            source_hashes[str(path.resolve())] = sha256_file(path)
        if sha256_file(manifest_path) != before:
            raise ValueError("Source manifest changed during validation")
    if not sources or set(rows) != {q["_id"] for q in queries}:
        raise ValueError("Source runs must cover exactly the requested query IDs")
    if any(rows[q["_id"]]["query"] != q["text"] for q in queries):
        raise ValueError("Requested query text differs from source rankings")
    index = Path(index_dir).resolve()
    if sha256_file(index / "manifest.json") != reference[2]:
        raise ValueError("Local index differs from the frozen component index")
    source_hashes[str(Path(queries_path).resolve())] = sha256_file(queries_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix=f".{target.name}.joining-", dir=target.parent))
    try:
        ordered = [rows[q["_id"]] for q in queries]
        write_jsonl(working / "results.jsonl", ordered)
        write_jsonl(working / "queries.jsonl", queries)
        tag = "joined-custom40"
        with (working / "run.trec").open("w") as stream:
            for row in ordered:
                for hit in row["hits"]:
                    stream.write(f"{row['query_id']} Q0 {hit['doc_id']} {hit['rank']} {hit['score']:.9g} {tag}\n")
        manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "engine": reference[0], "run_tag": tag, "coverage": "full", "top_k": 1000,
                    "index_path": str(index), "index_manifest_sha256": reference[2],
                    "corpus_sha256": reference[1], "retrieval_config": reference[3].get("bm25", reference[3]),
                    "query_source_sha256": sha256_file(queries_path), "query_count": len(queries),
                    "total_hits": sum(len(row["hits"]) for row in ordered),
                    "derivation": "Concatenated immutable disjoint-query runs; hit IDs, ranks and scores preserved; no new retrieval",
                    "latency_protocol": "No combined timing measurement; per-query timings belong to source runtime environments",
                    "components": sources, "source_hashes": source_hashes,
                    **{key: sha256_file(working / name) for name, key in
                       [("queries.jsonl", "query_snapshot_sha256"), ("results.jsonl", "results_sha256"),
                        ("run.trec", "run_sha256")]}}
        if reference[0] == "lucene-bm25":
            manifest["analyzer"] = reference[3]["analyzer"]
        (working / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        load_run(working, queries_path, eligible_ids, expected_source_sha256=reference[1])
        if any(sha256_file(path) != digest for path, digest in source_hashes.items()):
            raise ValueError("Source bytes changed while joining runs")
        working.rename(target)
        return manifest
    except BaseException:
        shutil.rmtree(working)
        raise


def clustered_comparison(first, second, families, *, samples=10000, seed=20261025):
    """Paired cluster bootstrap of the query-weighted mean (ratio of sums).

    Resample families, carrying all their queries together. Unequal family sizes
    must affect both numerator and denominator; averaging family means instead
    would change the estimand from the ordinary query-macro difference.
    """
    if type(samples) is not int or samples < 1:
        raise ValueError("Bootstrap samples must be positive")
    qids = list(first["per_query"])
    if not qids or set(qids) != set(second["per_query"]) or set(qids) != set(families):
        raise ValueError("Both systems and family mapping must have identical nonempty query sets")
    if any(not isinstance(families[q], str) or not families[q].strip() for q in qids):
        raise ValueError("Every query needs a nonempty family name")
    groups = list(dict.fromkeys(families[q] for q in qids))
    positions = [[i for i, q in enumerate(qids) if families[q] == family] for family in groups]
    sizes = np.array([len(p) for p in positions])
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(groups), size=(samples, len(groups)))
    metrics = {}
    for metric in ["ndcg_at_5", "ap_at_1000"]:
        delta = np.array([second["per_query"][q][metric] - first["per_query"][q][metric] for q in qids])
        sums = np.array([delta[p].sum() for p in positions])
        estimates = sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)
        metrics[metric] = {"mean_dense_minus_bm25": float(delta.mean()),
                           "cluster_bootstrap_95_percentile_ci": np.quantile(estimates, [.025, .975]).tolist()}
    return {"query_count": len(qids), "family_count": len(groups), "families": families,
            "samples": samples, "seed": seed, "metrics": metrics,
            "interpretation": "Descriptive paired-family resampling; query-weighted mean; not label-accuracy intervals or proof of independent families"}
