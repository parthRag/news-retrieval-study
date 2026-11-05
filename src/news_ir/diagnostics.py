"""Complementarity diagnostics over frozen rankings and existing reference labels.

Oracle values use labels and are ceilings, never deployable retrieval systems.
Unknown labels remain distinct from explicit nonrelevance throughout.
"""
import statistics

from .evaluation import evaluate_query
from .fusion import explain_fusion_hits


DEPTHS = (5, 10, 20, 100, 1000)
ENGINES = ("bm25", "dense", "rrf")


def overlap(first, second, depth):
    """Set overlap plus prefix agreement, which is sensitive to rank order.

    Prefix agreement averages |A[:d] intersect B[:d]| / max(prefix lengths)
    for d=1..min(depth, longer list length). Two empty lists agree completely.
    """
    if type(depth) is not int or depth < 1:
        raise ValueError("depth must be a positive integer")
    first, second = list(first)[:depth], list(second)[:depth]
    if len(set(first)) != len(first) or len(set(second)) != len(second):
        raise ValueError("Duplicate ranked document")
    a, b = set(first), set(second)
    union = a | b
    left, right, agreements = set(), set(), []
    for i in range(max(len(first), len(second))):
        if i < len(first):
            left.add(first[i])
        if i < len(second):
            right.add(second[i])
        agreements.append(len(left & right) / max(len(left), len(right)))
    return {"shared": len(a & b), "union_size": len(union),
            "jaccard": len(a & b) / len(union) if union else 1.0,
            "mean_prefix_overlap": statistics.mean(agreements) if agreements else 1.0}


def label_counts(doc_ids, judgments):
    ids = set(doc_ids)
    return {"known_relevant": sum(judgments.get(d, 0) > 0 for d in ids),
            "explicit_nonrelevant": sum(d in judgments and judgments[d] == 0 for d in ids),
            "unjudged": sum(d not in judgments for d in ids)}


def diagnose_query(rankings, judgments, *, depths=DEPTHS):
    if set(rankings) != set(ENGINES):
        raise ValueError("Expected BM25, dense and RRF rankings")
    if not depths or len(set(depths)) != len(depths) or any(type(d) is not int or d < 1 or d > 1000 for d in depths):
        raise ValueError("Diagnostic depths must be distinct integers in 1..1000")
    rankings = {e: list(r) for e, r in rankings.items()}
    if any(len(r) > 1000 or len(set(r)) != len(r) for r in rankings.values()):
        raise ValueError("Rankings must be unique and at most 1,000 documents")
    if not set(rankings["rrf"]) <= set(rankings["bm25"]) | set(rankings["dense"]):
        raise ValueError("RRF contains a document outside the component union")
    scores = {e: evaluate_query(r, judgments) for e, r in rankings.items()}
    relevant_total = sum(g > 0 for g in judgments.values())
    by_depth = {}
    for depth in depths:
        a, b = (set(rankings[e][:depth]) for e in ("bm25", "dense"))
        union, shared = a | b, a & b
        relevant = {d for d in union if judgments.get(d, 0) > 0}
        oracle = sorted(union, key=lambda d: (-judgments.get(d, 0), d))
        by_depth[str(depth)] = {
            **overlap(rankings["bm25"], rankings["dense"], depth),
            "bm25_only_known_relevant": len(relevant & (a - b)),
            "dense_only_known_relevant": len(relevant & (b - a)),
            "shared_known_relevant": len(relevant & shared),
            "union_known_relevant": len(relevant),
            "union_recall": len(relevant) / relevant_total if relevant_total else 0.0,
            "oracle_union_ndcg_at_5": evaluate_query(oracle[:5], judgments)["ndcg_at_5"],
            "label_counts": {e: label_counts(rankings[e][:depth], judgments) for e in ENGINES},
        }
    top = {e: set(r[:5]) for e, r in rankings.items()}
    changes = {}
    for e in ("bm25", "dense"):
        removed = sorted(top[e] - top["rrf"])
        introduced = sorted(top["rrf"] - top[e])
        changes[e] = {"removed_ids": removed, "introduced_ids": introduced,
                      "removed_labels": label_counts(removed, judgments),
                      "introduced_labels": label_counts(introduced, judgments)}
    explained = explain_fusion_hits(
        [{"doc_id": d, "rank": i} for i, d in enumerate(rankings["rrf"][:5], 1)],
        {e: rankings[e] for e in ("bm25", "dense")})
    for hit in explained:
        hit["known_grade"] = judgments.get(hit["doc_id"])
        hit["label_status"] = ("unjudged" if hit["doc_id"] not in judgments else
                               "known_relevant" if judgments[hit["doc_id"]] > 0 else "explicit_nonrelevant")
    return {"engines": scores, "depths": by_depth,
            "per_query_best_single_ndcg_at_5": max(scores[e]["ndcg_at_5"] for e in ("bm25", "dense")),
            "fusion_changes_at_5": changes, "fusion_top5": explained,
            "fusion_known_relevant_from_below_both_top5": label_counts(
                top["rrf"] - (top["bm25"] | top["dense"]), judgments)["known_relevant"]}


