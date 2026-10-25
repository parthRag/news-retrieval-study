"""Measure real E5 throughput before choosing a full-corpus encoding machine."""

import argparse
import json
import time
from pathlib import Path

from news_ir.data import DocumentStore
from news_ir.embedding import E5Encoder


def benchmark(model_dir, document_index, *, count=32, batch_size=4, device="auto", corpus=None):
    if count < 1 or batch_size < 1:
        raise ValueError("count and batch_size must be positive")
    with DocumentStore(document_index, corpus=corpus) as store:
        ids = [row[0] for row in store._db.execute(
            "SELECT doc_id FROM documents WHERE eligible=1 ORDER BY rowid LIMIT ?", (count,))]
        texts = [store.get(doc_id).contents for doc_id in ids]
        encoder = E5Encoder(model_dir, device=device)
        encoder.encode(texts[:1], kind="passage")
        encoder.synchronize()
        start = time.perf_counter()
        for offset in range(0, len(texts), batch_size):
            encoder.encode(texts[offset:offset+batch_size], kind="passage")
        encoder.synchronize()
        seconds = time.perf_counter() - start
        rate = len(texts) / seconds
        return {"documents": len(texts), "batch_size": batch_size, "seconds": seconds,
                "documents_per_second": rate, "runtime": encoder.runtime,
                "projected_full_corpus_hours": store.manifest["documents"]["indexed"] / rate / 3600,
                "sample_policy": "First eligible source articles; one unmeasured warmup article",
                "projection_limitations": "Encoding-only extrapolation; excludes startup, transfer, checkpoint/index costs and variability"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default="artifacts/models/e5-base-v2")
    parser.add_argument("--document-index", default="artifacts/indexes/bm25")
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--corpus")
    parser.add_argument("--output", default="artifacts/dense_benchmark.json")
    args = parser.parse_args()
    result = benchmark(args.model_dir, args.document_index, count=args.count,
                       batch_size=args.batch_size, device=args.device, corpus=args.corpus)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
