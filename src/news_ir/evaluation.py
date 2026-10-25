"""Strict ranked-run evaluation with explicit gains and missing-qrel policies."""

import json
import math
import statistics
from pathlib import Path

from .data import read_queries, sha256_file, valid_id


def load_qrels(path, query_ids):
    qrels = {qid: {} for qid in query_ids}
    if len(qrels) != len(query_ids):
        raise ValueError("Duplicate expected query IDs")
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Qrel must be an object on line {number}")
            qid, doc_id = row.get("query-id"), row.get("corpus-id")
            if qid not in qrels or not valid_id(doc_id):
                raise ValueError(f"Invalid qrel query/document ID on line {number}")
            raw = row.get("score")
            if isinstance(raw, bool) or not (type(raw) is int or isinstance(raw, str) and raw in {"0", "1", "2", "3", "4"}):
                raise ValueError(f"Qrel grade must be an integer in 0..4 on line {number}")
            grade = int(raw)
            if not 0 <= grade <= 4 or doc_id in qrels[qid]:
                raise ValueError(f"Duplicate qrel pair or invalid grade on line {number}")
            qrels[qid][doc_id] = grade
    if any(not judgments for judgments in qrels.values()):
        raise ValueError("Every query must have an explicit judgment set")
    return qrels


def gain(grade, mode):
    if mode == "linear":
        return grade
    if mode == "exp2":
        return 2 ** grade - 1
    if mode == "news2019":
        return 2 ** grade if grade > 0 else 0
    raise ValueError("Gain must be linear, exp2 or news2019")


def evaluate_query(ranked_ids, judgments, *, depth=1000, gain_mode="linear"):
    if type(depth) is not int or depth < 1:
        raise ValueError("depth must be a positive integer")
    ranked = list(ranked_ids)[:depth]
    if any(type(grade) is not int or not 0 <= grade <= 4 for grade in judgments.values()):
        raise ValueError("Judgments must contain integer grades in 0..4")
    if len(set(ranked)) != len(ranked):
        raise ValueError("Duplicate document in ranked results")
    # Validate the gain convention even for an empty ranking/judgment set.
    gain(0, gain_mode)
    relevant_total = sum(grade > 0 for grade in judgments.values())
    found, precision_sum, first = 0, 0.0, 0.0
    for rank, doc_id in enumerate(ranked, 1):
        if judgments.get(doc_id, 0) > 0:
            found += 1
            precision_sum += found / rank
            if first == 0:
                first = 1 / rank
    result = {
        "ap_at_1000": precision_sum / relevant_total if relevant_total else 0.0,
        "recall_at_1000": found / relevant_total if relevant_total else 0.0,
        "reciprocal_rank_at_1000": first,
        "retrieved": len(ranked), "known_relevant": relevant_total, "relevant_retrieved": found,
    }
    ideal_gains = sorted((gain(g, gain_mode) for g in judgments.values()), reverse=True)
    for cutoff in (5, 10):
        hits = ranked[:cutoff]
        dcg = sum(gain(judgments.get(doc_id, 0), gain_mode) / math.log2(rank + 1)
                  for rank, doc_id in enumerate(hits, 1))
        ideal = sum(g / math.log2(rank + 1) for rank, g in enumerate(ideal_gains[:cutoff], 1))
        result[f"ndcg_at_{cutoff}"] = dcg / ideal if ideal else 0.0
        result[f"precision_at_{cutoff}"] = sum(judgments.get(doc_id, 0) > 0 for doc_id in hits) / cutoff
        result[f"judged_at_{cutoff}"] = sum(doc_id in judgments for doc_id in hits) / len(hits) if hits else 0.0
    for cutoff in (20, 1000):
        hits = ranked[:cutoff]
        result[f"judged_at_{cutoff}"] = sum(doc_id in judgments for doc_id in hits) / len(hits) if hits else 0.0
    return result


METRICS = ("ndcg_at_5", "ndcg_at_10", "ap_at_1000", "recall_at_1000",
           "precision_at_5", "precision_at_10", "reciprocal_rank_at_1000",
           "judged_at_5", "judged_at_10", "judged_at_20", "judged_at_1000")


