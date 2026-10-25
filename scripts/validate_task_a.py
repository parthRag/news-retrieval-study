"""Check every exported rank and document lookup against a completed Task A run."""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from news_ir.data import DocumentStore, read_queries, sha256_file


def validate(index, run_dir, repeat_dir):
    summary = json.loads((run_dir / "manifest.json").read_text())
    repeat = json.loads((repeat_dir / "manifest.json").read_text())
    assert summary["run_sha256"] == sha256_file(run_dir / "run.trec")
    assert summary["run_sha256"] == repeat["run_sha256"] == sha256_file(repeat_dir / "run.trec")
    assert summary["results_sha256"] == sha256_file(run_dir / "results.jsonl")
    assert summary["index_manifest_sha256"] == sha256_file(index / "manifest.json")
    assert summary["query_snapshot_sha256"] == sha256_file(run_dir / "queries.jsonl")
    queries = read_queries(run_dir / "queries.jsonl")
    trec_lines = (run_dir / "run.trec").read_text().splitlines()
    results = [json.loads(line) for line in (run_dir / "results.jsonl").read_text().splitlines()]
    assert len(queries) == len(results) == summary["query_count"]
    offset, unique_ids = 0, set()
    with DocumentStore(index) as store:
        assert summary["corpus_sha256"] == store.manifest["source"]["sha256"]
        for query, result in zip(queries, results, strict=True):
            assert result["query_id"] == query["_id"] and result["query"] == query["text"]
            previous, seen = math.inf, set()
            assert len(result["hits"]) <= summary["top_k"]
            for rank, hit in enumerate(result["hits"], 1):
                assert hit["rank"] == rank and hit["doc_id"] not in seen
                assert math.isfinite(hit["score"]) and hit["score"] <= previous
                expected = f"{query['_id']} Q0 {hit['doc_id']} {rank} {hit['score']:.9g} {summary['run_tag']}"
                assert trec_lines[offset] == expected
                offset += 1
                seen.add(hit["doc_id"])
                unique_ids.add(hit["doc_id"])
                previous = hit["score"]
                doc = store.get(hit["doc_id"])
                assert doc is not None and doc.eligible
        assert offset == len(trec_lines) == summary["total_hits"]
        # Demonstrate body-level lookups without claiming these queries are judged.
        previews = []
        for result in results[:3]:
            if not result["hits"]:
                continue
            hit = result["hits"][0]
            doc = store.get(hit["doc_id"])
            previews.append({"query_id": result["query_id"], "query": result["query"],
                             "top_document_id": doc.doc_id, "title": doc.title})
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": "passed",
        "query_count": len(queries), "ranked_hits_checked": offset,
        "unique_ranked_documents": len(unique_ids),
        "trec_jsonl_agreement": True, "all_ranked_documents_resolved": True,
        "repeat_run_identical": True, "run_sha256": summary["run_sha256"],
        "initial_run_latency_ms": summary["latency_ms"],
        "repeat_run_latency_ms": repeat["latency_ms"],
        "preview_original_queries": previews,
        "notes": ["Correctness checks, not relevance judgments.",
                  "Initial run overlapped integrity checks; repeat run was sequential without those checks.",
                  "Source corpus identity is independently recorded by news-ir verify."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=Path("artifacts/indexes/bm25"))
    parser.add_argument("--run", type=Path, default=Path("artifacts/runs/bm25-original"))
    parser.add_argument("--repeat", type=Path, default=Path("artifacts/runs/bm25-original-repeat"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/task_a_run_validation.json"))
    args = parser.parse_args()
    result = validate(args.index, args.run, args.repeat)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
