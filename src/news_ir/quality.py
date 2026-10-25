"""Bounded, label-independent quality reranking of already judged candidates."""
from .evaluation import evaluate_query


def filter_candidates(ids, articles, *, empty=False, deduplicate=False):
    kept, seen = [], set()
    for doc_id in ids:
        article = articles[doc_id]
        if empty and not article["text"].strip():
            continue
        content = article["contents_sha256"]
        if deduplicate and content in seen:
            continue
        seen.add(content)
        kept.append(doc_id)
    return kept


def quality_scores(ids, articles, labels):
    """Fixed-document reference and unique-content nDCG, both only at rank five.

    Duplicate content earns unique-content gain only on its first occurrence.
    Later duplicates retain rank and contribute zero. The content IDCG uses all
    unique contents in the original joint pool. No new relevance is inferred.
    """
    if len(ids) != len(set(ids)) or any(d not in labels for d in ids):
        raise ValueError("Candidates must be unique judged document IDs")
    by_content = {}
    for doc_id, grade in labels.items():
        content = articles[doc_id]["contents_sha256"]
        if content in by_content and by_content[content] != grade:
            raise ValueError("Same-query identical content has conflicting grades")
        by_content[content] = grade
    ranked, seen = [], set()
    for rank, doc_id in enumerate(ids):
        content = articles[doc_id]["contents_sha256"]
        ranked.append("content:" + content if content not in seen else f"duplicate:{rank}")
        seen.add(content)
    fixed = evaluate_query(ids, labels)
    unique = evaluate_query(ranked, {"content:" + h: g for h, g in by_content.items()})
    return {"fixed_reference_ndcg_at_5": fixed["ndcg_at_5"],
            "precision_at_5": fixed["precision_at_5"],
            "unique_content_ndcg_at_5": unique["ndcg_at_5"],
            "displayed_at_5": min(5, len(ids)),
            "unique_contents_at_5": len({articles[d]["contents_sha256"] for d in ids[:5]})}
