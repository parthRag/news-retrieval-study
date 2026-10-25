"""Print full stored bodies in stable, zero-based packet order (no grading)."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query_id")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int)
    parser.add_argument("--scope", choices=("top5", "depth20"), default="top5")
    parser.add_argument("--pending-only", action="store_true")
    parser.add_argument("--max-chars", type=int, help="Stop before the next article would exceed this display budget; never truncate an article")
    parser.add_argument("--body-start", type=int, default=0, help="Explicit character range for reading a long article in consecutive chunks")
    parser.add_argument("--body-end", type=int)
    args = parser.parse_args()
    root = Path("artifacts/assessments/custom20-v1")
    priority = {(r["query_id"], r["doc_id"]) for r in
                map(json.loads, (root / "pool.provenance.jsonl").read_text().splitlines()) if r["priority_top5"]}
    rows = [r for r in map(json.loads, (root / "articles.blinded.jsonl").read_text().splitlines())
            if r["query_id"] == args.query_id and (args.scope == "depth20" or (r["query_id"], r["doc_id"]) in priority)]
    labels = Path(f"annotations/ai_study_v1/assessments.{args.scope}.jsonl")
    if not labels.exists() and args.scope == "depth20":
        labels = labels.with_name("assessments.top5.jsonl")
    assessed = {(r["query_id"], r["doc_id"]) for r in map(json.loads, labels.read_text().splitlines())} if labels.exists() else set()
    seen = {}
    printed_chars = 0
    for position, row in enumerate(rows):
        digest = row["contents_sha256"]
        first = seen.setdefault(digest, position)
        if position < args.start or args.end is not None and position >= args.end:
            continue
        if args.pending_only and (row["query_id"], row["doc_id"]) in assessed:
            continue
        if args.max_chars is not None and len(row["text"]) > args.max_chars and not args.body_start and args.body_end is None:
            print(f"\nNEXT POSITION: {position}; long body ({len(row['text'])} characters). Read with explicit --body-start/--body-end chunks before judging.")
            break
        if args.max_chars is not None and printed_chars and printed_chars + len(row["text"]) > args.max_chars:
            print(f"\nNEXT POSITION: {position} (display budget reached; article not printed)")
            break
        print(f"\nARTICLE {position} {row['doc_id']} | {row['title']} | original body chars: {len(row['text'])}")
        if first != position and not args.pending_only:
            print(f"EXACT CONTENT DUPLICATE of article {first}; source SHA256 {digest}")
            continue
        body = row["text"]
        # Remove only this repeated extraction glossary; do not truncate substantive article text.
        glossary = "*[WSU]: Wayne State University   *[Tue]: Tuesday   *[Wed]: Wednesday   *[UNM]: University of New Mexico"
        count = body.count(glossary)
        if count:
            print(f"[Repeated extraction glossary omitted {count} times: {glossary}]")
            body = body.replace(glossary, "")
        if args.body_start or args.body_end is not None:
            print(f"[Explicit body chunk {args.body_start}:{args.body_end}; complete displayed body length {len(body)}; read all chunks before judging]")
        print(body[args.body_start:args.body_end])
        printed_chars += len(row["text"])


if __name__ == "__main__":
    main()
