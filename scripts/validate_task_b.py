"""Validate real pilot vectors and compare FAISS search with brute-force cosine."""

import json
from pathlib import Path

import numpy as np

from news_ir.dense import DenseEngine, read_shards
from news_ir.embedding import validate_vectors


def main():
    encodings = Path("artifacts/encodings/e5-pilot")
    config = json.loads((encodings / "config.json").read_text())
    shards, count, _ = read_shards(encodings, config)
    matrix = np.concatenate([np.load(folder / "vectors.npy", allow_pickle=False) for folder, _ in shards])
    validate_vectors(matrix, dimension=768, rows=count)
    examples = []
    with DenseEngine("artifacts/indexes/dense-pilot", allow_partial=True, device="cpu") as engine:
        for doc_id in engine.ids[:3]:
            query = engine.get_document(doc_id).title
            vector = engine.encoder.encode([query], kind="query")[0]
            scores = matrix @ vector
            reference = sorted(range(len(scores)), key=lambda row: (-float(scores[row]), engine.ids[row]))[:10]
            hits = engine.search(query, 10)
            assert [hit.doc_id for hit in hits] == [engine.ids[row] for row in reference]
            assert np.allclose([hit.score for hit in hits], scores[reference], atol=1e-6)
            examples.append({"query": query, "top_doc_id": hits[0].doc_id,
                             "top_title": engine.get_document(hits[0].doc_id).title})
        for doc_id in engine.ids:
            assert engine.get_document(doc_id).eligible
    result = {"status": "passed", "coverage": "pilot", "vectors_checked": count,
              "document_lookups_checked": count, "faiss_vs_brute_force_queries": len(examples),
              "max_unit_norm_error": float(np.max(np.abs(np.linalg.norm(matrix, axis=1) - 1))),
              "examples": examples, "note": "512-article integration pilot; no full-corpus effectiveness claim."}
    Path("artifacts/task_b_pilot_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
