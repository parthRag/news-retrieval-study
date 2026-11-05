"""Prepare blinded, portable human review tasks; validate returned judgments.

Relevance labels and query-meaning checks have separate schemas. Partial reviews
are never promoted to a complete human-labeled retrieval benchmark.
"""
import hashlib
import json
from collections import Counter


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def select_article_pairs(queries, rankings, *, seed="news-ir-human-round1-20261102"):
    """One top-five draw per query per wave, counterbalanced by category.

    Selection never receives relevance labels. Wave 1 targets five queries per
    engine in each ten-query category; wave 2 uses the other engine and a
    different document. Shared hits remain shared; targeted origin isn't proof
    that only that engine retrieved an article.
    """
    key = lambda value: hashlib.sha256((seed + "\0" + value).encode()).hexdigest()
    groups = {}
    for query in queries:
        groups.setdefault(query["category"], []).append(query["_id"])
    first = {}
    for category, qids in groups.items():
        for i, qid in enumerate(sorted(qids, key=key)):
            first[qid] = "bm25" if i < len(qids) // 2 else "dense"
    selected = []
    for query in queries:
        qid = query["_id"]
        used = set()
        engines = [first[qid], "dense" if first[qid] == "bm25" else "bm25"]
        for wave, engine in enumerate(engines, 1):
            candidates = set(rankings[engine][qid][:5]) - used
            if not candidates:
                raise ValueError("Need two distinct top-five articles per query")
            doc_id = min(candidates, key=lambda d: key(f"{qid}:{wave}:{d}"))
            used.add(doc_id)
            selected.append({"query_id": qid, "doc_id": doc_id, "wave": wave,
                             "target_engine": engine})
    return selected


def validate_return(tasks, reviews):
    """Validate supplied rows without changing frozen queries, labels or scores."""
    lookup = {t["task_id"]: t for t in tasks}
    if len(lookup) != len(tasks):
        raise ValueError("Duplicate task IDs in pack")
    seen, accepted, pending, uncertain = set(), [], [], []
    for row in reviews:
        task_id = row.get("task_id")
        if task_id not in lookup:
            raise ValueError("Unknown review task: " + str(task_id))
        task = lookup[task_id]
        field = "grade" if task["kind"] == "relevance" else "verdict"
        value = row.get(field)
        if value in (None, ""):
            pending.append(task_id)
            continue
        reviewer = row.get("reviewer", "")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError(f"{task_id}: enter the actual reviewer name")
        identity = reviewer.strip().casefold(), task_id
        if identity in seen:
            raise ValueError(f"{task_id}: duplicate reviewer/task; supply only the latest export")
        seen.add(identity)
        reason = row.get("reason", "")
        if not isinstance(reason, str):
            raise ValueError(f"{task_id}: reason must be text")
        checked = dict(row, reviewer=reviewer.strip())
        if task["kind"] == "relevance":
            if not (type(value) is int and value in (0, 1, 2) or value == "U"):
                raise ValueError(f"{task_id}: grade must be 0, 1, 2 or U")
            if value != "U" and row.get("full_article_read") is not True:
                raise ValueError(f"{task_id}: confirm reading the full available article")
            quote = row.get("evidence_quote", "")
            if not isinstance(quote, str):
                raise ValueError(f"{task_id}: evidence quote must be text")
            if quote:
                start = task["article_contents"].find(quote)
                if start < 0:
                    raise ValueError(f"{task_id}: evidence is not a literal article quotation")
                checked["evidence"] = [{"start": start, "end": start + len(quote), "quote": quote}]
            checked.update(query_id=task["query_id"], doc_id=task["doc_id"],
                           contents_sha256=task["contents_sha256"])
        else:
            if value not in {"same", "narrower", "broader", "different", "uncertain"}:
                raise ValueError(f"{task_id}: invalid meaning verdict")
            checked.update(topic_id=task["topic_id"], dataset=task["dataset"])
        if value in ("U", "uncertain"):
            uncertain.append(checked)
        else:
            accepted.append(checked)
    resolved = {r["task_id"] for r in accepted}
    required = {t["task_id"] for t in tasks if t["priority"] == "required"}
    kinds = Counter(lookup[r["task_id"]]["kind"] for r in accepted)
    queries = {r["query_id"] for r in accepted if lookup[r["task_id"]]["kind"] == "relevance"}
    return {"status": "valid", "resolved_unique_tasks": len(resolved),
            "required_tasks": len(required), "required_resolved": len(required & resolved),
            "required_unresolved_ids": sorted(required - resolved),
            "resolved_review_rows_by_kind": dict(kinds), "article_query_coverage": len(queries),
            "actual_reviewer_count": len({r["reviewer"].casefold() for r in accepted + uncertain}),
            "resolved_rows_with_written_reason": sum(bool(r.get("reason", "").strip()) for r in accepted),
            "resolved_rows_with_literal_evidence": sum(bool(r.get("evidence")) for r in accepted),
            "uncertain_rows": len(uncertain), "blank_rows": len(pending),
            "accepted": accepted, "uncertain": uncertain,
            "interpretation": "A stratified top-five audit, not complete human qrels for custom40. One reviewer does not establish inter-human agreement."}


def review_views(tasks):
    """Alternative time/team views of the same immutable task IDs and contents."""
    required = [t for t in tasks if t['priority'] == 'required']
    extra = [t for t in tasks if t['priority'] == 'optional']
    rewrites = [t for t in required if t['kind'] == 'rewrite']
    articles = [t for t in required if t['kind'] == 'relevance']
    categories = list(dict.fromkeys(t['category'] for t in articles))
    short = [t for c in categories for t in [r for r in articles if r['category'] == c][:3]]
    overlap = [t for c in categories for t in [r for r in articles if r['category'] == c][:2]]
    views = [('START_HERE.html', 'Main review — 94 required tasks', required),
             ('TIME_LIMITED.html', 'Time-limited review — 54 meaning checks + 12 articles', rewrites + short),
             ('OPTIONAL_SECOND_PASS.html', 'Optional second article pass — 40 tasks', extra),
             ('SECOND_REVIEWER_8.html', 'Optional independent second reviewer — 8 existing article tasks', overlap)]
    views += [(f'BATCH_{b}.html', f'Batch {b} — required tasks', [t for t in required if t['batch'] == b]) for b in 'ABCD']
    views += [('TWO_REVIEWERS_1.html', 'Two reviewers: person 1 — batches A + C', [t for t in required if t['batch'] in 'AC']),
              ('TWO_REVIEWERS_2.html', 'Two reviewers: person 2 — batches B + D', [t for t in required if t['batch'] in 'BD'])]
    return views
