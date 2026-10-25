"""Evaluate the complete custom depth-20 pool against unchanged depth-1000 runs."""
import argparse
import json

from news_ir.custom_depth20 import evaluate_depth20_study


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default="artifacts/assessments/custom20-v1")
    parser.add_argument("--assessments", default="annotations/ai_study_v1/assessments.depth20.jsonl")
    parser.add_argument("--seed-assessments", default="annotations/ai_study_v1/assessments.top5.jsonl")
    parser.add_argument("--document-index", default="artifacts/indexes/bm25")
    parser.add_argument("--output", default="artifacts/evaluations/custom20-depth20-v1")
    args = parser.parse_args()
    print(json.dumps(evaluate_depth20_study(args.pool, args.assessments, args.seed_assessments,
                                          args.document_index, args.output), indent=2))
