import copy
import math

import pytest

from news_ir.diagnostics import diagnose_query, formulation_stability, label_counts, overlap, summarize
from news_ir.fusion import explain_fusion_hits, reciprocal_rank_fusion


def test_overlap_distinguishes_membership_and_order_and_short_empty_lists():
    same = overlap(["a", "b"], ["a", "b"], 10)
    reversed_ = overlap(["a", "b"], ["b", "a"], 10)
    assert same["jaccard"] == same["mean_prefix_overlap"] == 1
    assert reversed_["jaccard"] == 1
    assert reversed_["mean_prefix_overlap"] == .5
    assert overlap([], [], 5)["mean_prefix_overlap"] == 1
    assert overlap([], ["a"], 5)["jaccard"] == 0
    assert overlap(["a"], ["a", "b"], 5)["mean_prefix_overlap"] == .75
    with pytest.raises(ValueError, match="Duplicate"):
        overlap(["a", "a"], [], 5)
    with pytest.raises(ValueError):
        overlap([], [], True)


def test_unjudged_is_never_an_explicit_negative():
    assert label_counts(["a", "b", "c", "a"], {"a": 2, "b": 0}) == {
        "known_relevant": 1, "explicit_nonrelevant": 1, "unjudged": 1}


def test_hand_computed_complementarity_recall_and_oracle_with_missing_positive():
    # The absent highest-grade positive must remain in the ideal/recall denominator.
    labels = {"a": 1, "b": 2, "negative": 0, "missing": 4}
    row = diagnose_query({"bm25": ["negative", "a"], "dense": ["unknown", "b"],
                          "rrf": ["negative", "a", "unknown", "b"]}, labels, depths=(5, 20))
    d = row["depths"]["20"]
    assert d["bm25_only_known_relevant"] == d["dense_only_known_relevant"] == 1
    assert d["union_known_relevant"] == 2 and d["shared_known_relevant"] == 0
    assert d["union_recall"] == pytest.approx(2 / 3)
    ideal = 4 + 2 / math.log2(3) + 1 / math.log2(4)
    assert d["oracle_union_ndcg_at_5"] == pytest.approx((2 + 1 / math.log2(3)) / ideal)
    assert d["label_counts"]["rrf"]["unjudged"] == 1
    assert d["label_counts"]["rrf"]["explicit_nonrelevant"] == 1
    assert row["fusion_top5"][2]["known_grade"] is None
    assert row["fusion_top5"][2]["label_status"] == "unjudged"
    assert row["fusion_top5"][0]["known_grade"] == 0


def test_fusion_can_rescue_an_article_below_both_top_fives_and_drop_unique_positive():
    bm25 = [f"b{i}" for i in range(4)] + ["unique", "shared"]
    dense = [f"d{i}" for i in range(5)] + ["shared"]
    # Unfused singleton scores are lower than a shared sixth-ranked candidate.
    fused = reciprocal_rank_fusion([bm25, dense])
    row = diagnose_query({"bm25": bm25, "dense": dense, "rrf": [h["doc_id"] for h in fused]},
                         {"shared": 2, "unique": 1})
    assert row["fusion_known_relevant_from_below_both_top5"] == 1
    assert row["fusion_top5"][0]["fusion"]["component_ranks"] == {"bm25": 6, "dense": 6}
    assert row["fusion_changes_at_5"]["bm25"]["removed_labels"]["known_relevant"] == 1
    assert row["fusion_changes_at_5"]["bm25"]["introduced_labels"]["known_relevant"] == 1


def test_summary_separates_per_query_oracle_from_best_fixed_engine():
    rows = {"q1": diagnose_query({"bm25": ["a"], "dense": ["b"], "rrf": ["a", "b"]}, {"a": 2, "b": 0}),
            "q2": diagnose_query({"bm25": ["a"], "dense": ["b"], "rrf": ["a", "b"]}, {"a": 0, "b": 2})}
    s = summarize(rows)
    assert s["best_fixed_single_ndcg_at_5"] == .5
    assert s["per_query_best_single_oracle_ndcg_at_5"] == 1
    assert s["fusion_vs_source"]["bm25"]["wins"] == 1
    assert s["fusion_vs_source"]["bm25"]["ties"] == 1
    assert s["depths"]["5"]["queries_with_dense_only_known_relevant"] == 1
    assert s["depths"]["5"]["queries_with_bm25_only_known_relevant"] == 1
    with pytest.raises(ValueError):
        summarize({})


def test_stability_pairs_topic_ids_and_rejects_dropped_topics():
    result = formulation_stability({"2": ["a"], "1": ["b"]}, {"1": ["b"], "2": ["x"]})
    assert result["aggregate"]["jaccard"] == .5
    with pytest.raises(ValueError, match="identical"):
        formulation_stability({"1": ["a"]}, {"2": ["a"]})


def test_fusion_explanations_preserve_hits_scores_and_zero_missing_contributions():
    components = {"bm25": ["b", "a"], "dense": ["a", "z"]}
    hits = reciprocal_rank_fusion(list(components.values()))
    snapshot = copy.deepcopy(hits)
    explained = explain_fusion_hits(hits, components)
    assert hits == snapshot
    for hit in explained:
        assert hit["score"] == pytest.approx(hit["fusion"]["reconstructed_score"])
    z = next(h for h in explained if h["doc_id"] == "z")
    assert z["fusion"]["component_ranks"]["bm25"] is None
    assert z["fusion"]["contributions"]["bm25"] == 0
    with pytest.raises(ValueError, match="absent"):
        explain_fusion_hits([{"doc_id": "missing"}], components)
    with pytest.raises(ValueError, match="Duplicate"):
        explain_fusion_hits([], {"a": ["x", "x"], "b": []})


@pytest.mark.parametrize("rankings,depths", [
    ({"bm25": [], "dense": [], "rrf": ["outside"]}, (5,)),
    ({"bm25": ["a", "a"], "dense": [], "rrf": []}, (5,)),
    ({"bm25": [], "dense": [], "rrf": []}, (5, 5)),
    ({"bm25": [], "dense": [], "rrf": []}, (0,)),
    ({"bm25": [], "dense": [], "rrf": []}, (1001,)),
    ({"bm25": [], "dense": [], "rrf": []}, (True,)),
])
def test_bad_rankings_and_depths_are_rejected(rankings, depths):
    with pytest.raises(ValueError):
        diagnose_query(rankings, {}, depths=depths)
