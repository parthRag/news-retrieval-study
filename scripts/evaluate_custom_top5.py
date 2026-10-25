"""Evaluate all 20 custom queries after completing the full top-five union."""

import argparse
import json

from news_ir.custom_study import evaluate_top5_study


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default="artifacts/assessments/custom20-v1")
    parser.add_argument("--assessments", default="annotations/ai_study_v1/assessments.top5.jsonl")
    parser.add_argument("--output", default="artifacts/evaluations/custom20-top5-v1")
    args = parser.parse_args()
    print(json.dumps(evaluate_top5_study(args.pool, args.assessments, args.output), indent=2))