def evaluate_rankings(rankings, qrels, *, gain_mode="linear"):
    if not qrels:
        raise ValueError("Cannot evaluate an empty query set")
    if set(rankings) != set(qrels):
        raise ValueError("Run and qrels query sets differ; missing queries cannot silently disappear")
    per_query = {qid: evaluate_query(rankings[qid], judgments, gain_mode=gain_mode)
                 for qid, judgments in qrels.items()}
    aggregate = {key: statistics.mean(row[key] for row in per_query.values()) for key in METRICS}
    return {"query_count": len(per_query), "gain": gain_mode, "aggregate": aggregate, "per_query": per_query,
            "zero_relevant_queries": [qid for qid, row in per_query.items() if not row["known_relevant"]]}


def load_run(run_dir, queries_path, eligible_ids, *, expected_source_sha256):
    root = Path(run_dir)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["engine"] not in {"lucene-bm25", "e5-cosine", "rrf"}:
        raise ValueError("Unknown run engine")
    # Early BM25 manifests predate the coverage field; full BM25 source/count is bound below.
    if manifest.get("coverage", "full" if manifest["engine"] == "lucene-bm25" else None) != "full":
        raise ValueError("Benchmark requires full-corpus runs")
    if manifest["top_k"] != 1000 or manifest["corpus_sha256"] != expected_source_sha256:
        raise ValueError("Run depth or corpus identity differs from benchmark")
    if manifest["query_source_sha256"] != sha256_file(queries_path):
        raise ValueError("Run uses a different query source")
    for name, key in (("run.trec", "run_sha256"), ("results.jsonl", "results_sha256"),
                      ("queries.jsonl", "query_snapshot_sha256")):
        if sha256_file(root / name) != manifest[key]:
            raise ValueError(f"Run file hash mismatch: {name}")
    queries = read_queries(queries_path)
    if queries != read_queries(root / "queries.jsonl"):
        raise ValueError("Run query snapshot differs from requested suite")
    rows = [json.loads(line) for line in (root / "results.jsonl").read_text().splitlines()]
    if len(rows) != len(queries) or manifest["query_count"] != len(queries):
        raise ValueError("Run must explicitly represent every query")
    trec_lines = (root / "run.trec").read_text().splitlines()
    position, rankings = 0, {}
    for query, row in zip(queries, rows, strict=True):
        if row["query_id"] != query["_id"] or row["query"] != query["text"]:
            raise ValueError("Run query order/text mismatch")
        previous, seen, ranked = math.inf, set(), []
        if len(row["hits"]) > 1000:
            raise ValueError("Run exceeds its configured depth")
        for rank, hit in enumerate(row["hits"], 1):
            doc_id, score = hit["doc_id"], hit["score"]
            if (doc_id not in eligible_ids or doc_id in seen or hit["rank"] != rank
                    or not math.isfinite(score) or score > previous):
                raise ValueError("Ineligible/duplicate document, bad rank or invalid score")
            expected = f"{query['_id']} Q0 {doc_id} {rank} {score:.9g} {manifest['run_tag']}"
            if position >= len(trec_lines) or trec_lines[position] != expected:
                raise ValueError("TREC and JSONL rankings disagree")
            seen.add(doc_id)
            ranked.append(doc_id)
            previous, position = score, position + 1
        rankings[query["_id"]] = ranked
    if position != len(trec_lines) or position != manifest["total_hits"]:
        raise ValueError("Run hit count mismatch")
    return rankings, manifest


def paired_comparison(first, second, *, samples=10000, seed=20261024):
    import numpy as np

    if type(samples) is not int or samples < 1:
        raise ValueError("Bootstrap samples must be positive")
    if set(first["per_query"]) != set(second["per_query"]):
        raise ValueError("Paired comparison requires identical query sets")
    qids = list(first["per_query"])
    if not qids:
        raise ValueError("Paired comparison requires at least one query")
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(qids), size=(samples, len(qids)))
    report = {}
    for metric in ("ndcg_at_5", "ap_at_1000"):
        deltas = np.array([second["per_query"][q][metric] - first["per_query"][q][metric] for q in qids])
        interval = np.quantile(deltas[draws].mean(axis=1), [0.025, 0.975])
        report[metric] = {"mean_dense_minus_bm25": float(deltas.mean()),
                          "paired_bootstrap_95_percentile_ci": interval.tolist(),
                          "dense_wins": int((deltas > 1e-12).sum()),
                          "ties": int((np.abs(deltas) <= 1e-12).sum()),
                          "bm25_wins": int((deltas < -1e-12).sum())}
    return {"direction": "dense minus bm25", "samples": samples, "seed": seed,
            "unit": f"query; percentile intervals are descriptive for this {len(qids)}-query set", "metrics": report}
