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
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    index = faiss.IndexFlatIP(config["model"]["dimension"])
    for shard in sorted((root / "shards").glob("shard-*")):
        vectors = np.load(shard / "vectors.npy", allow_pickle=False)
        index.add(vectors)
    # Python file I/O also supports Windows paths outside the system code page.
    with Path(output).open("wb") as stream:
        faiss.write_index(index, faiss.PyCallbackIOWriter(stream.write))
    return {"count": index.ntotal, "dimension": index.d, "faiss_version": importlib.metadata.version("faiss-cpu")}


def serve(root):
    root = Path(root)
    faiss.omp_set_num_threads(4)
    with (root / "vectors.faiss").open("rb") as stream:
        index = faiss.read_index(faiss.PyCallbackIOReader(stream.read))
    ids = [json.loads(line) for line in (root / "ids.jsonl").read_text(encoding="utf-8").splitlines()]
    if index.ntotal != len(ids) or index.metric_type != faiss.METRIC_INNER_PRODUCT:
        raise ValueError("Invalid FAISS index/ID mapping")
    print(json.dumps({"ready": True, "count": index.ntotal, "dimension": index.d}), flush=True)
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if message["method"] == "close":
                print(json.dumps({"closed": True}), flush=True)
                return
            if message["method"] not in {"search", "search_batch"}:
                raise ValueError("Unknown FAISS worker operation")
            batched = message["method"] == "search_batch"
            vector = np.asarray(message["vectors"] if batched else [message["vector"]], dtype=np.float32)
            if vector.ndim != 2 or not 1 <= len(vector) <= 64 or vector.shape[1] != index.d or not np.isfinite(vector).all():
                raise ValueError("Invalid query vector")
            k = message["top_k"]
            if type(k) is not int or not 1 <= k <= 10000:
                raise ValueError("Invalid top_k")
            count = min(k, index.ntotal)
            requested = min(count + 1, index.ntotal)
            scores, rows = index.search(vector, requested)
            batches = []
            for i in range(len(vector)):
                row_scores, row_ids, take = scores[i], rows[i], requested
                while take != index.ntotal and row_scores[count - 1] == row_scores[-1]:
                    take = min(index.ntotal, take * 2)
                    extra_scores, extra_ids = index.search(vector[i:i+1], take)
                    row_scores, row_ids = extra_scores[0], extra_ids[0]
                candidates = [(float(score), ids[int(row)]) for score, row in zip(row_scores, row_ids, strict=True)]
                candidates.sort(key=lambda item: (-item[0], item[1]))
                batches.append(candidates[:count])
            print(json.dumps({"batches": batches} if batched else {"hits": batches[0]}), flush=True)
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
