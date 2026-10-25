"""Download only the pinned E5 weights/tokenizer needed for offline retrieval."""
import argparse
import json

from news_ir.embedding import download_model

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/models/e5-base-v2")
    parser.add_argument("--revision", default="main")
    args = parser.parse_args()
    print(json.dumps(download_model(args.output, revision=args.revision), indent=2))
