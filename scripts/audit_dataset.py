"""Inspect the local retrieval dataset without modifying its source files.

Run from the project root: python3 scripts/audit_dataset.py
Uses only the Python standard library; corpus text is streamed, not retained.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def records(path, manifests):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line_number, raw in enumerate(stream, 1):
            digest.update(raw)
            if not raw.strip():
                raise ValueError(f"{path}:{line_number}: blank JSONL record")
            row = json.loads(raw)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield row
    manifests[path.name] = {
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def require_strings(row, keys):
    for key in keys:
        if not isinstance(row.get(key), str):
            raise ValueError(f"Missing or non-string field {key!r}: {row.keys()}")


def audit(data_dir):
    manifests = {}
    queries = list(records(data_dir / "queries.jsonl", manifests))
    qrels = list(records(data_dir / "qrel.jsonl", manifests))
    for row in queries:
        require_strings(row, ("_id", "text"))
    query_ids = {row["_id"] for row in queries}
    titles = defaultdict(list)
    for row in queries:
        titles[row["text"]].append(row["_id"])
    grades = Counter()
    positives = Counter()
    qrel_docs = set()
    pairs = set()
    duplicate_pairs = 0
    for row in qrels:
        require_strings(row, ("query-id", "corpus-id"))
        grade = int(row["score"])
        if str(grade) != str(row["score"]) or not 0 <= grade <= 4:
            raise ValueError(f"Expected integer relevance grade 0..4: {row}")
        grades[grade] += 1
        if grade > 0:
            positives[row["query-id"]] += 1
        pair = row["query-id"], row["corpus-id"]
        duplicate_pairs += pair in pairs
        pairs.add(pair)
        qrel_docs.add(row["corpus-id"])

    seen = set()
    schemas = Counter()
    word_counts = []
    empty_text = empty_title = empty_both = duplicates = 0
    title_matches = defaultdict(list)
    for row in records(data_dir / "corpus.jsonl", manifests):
        require_strings(row, ("_id", "title", "text"))
        doc_id, title, text = row["_id"], row["title"], row["text"]
        duplicates += doc_id in seen
        seen.add(doc_id)
        schemas[tuple(sorted(row))] += 1
        empty_text += not text.strip()
        empty_title += not title.strip()
        empty_both += not title.strip() and not text.strip()
        word_counts.append(len(text.split()))
        for query_id in titles.get(title, ()):
            title_matches[query_id].append(doc_id)
    if not word_counts:
        raise ValueError("Empty corpus")
    word_counts.sort()
    missing_ids = qrel_docs - seen
    missing_qrels = [row for row in qrels if row["corpus-id"] in missing_ids]
    positive_counts = [positives[query_id] for query_id in sorted(query_ids)]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": manifests,
        "corpus": {
            "rows": len(word_counts), "unique_doc_ids": len(seen),
            "duplicate_doc_ids": duplicates,
            "schemas": [{"keys": list(keys), "rows": count} for keys, count in schemas.items()],
            "empty_text": empty_text, "empty_title": empty_title,
            "empty_title_and_text": empty_both,
            "body_word_counts": {
                "mean": round(sum(word_counts) / len(word_counts), 2),
                "median": word_counts[len(word_counts) // 2],
                "p90": word_counts[int(len(word_counts) * 0.90)],
                "p99": word_counts[int(len(word_counts) * 0.99)],
                "max": word_counts[-1],
            },
        },
        "queries": {
            "rows": len(queries), "duplicate_ids": len(queries) - len(query_ids),
            "empty_text": sum(not row["text"].strip() for row in queries),
            "exact_headline_matches_in_corpus": dict(title_matches),
        },
        "qrels": {
            "rows": len(qrels), "grade_counts": dict(sorted(grades.items())),
            "duplicate_pairs": duplicate_pairs,
            "unknown_query_ids": sorted({row["query-id"] for row in qrels} - query_ids),
            "missing_corpus_doc_ids": sorted(missing_ids),
            "missing_corpus_judgment_rows": len(missing_qrels),
            "missing_corpus_grade_counts": dict(sorted(Counter(int(row["score"]) for row in missing_qrels).items())),
            "missing_corpus_judgments": missing_qrels,
            "positive_judgments_per_query": {
                "min": min(positive_counts), "max": max(positive_counts),
                "mean": round(sum(positive_counts) / len(positive_counts), 2),
            },
        },
        "notes": [
            "Word lengths use whitespace splitting, not model tokenization.",
            "Dataset provenance and official benchmark equivalence require a separate source check.",
            "Missing judged documents and headline matches are reported, not removed.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.data_dir)
    output = args.output or args.data_dir / "artifacts" / "dataset_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Audit saved to {output}")
    print(f"Documents: {result['corpus']['rows']:,}; queries: {result['queries']['rows']}; qrels: {result['qrels']['rows']:,}")
    print(f"Missing judged document IDs: {len(result['qrels']['missing_corpus_doc_ids'])}")
    print(f"Grades for missing documents: {result['qrels']['missing_corpus_grade_counts']}")
    print(f"Documents with no title or body: {result['corpus']['empty_title_and_text']}")


if __name__ == "__main__":
    main()
