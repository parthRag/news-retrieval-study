"""Measure the fixed-k hybrid against the original 57-query baselines."""

import argparse
import json

from news_ir.fusion import evaluate_fusion


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", dest="queries_path", default="queries.jsonl")
    parser.add_argument("--qrels", dest="qrels_path", default="qrel.jsonl")
    parser.add_argument("--bm25-run", default="artifacts/runs/bm25-original-benchmark")
    parser.add_argument("--dense-run", default="artifacts/runs/dense-original")
    parser.add_argument("--fusion-run", default="artifacts/runs/rrf-original-k60")
    parser.add_argument("--document-index", default="artifacts/indexes/bm25")
    parser.add_argument("--output", default="artifacts/evaluations/rrf-original-57")
    print(json.dumps(evaluate_fusion(**vars(parser.parse_args())), indent=2))
