"""Isolated FAISS process: never load PyTorch/JVM into this native-library runtime."""

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

import faiss
import numpy as np


def build(encodings, output):
    root = Path(encodings)
    config = json.loads((root / "config.json").read_text())
    index = faiss.IndexFlatIP(config["model"]["dimension"])
    for shard in sorted((root / "shards").glob("shard-*")):
        vectors = np.load(shard / "vectors.npy", allow_pickle=False)
        index.add(vectors)
    faiss.write_index(index, output)
    return {"count": index.ntotal, "dimension": index.d, "faiss_version": importlib.metadata.version("faiss-cpu")}


def serve(root):
    root = Path(root)
    faiss.omp_set_num_threads(4)
    index = faiss.read_index(str(root / "vectors.faiss"))
    ids = [json.loads(line) for line in (root / "ids.jsonl").read_text().splitlines()]
    if index.ntotal != len(ids) or index.metric_type != faiss.METRIC_INNER_PRODUCT:
        raise ValueError("Invalid FAISS index/ID mapping")
    print(json.dumps({"ready": True, "count": index.ntotal, "dimension": index.d}), flush=True)
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if message["method"] == "close":
                print(json.dumps({"closed": True}), flush=True)
                return
            if message["method"] != "search":
                raise ValueError("Unknown FAISS worker operation")
            vector = np.asarray([message["vector"]], dtype=np.float32)
            if vector.shape != (1, index.d) or not np.isfinite(vector).all():
                raise ValueError("Invalid query vector")
            k = message["top_k"]
            if type(k) is not int or not 1 <= k <= 10000:
                raise ValueError("Invalid top_k")
            count = min(k, index.ntotal)
            requested = min(count + 1, index.ntotal)
            while True:
                scores, rows = index.search(vector, requested)
                if requested == index.ntotal or scores[0, count - 1] != scores[0, -1]:
                    break
                requested = min(index.ntotal, requested * 2)
            candidates = [(float(score), ids[int(row)]) for score, row in zip(scores[0], rows[0], strict=True)]
            candidates.sort(key=lambda item: (-item[0], item[1]))
            print(json.dumps({"hits": candidates[:count]}), flush=True)
        except Exception as exc:
            print(json.dumps({"error": str(exc)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index")
    parser.add_argument("--build")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.build:
        print(json.dumps(build(args.build, args.output)))
    else:
        serve(args.index)
