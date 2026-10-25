"""Freeze the custom suite and export a reproducible equal-depth article pool."""

import argparse
import json

from news_ir.assessment import prepare_pool


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", default="annotations/custom_queries.draft.jsonl")
    parser.add_argument("--bm25-run", default="artifacts/runs/bm25-custom-draft-depth1000")
    parser.add_argument("--dense-run", default="artifacts/runs/dense-custom-draft")
    parser.add_argument("--document-index", default="artifacts/indexes/bm25")
    parser.add_argument("--output", default="artifacts/assessments/custom20-v1")
    parser.add_argument("--depth", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(prepare_pool(queries_path=args.queries, bm25_run=args.bm25_run, dense_run=args.dense_run,
                                 document_index=args.document_index, output=args.output, depth=args.depth), indent=2))
