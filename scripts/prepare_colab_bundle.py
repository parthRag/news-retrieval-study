"""Package source and compact document metadata, excluding corpus/model/index binaries."""

import json
import zipfile
from pathlib import Path

from news_ir.data import sha256_file
from news_ir.embedding import read_model_spec


def prepare_bundle(output, *, extra_files=()):
    root = Path(__file__).resolve().parents[1]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    model = read_model_spec(root / "artifacts/models/e5-base-v2")
    source = json.loads((root / "artifacts/indexes/bm25/manifest.json").read_text())
    info = {"source_sha256": source["source"]["sha256"], "source_bytes": source["source"]["bytes"],
            "eligible_documents": source["documents"]["indexed"], "model_revision": model["revision"],
            "model_files": model["files"], "query_sha256": sha256_file(root / "annotations/custom_queries.draft.jsonl"),
            "corpus_repository": "liuqi6777/trec-news"}
    files = [(p, str(p.relative_to(root))) for p in (root / "src/news_ir").glob("*.py")]
    files += [(root / name, name) for name in ["scripts/download_e5.py", "scripts/benchmark_dense.py",
                                              "annotations/custom_queries.draft.jsonl"]]
    files += [(root / "artifacts/indexes/bm25" / name, "corpus_metadata/" + name)
              for name in ["manifest.json", "documents.sqlite3"]]
    files += [(root / name, name) for name in extra_files]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for path, name in files:
            archive.write(path, name)
        archive.writestr("bundle.json", json.dumps(info, indent=2) + "\n")
    return {"bundle": str(output), "bytes": output.stat().st_size,
            "sha256": sha256_file(output), "contains_corpus": False, "contains_model_weights": False}


def main():
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(prepare_bundle(root / "artifacts/bundles/news_ir_colab.zip"), indent=2))


if __name__ == "__main__":
    main()