def summarize(per_query):
    if not per_query:
        raise ValueError("Cannot summarize an empty query set")
    rows = list(per_query.values())
    depth_keys = list(rows[0]["depths"])
    if any(list(r["depths"]) != depth_keys for r in rows):
        raise ValueError("Diagnostic depths differ between queries")
    mean = statistics.mean
    engines = {e: {m: mean(r["engines"][e][m] for r in rows)
                   for m in ("ndcg_at_5", "ndcg_at_10", "ap_at_1000", "recall_at_1000", "judged_at_5")}
               for e in ENGINES}
    depths = {}
    for d in depth_keys:
        depths[d] = {m: mean(r["depths"][d][m] for r in rows)
                     for m in rows[0]["depths"][d] if m != "label_counts"}
        depths[d]["queries_with_bm25_only_known_relevant"] = sum(r["depths"][d]["bm25_only_known_relevant"] > 0 for r in rows)
        depths[d]["queries_with_dense_only_known_relevant"] = sum(r["depths"][d]["dense_only_known_relevant"] > 0 for r in rows)
    effects = {}
    for e in ("bm25", "dense"):
        deltas = [r["engines"]["rrf"]["ndcg_at_5"] - r["engines"][e]["ndcg_at_5"] for r in rows]
        effects[e] = {"mean_ndcg_at_5_difference": mean(deltas),
                      "wins": sum(d > 1e-12 for d in deltas), "losses": sum(d < -1e-12 for d in deltas),
                      "ties": sum(abs(d) <= 1e-12 for d in deltas),
                      "removed_known_relevant": sum(r["fusion_changes_at_5"][e]["removed_labels"]["known_relevant"] for r in rows),
                      "introduced_known_relevant": sum(r["fusion_changes_at_5"][e]["introduced_labels"]["known_relevant"] for r in rows)}
    return {"query_count": len(rows), "engines": engines, "depths": depths, "fusion_vs_source": effects,
            "per_query_best_single_oracle_ndcg_at_5": mean(r["per_query_best_single_ndcg_at_5"] for r in rows),
            "best_fixed_single_ndcg_at_5": max(engines[e]["ndcg_at_5"] for e in ("bm25", "dense")),
            "fusion_known_relevant_from_below_both_top5": sum(r["fusion_known_relevant_from_below_both_top5"] for r in rows)}


def formulation_stability(original, alternative, *, depth=10):
    """Within-topic membership/order stability; no claims about intent equivalence."""
    if not original or set(original) != set(alternative):
        raise ValueError("Formulations must cover identical nonempty topic sets")
    per_query = {q: overlap(original[q], alternative[q], depth) for q in sorted(original)}
    return {"query_count": len(per_query), "depth": depth, "per_query": per_query,
            "aggregate": {m: statistics.mean(r[m] for r in per_query.values())
                          for m in ("shared", "union_size", "jaccard", "mean_prefix_overlap")}}
