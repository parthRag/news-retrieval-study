"""Reuse an existing decision only for identical full content under the same query.

No new relevance decision is inferred. Content hashes and evidence are validated
against the frozen source packets before the destination is atomically replaced.
"""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from news_ir.assessment import validate_assessments, write_jsonl


def reuse_identical(pool: Path, source: Path, destination: Path):
    validation = validate_assessments(pool, source)
    rows = list(map(json.loads, source.read_text().splitlines()))
    lookup = {(r["query_id"], r["contents_sha256"]): r for r in rows}
    done = {(r["query_id"], r["doc_id"]) for r in rows}
    added = 0
    for article in map(json.loads, (pool / "articles.blinded.jsonl").read_text().splitlines()):
        key = article["query_id"], article["doc_id"]
        parent = lookup.get((article["query_id"], article["contents_sha256"]))
        if key in done or parent is None:
            continue
        row = copy.deepcopy(parent)
        row["doc_id"] = article["doc_id"]
        row["assessed_at_utc"] = datetime.now(timezone.utc).isoformat()
        row["judgment_reuse"] = {"method": "identical_query_and_full_contents_sha256",
                                 "source_doc_id": parent["doc_id"]}
        rows.append(row)
        done.add(key)
        added += 1
    temporary = destination.with_suffix(".reuse-pending.jsonl")
    try:
        write_jsonl(temporary, rows)
        validation = validate_assessments(pool, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"reused_pairs_added": added, "assessed_pairs": validation["assessed_pairs"],
            "remaining_pairs": validation["remaining_pairs"]}


if __name__ == "__main__":
    pool = Path("artifacts/assessments/custom20-v1")
    destination = Path("annotations/ai_study_v1/assessments.depth20.jsonl")
    source = destination if destination.exists() else destination.with_name("assessments.top5.jsonl")
    print(json.dumps(reuse_identical(pool, source, destination)))
