"""Validate a returned full-corpus index and its rankings against local assets.

The FAISS/NumPy audit runs in a separate process from E5/PyTorch so macOS never
loads the two incompatible OpenMP runtimes into one process.
"""

import argparse
import json
import math
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def vector_audit(index_dir):
    import faiss
    import numpy as np

    root = Path(index_dir)
    request = json.load(sys.stdin)
    index = faiss.read_index(str(root / "vectors.faiss"))
    if not isinstance(index, faiss.IndexFlatIP) or index.metric_type != faiss.METRIC_INNER_PRODUCT:
        raise ValueError("Expected exact IndexFlatIP cosine index")
    assert index.ntotal == request["count"] and index.d == request["dimension"]
    probes = request["probes"]
    queries = np.asarray([p["vector"] for p in probes], dtype=np.float32)
    scores = np.empty((index.ntotal, len(probes)), dtype=np.float32)
    max_error = 0.0
    for offset in range(0, index.ntotal, 8192):
        block = index.reconstruct_n(offset, min(8192, index.ntotal - offset))
        if not np.isfinite(block).all():
            raise ValueError("Non-finite document vector")
        max_error = max(max_error, float(np.max(np.abs(np.linalg.norm(block, axis=1) - 1))))
        scores[offset:offset + len(block)] = block @ queries.T
    if max_error > 1e-4:
        raise ValueError("Document embeddings are not L2-normalized")
    ids = [json.loads(line) for line in (root / "ids.jsonl").read_text().splitlines()]
    positions = {doc_id: row for row, doc_id in enumerate(ids)}
    checks = []
    for number, probe in enumerate(probes):
        column = scores[:, number]
        # Independent full-corpus NumPy ranking; near-equal floating scores can differ by backend.
        best = sorted(range(index.ntotal), key=lambda row: (-float(column[row]), ids[row]))[:5]
        reference = [ids[row] for row in best]
        expected = [hit["doc_id"] for hit in probe["hits"]]
        error = max(abs(float(column[positions[hit["doc_id"]]]) - hit["score"]) for hit in probe["hits"])
        cutoff = float(column[best[-1]])
        if error > 1e-5 or any(column[positions[doc_id]] < cutoff - 1e-5 for doc_id in expected):
            raise ValueError("FAISS results disagree with independent full-corpus cosine calculation")
        checks.append({"query_id": probe["query_id"], "exact_top5_order_agreement": reference == expected,
                       "max_score_error": error, "reference_top5": reference})
    return {"vectors_checked": index.ntotal, "dimension": index.d, "faiss_type": type(index).__name__,
            "max_unit_norm_error": max_error, "independent_cosine_checks": checks}


