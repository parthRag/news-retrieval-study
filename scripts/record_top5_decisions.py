"""Store explicitly supplied AI reading decisions; this tool never assigns grades.

Input on stdin: query_id, decisions [{position, grade, rationale, quotes,
confidence, full_article_read:true}]. Positions match read_assessment_batch.py.
"""

import json
import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from news_ir.assessment import validate_assessments, write_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("top5", "depth20"), default="top5")
    args = parser.parse_args()
    supplied = json.load(sys.stdin)
    # Compact input still contains an explicit reading decision for every row.
    if "decisions" not in supplied and "rows" in supplied:
        supplied["decisions"] = [dict(position=r[0], grade=r[1], quotes=r[2], rationale=r[3],
                                      confidence=r[4] if len(r) > 4 else "high", full_article_read=True)
                                  for r in supplied["rows"]]
    pool = Path("artifacts/assessments/custom20-v1")
    destination = Path(f"annotations/ai_study_v1/assessments.{args.scope}.jsonl")
    if not destination.exists():
        seed = "assessments.top5.jsonl" if args.scope == "depth20" else "assessments.pilot.jsonl"
        shutil.copyfile(destination.with_name(seed), destination)
    priority = {(r["query_id"], r["doc_id"]) for r in
                map(json.loads, (pool / "pool.provenance.jsonl").read_text().splitlines()) if r["priority_top5"]}
    articles = [r for r in map(json.loads, (pool / "articles.blinded.jsonl").read_text().splitlines())
                if r["query_id"] == supplied["query_id"] and (args.scope == "depth20" or (r["query_id"], r["doc_id"]) in priority)]
    existing = list(map(json.loads, destination.read_text().splitlines()))
    for decision in supplied["decisions"]:
        position = decision["position"]
        if type(position) is not int or not 0 <= position < len(articles):
            raise ValueError("Position outside query's selected article union")
        article = articles[position]
        contents = (article["title"] + "\n" + article["text"]).strip()
        spans = []
        for quote in decision["quotes"]:
            start = contents.find(quote)
            if start < 0:
                raise ValueError(f"Evidence absent from article {position}: {quote}")
            spans.append({"start": start, "end": start + len(quote), "quote": quote})
        existing.append({"query_id": article["query_id"], "doc_id": article["doc_id"],
                         "grade": decision["grade"], "rationale": decision["rationale"],
                         "confidence": decision["confidence"], "full_article_read": decision["full_article_read"],
                         "assessor_type": "AI", "assessor": "Codex assistant; exact serving model identifier unavailable",
                         "read_scope": "Entire available title/body; exact duplicate content read once; repeated extraction abbreviation glossary omitted in display",
                         "contents_sha256": article["contents_sha256"], "evidence": spans,
                         "assessed_at_utc": datetime.now(timezone.utc).isoformat()})
    temporary = destination.with_suffix(".pending.jsonl")
    try:
        write_jsonl(temporary, existing)
        validation = validate_assessments(pool, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({k: v for k, v in validation.items() if k != "qrels"}, indent=2))


if __name__ == "__main__":
    main()
