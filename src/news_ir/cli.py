"""Command-line entry point for lexical and dense retrieval."""

import argparse
import json
import logging
import sys


DEFAULT_INDEX = "artifacts/indexes/bm25"


def parser():
    root = argparse.ArgumentParser(description="News retrieval: lexical engine and experiment exports")
    sub = root.add_subparsers(dest="command", required=True)
    index = sub.add_parser("index", help="Build a fresh BM25 index and document offset store")
    index.add_argument("--corpus", default="corpus.jsonl")
    index.add_argument("--output", default=DEFAULT_INDEX)
    index.add_argument("--threads", type=int, default=4)
    index.add_argument("--batch-size", type=int, default=256)
    search = sub.add_parser("search", help="Retrieve articles for a natural-language query")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--snippet-length", type=int, default=400)
    doc = sub.add_parser("document", help="Read a full source article by its exact ID")
    doc.add_argument("doc_id")
    analyze = sub.add_parser("analyze", help="Inspect the exact query tokens used by BM25")
    analyze.add_argument("text")
    run = sub.add_parser("run", help="Export a JSONL query suite as TREC and JSONL runs")
    run.add_argument("--queries", default="queries.jsonl")
    run.add_argument("--output", required=True)
    run.add_argument("--top-k", type=int, default=1000)
    run.add_argument("--run-tag")
    verify = sub.add_parser("verify", help="Verify source hash, counts, offsets and analyzer")
    verify.add_argument("--sample-size", type=int, default=1000)
    for child in (search, doc, analyze, run, verify):
        child.add_argument("--index", default=DEFAULT_INDEX)
        child.add_argument("--corpus", help="Relocated copy of the exact indexed corpus")
    encode = sub.add_parser("encode", help="Encode shared eligible articles in resumable E5 shards")
    encode.add_argument("--document-index", default=DEFAULT_INDEX)
    encode.add_argument("--model-dir", default="artifacts/models/e5-base-v2")
    encode.add_argument("--output", default="artifacts/encodings/e5-base-v2")
    encode.add_argument("--corpus")
    encode.add_argument("--batch-size", type=int, default=8)
    encode.add_argument("--shard-size", type=int, default=1024)
    encode.add_argument("--limit", type=int, help="Explicit pilot limit, never labeled full coverage")
    encode.add_argument("--resume", action="store_true")
    encode.add_argument("--time-budget-seconds", type=float,
                        help="Stop after a committed shard when this encoding time elapses; resume later")
    encode.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    dense_index = sub.add_parser("dense-index", help="Build exact FAISS cosine search from encoding shards")
    dense_index.add_argument("--encodings", default="artifacts/encodings/e5-base-v2")
    dense_index.add_argument("--output", default="artifacts/indexes/dense")
    dense_index.add_argument("--corpus")
    dense_search = sub.add_parser("dense-search", help="Search the dense index with the same E5 model")
    dense_search.add_argument("query")
    dense_search.add_argument("--index", default="artifacts/indexes/dense")
    dense_search.add_argument("--top-k", type=int, default=5)
    dense_search.add_argument("--corpus")
    dense_search.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    for child in (dense_index, dense_search):
        child.add_argument("--document-index", default=DEFAULT_INDEX)
        child.add_argument("--model-dir", default="artifacts/models/e5-base-v2")
        child.add_argument("--allow-partial", action="store_true")
    run.add_argument("--engine", choices=["bm25", "dense"], default="bm25")
    run.add_argument("--document-index", default=DEFAULT_INDEX)
    run.add_argument("--model-dir", default="artifacts/models/e5-base-v2")
    run.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    run.add_argument("--allow-partial", action="store_true")
    run.set_defaults(index=None)
    evaluate = sub.add_parser("evaluate", help="Evaluate paired full-corpus runs against supplied original qrels")
    evaluate.add_argument("--queries", default="queries.jsonl")
    evaluate.add_argument("--qrels", default="qrel.jsonl")
    evaluate.add_argument("--bm25-run", default="artifacts/runs/bm25-original-benchmark")
    evaluate.add_argument("--dense-run", default="artifacts/runs/dense-original")
    evaluate.add_argument("--document-index", default=DEFAULT_INDEX)
    evaluate.add_argument("--output", default="artifacts/evaluations/original-57")
    evaluate.add_argument("--bootstrap-samples", type=int, default=10000)
    evaluate.add_argument("--seed", type=int, default=20261024)
    fuse = sub.add_parser("fuse", help="Reciprocal-rank fusion of saved full-corpus BM25 and dense runs")
    fuse.add_argument("--queries", default="queries.jsonl")
    fuse.add_argument("--bm25-run", default="artifacts/runs/bm25-original-benchmark")
    fuse.add_argument("--dense-run", default="artifacts/runs/dense-original")
    fuse.add_argument("--document-index", default=DEFAULT_INDEX)
    fuse.add_argument("--output", required=True)
    fuse.add_argument("--k", type=int, default=60)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    try:
        if args.command == "fuse":
            from .fusion import fuse_runs
            result = fuse_runs(queries_path=args.queries, bm25_run=args.bm25_run, dense_run=args.dense_run,
                               document_index=args.document_index, output=args.output, k=args.k)
        elif args.command == "evaluate":
            from .benchmark import compare_benchmark
            result = compare_benchmark(queries_path=args.queries, qrels_path=args.qrels,
                                       bm25_run=args.bm25_run, dense_run=args.dense_run,
                                       document_index=args.document_index, output=args.output,
                                       bootstrap_samples=args.bootstrap_samples, seed=args.seed)
        elif args.command == "encode":
            from .dense import encode_corpus
            result = encode_corpus(args.document_index, args.model_dir, args.output, corpus=args.corpus,
                                   batch_size=args.batch_size, shard_size=args.shard_size, limit=args.limit,
                                   resume=args.resume, device=args.device,
                                   time_budget_seconds=args.time_budget_seconds)
        elif args.command == "dense-index":
            from .dense import build_dense_index
            result = build_dense_index(args.encodings, args.output, document_index=args.document_index,
                                        model_dir=args.model_dir, corpus=args.corpus, allow_partial=args.allow_partial)
        elif args.command == "dense-search":
            from .dense import DenseEngine
            with DenseEngine(args.index, document_index=args.document_index, model_dir=args.model_dir,
                             corpus=args.corpus, device=args.device, allow_partial=args.allow_partial) as engine:
                import time
                start = time.perf_counter()
                hits = engine.search(args.query, args.top_k)
                result = {"query": args.query, "coverage": engine.manifest["coverage"],
                          "search_latency_ms": (time.perf_counter() - start) * 1000,
                          "hits": [{**hit.to_dict(), "title": engine.get_document(hit.doc_id).title,
                                    "snippet": engine.get_document(hit.doc_id).text[:400]} for hit in hits]}
        elif args.command == "index":
            from .indexing import build_index
            result = build_index(args.corpus, args.output, threads=args.threads, batch_size=args.batch_size)
        elif args.command == "run":
            from .experiments import run_queries
            run_index = args.index or (DEFAULT_INDEX if args.engine == "bm25" else "artifacts/indexes/dense")
            result = run_queries(run_index, args.queries, args.output, top_k=args.top_k,
                                 run_tag=args.run_tag, corpus=args.corpus, engine_type=args.engine,
                                 document_index=args.document_index, model_dir=args.model_dir,
                                 device=args.device, allow_partial=args.allow_partial)
        elif args.command == "verify":
            from .experiments import verify_index
            result = verify_index(args.index, corpus=args.corpus, sample_size=args.sample_size)
        else:
            from .retrieval import BM25Engine
            with BM25Engine(args.index, corpus=args.corpus) as engine:
                if args.command == "analyze":
                    result = {"text": args.text, "tokens": engine.analyze(args.text)}
                elif args.command == "document":
                    doc = engine.get_document(args.doc_id)
                    if doc is None:
                        raise ValueError(f"Unknown document ID: {args.doc_id}")
                    result = doc.to_dict()
                else:
                    if args.snippet_length < 0:
                        raise ValueError("snippet-length must be nonnegative")
                    import time
                    start = time.perf_counter()
                    hits = engine.search(args.query, args.top_k)
                    elapsed = (time.perf_counter() - start) * 1000
                    enriched = []
                    for hit in hits:
                        doc = engine.get_document(hit.doc_id)
                        if doc is None:
                            raise ValueError(f"Ranked document missing from store: {hit.doc_id}")
                        enriched.append({**hit.to_dict(), "title": doc.title,
                                         "snippet": doc.text[:args.snippet_length]})
                    result = {"query": args.query, "analyzed_terms": engine.analyze(args.query),
                              "search_latency_ms": elapsed, "hits": enriched}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