def verify(args):
    from news_ir.data import DocumentStore, read_queries, sha256_file
    from news_ir.dense import DenseEngine
    from news_ir.embedding import read_model_spec

    index, run = Path(args.index), Path(args.run)
    summary = json.loads(Path(args.summary).read_text())
    manifest = json.loads((index / "manifest.json").read_text())
    run_manifest = json.loads((run / "manifest.json").read_text())
    assert summary["completed"] is True and summary["coverage"] == manifest["coverage"] == "full"
    assert sha256_file(args.archive) == summary["results_sha256"]
    for name, digest in manifest["files"].items():
        assert Path(name).name == name and sha256_file(index / name) == digest, name
    for name, key in (("run.trec", "run_sha256"), ("results.jsonl", "results_sha256"),
                      ("queries.jsonl", "query_snapshot_sha256")):
        assert sha256_file(run / name) == run_manifest[key], name
    assert sha256_file(index / "manifest.json") == run_manifest["index_manifest_sha256"]
    assert manifest["model"] == read_model_spec(args.model_dir) == run_manifest["retrieval_config"]["model"]
    assert manifest["model"]["revision"] == summary["model_revision"]
    assert run_manifest["engine"] == manifest["engine"] == "e5-cosine"
    assert run_manifest["coverage"] == "full"
    assert run_manifest["query_source_sha256"] == sha256_file(args.queries)
    queries = read_queries(args.queries)
    assert queries == read_queries(run / "queries.jsonl")
    ids = [json.loads(line) for line in (index / "ids.jsonl").read_text().splitlines()]
    with DocumentStore(args.document_index) as store:
        assert sha256_file(store.corpus) == manifest["source_sha256"] == summary["source_sha256"] == run_manifest["corpus_sha256"]
        expected_ids = [row[0] for row in store._db.execute(
            "SELECT doc_id FROM documents WHERE eligible=1 ORDER BY rowid")]
        assert ids == expected_ids, "Dense ID order/eligibility differs from BM25"
        count = len(ids)
        assert count == len(set(ids)) == manifest["indexed_documents"] == manifest["target_documents"]
        assert count == store.manifest["documents"]["indexed"] == summary["encoded_documents"] == summary["target_documents"]
        assert manifest["source_bytes"] == store.corpus.stat().st_size
        eligible = set(ids)
        results = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
        assert len(results) == len(queries) == summary["query_count"] == run_manifest["query_count"]
        trec = (run / "run.trec").read_text().splitlines()
        line_number, lookup_ids = 0, set(random.Random(42).sample(ids, min(1000, count)))
        for query, result in zip(queries, results, strict=True):
            assert (result["query_id"], result["query"]) == (query["_id"], query["text"])
            hits = result["hits"]
            assert len(hits) == min(run_manifest["top_k"], count)
            assert len({hit["doc_id"] for hit in hits}) == len(hits)
            previous = math.inf
            for rank, hit in enumerate(hits, 1):
                assert hit["doc_id"] in eligible and hit["rank"] == rank
                assert math.isfinite(hit["score"]) and -1.00001 <= hit["score"] <= 1.00001
                assert hit["score"] <= previous
                previous = hit["score"]
                parts = trec[line_number].split()
                assert parts[:4] == [query["_id"], "Q0", hit["doc_id"], str(rank)]
                assert abs(float(parts[4]) - hit["score"]) <= 1e-8 and parts[5] == run_manifest["run_tag"]
                line_number += 1
            lookup_ids.update(hit["doc_id"] for hit in hits[:20])
        assert line_number == len(trec) == run_manifest["total_hits"] == summary["total_hits"]
        for doc_id in lookup_ids:
            assert store.get(doc_id).eligible
    print(f"Verified archive, source/model identity, all {count} IDs and {line_number} hits", flush=True)
    probes, examples = [], []
    # First query in each pre-existing category, chosen without observing rankings.
    drafts = [json.loads(line) for line in Path(args.queries).read_text().splitlines()]
    seen = set()
    selected = []
    for row in drafts:
        if row["category"] not in seen:
            selected.append(row)
            seen.add(row["category"])
    with DenseEngine(index, document_index=args.document_index, model_dir=args.model_dir, device="cpu") as engine:
        for query in selected:
            hits = engine.search(query["text"], 5)
            assert hits == engine.search(query["text"], 5), "Local repeated search changed"
            vector = engine.encoder.encode([query["text"]], kind="query")[0]
            probes.append({"query_id": query["_id"], "vector": vector.tolist(),
                           "hits": [hit.to_dict() for hit in hits]})
            examples.append({"query_id": query["_id"], "query": query["text"],
                             "hits": [{**hit.to_dict(), "title": engine.get_document(hit.doc_id).title} for hit in hits]})
        local_runtime = engine.encoder.runtime
    child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--vector-audit", str(index)],
                           input=json.dumps({"count": count, "dimension": manifest["model"]["dimension"],
                                             "probes": probes}), text=True, capture_output=True, check=True)
    vector_checks = json.loads(child.stdout)
    report = {"status": "passed", "verified_at_utc": datetime.now(timezone.utc).isoformat(), "coverage": "full",
              "archive_sha256": summary["results_sha256"], "corpus_sha256": summary["source_sha256"],
              "model_revision": summary["model_revision"], "ordered_document_ids_checked": count,
              "document_lookups_checked": len(lookup_ids), "query_count": len(queries),
              "ranking_hits_checked": line_number, "vector_checks": vector_checks,
              "kaggle_encoding_seconds": summary["progress"]["session_seconds"],
              "kaggle_runtime": summary["progress"]["runtime"], "local_query_runtime": local_runtime,
              "local_search_examples": examples,
              "evaluation": "Integrity and mathematical integration checks only; human relevance labels and effectiveness metrics pending"}
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "passed", "report": str(Path(args.output).resolve()),
                      "documents": count, "hits": line_number, "vector_checks": vector_checks}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vector-audit", help=argparse.SUPPRESS)
    parser.add_argument("--archive", default="dense-results.zip")
    parser.add_argument("--summary", default="job_summary.json")
    parser.add_argument("--index", default="artifacts/indexes/dense")
    parser.add_argument("--run", default="artifacts/runs/dense-custom-draft")
    parser.add_argument("--document-index", default="artifacts/indexes/bm25")
    parser.add_argument("--model-dir", default="artifacts/models/e5-base-v2")
    parser.add_argument("--queries", default="annotations/custom_queries.draft.jsonl")
    parser.add_argument("--output", default="artifacts/task_b_full_validation.json")
    args = parser.parse_args()
    if args.vector_audit:
        print(json.dumps(vector_audit(args.vector_audit)))
    else:
        verify(args)
