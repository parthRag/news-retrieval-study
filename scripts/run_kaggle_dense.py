"""Kaggle GPU handoff: verified downloads, resumable full encoding, and export.

Run through notebooks/News_IR_Kaggle_Encoding.ipynb. Only the standard library
is imported until the uploaded project bundle has been unpacked.
"""

import argparse
import json
import logging
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def find_bundle(input_root):
    root = Path(input_root)
    candidates = sorted(root.rglob("news_ir_kaggle.zip"))
    # Kaggle may automatically unpack a Dataset ZIP during upload.
    candidates += sorted(p.parent for p in root.rglob("bundle.json")
                         if (p.parent / "scripts/run_kaggle_dense.py").is_file())
    if len(candidates) != 1:
        raise ValueError(f"Expected one attached project bundle, found {len(candidates)}. "
                         "Attach the private project Dataset or set --bundle explicitly.")
    return candidates[0]


def unpack_checked(archive_path, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if (name.is_absolute() or ".." in name.parts or "\\" in entry.filename
                    or stat.S_ISLNK(entry.external_attr >> 16)
                    or not (destination / entry.filename).resolve().is_relative_to(destination)):
                raise ValueError(f"Unsafe archive member: {entry.filename}")
        archive.extractall(destination)


def relocate_metadata(metadata, corpus, bundle):
    from news_ir.data import sha256_file

    corpus, metadata = Path(corpus), Path(metadata)
    if corpus.stat().st_size != bundle["source_bytes"] or sha256_file(corpus) != bundle["source_sha256"]:
        raise ValueError("Downloaded corpus differs from the BM25 source; refusing to encode")
    path = metadata / "manifest.json"
    manifest = json.loads(path.read_text())
    if (manifest["source"]["sha256"] != bundle["source_sha256"]
            or manifest["documents"]["indexed"] != bundle["eligible_documents"]):
        raise ValueError("Bundled document metadata disagrees with bundle identity")
    manifest["source"]["path"] = str(corpus.resolve())
    manifest["source"]["mtime_ns"] = corpus.stat().st_mtime_ns
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def restore_checkpoint(archive, encodings):
    """Restore through a staging directory, leaving existing local progress alone."""
    encodings = Path(encodings)
    if (encodings / "config.json").is_file():
        print("Using existing writable checkpoints; attached resume archive is not needed.", flush=True)
        return
    if encodings.exists():
        raise FileExistsError("Encoding destination exists without a valid config")
    encodings.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".restoring-", dir=encodings.parent))
    try:
        archive = Path(archive)
        if archive.is_dir():
            source_directory = archive if (archive / "config.json").is_file() else archive / "encodings"
            shutil.copytree(source_directory, staging / "encodings")
        else:
            unpack_checked(archive, staging)
        source = staging / "encodings"
        if not (source / "config.json").is_file() or not (source / "shards").is_dir():
            raise ValueError("Resume archive must contain encodings/config.json and encodings/shards")
        from news_ir.dense import read_shards
        read_shards(source, json.loads((source / "config.json").read_text()))
        source.rename(encodings)
    finally:
        shutil.rmtree(staging)


def export_checkpoint(encodings, output):
    """Include only committed shards, excluding abandoned in-flight directories."""
    encodings, output = Path(encodings), Path(output)
    temporary = output.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.write(encodings / "config.json", "encodings/config.json")
        archive.writestr("encodings/shards/", "")
        if (encodings / "progress.json").exists():
            archive.write(encodings / "progress.json", "encodings/progress.json")
        for folder in sorted((encodings / "shards").glob("shard-*")):
            for name in ("manifest.json", "ids.jsonl", "vectors.npy"):
                path = folder / name
                archive.write(path, "encodings/" + str(path.relative_to(encodings)))
    temporary.replace(output)
    return output


def run_job(args):
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA GPU allocated. Enable GPU in Kaggle Settings before starting.")
    print(f"Using cuda:0: {torch.cuda.get_device_name(0)} (one GPU)", flush=True)
    workspace, output = Path(args.workspace).resolve(), Path(args.output).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    payload = Path(tempfile.mkdtemp(prefix="payload-", dir=workspace))
    bundle_path = Path(args.bundle) if args.bundle else find_bundle(args.input_root)
    if bundle_path.is_dir():
        shutil.copytree(bundle_path, payload, dirs_exist_ok=True)
    else:
        unpack_checked(bundle_path, payload)
    sys.path.insert(0, str(payload / "src"))
    # Child processes (isolated FAISS and benchmark) must use this same source.
    os.environ["PYTHONPATH"] = str(payload / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("USE_TF", "0")
    bundle = json.loads((payload / "bundle.json").read_text())

    from huggingface_hub import hf_hub_download
    from news_ir.data import sha256_file
    from news_ir.embedding import download_model
    from news_ir.dense import build_dense_index, encode_corpus, read_shards, write_json
    from news_ir.experiments import run_queries

    metadata = payload / "corpus_metadata"
    queries = payload / "annotations/custom_queries.draft.jsonl"
    if sha256_file(queries) != bundle["query_sha256"]:
        raise ValueError("Draft query file differs from the bundled identity")
    print("Downloading/verifying the corpus (about 2.45 GB); no browser corpus upload needed.", flush=True)
    corpus = Path(hf_hub_download(repo_id=bundle["corpus_repository"], repo_type="dataset",
                                filename="corpus.jsonl", cache_dir=workspace / "corpus-cache", token=False))
    relocate_metadata(metadata, corpus, bundle)
    model_dir = workspace / "e5-base-v2"
    model = download_model(model_dir, revision=bundle["model_revision"])
    if model["files"] != bundle["model_files"]:
        raise ValueError("Downloaded model/tokenizer differs from the tested local model")

    job = output / "news_ir_job"
    job.mkdir(exist_ok=True)
    encodings = job / "encodings"
    if args.resume_archive:
        restore_checkpoint(args.resume_archive, encodings)
    # A subprocess releases its model/GPU allocation before the full encoder starts.
    subprocess.run([sys.executable, str(payload / "scripts/benchmark_dense.py"),
                    "--document-index", str(metadata), "--model-dir", str(model_dir),
                    "--corpus", str(corpus), "--device", "cuda", "--count", "128",
                    "--batch-size", str(args.batch_size), "--output", str(job / "gpu_benchmark.json")], check=True)
    print("Starting/resuming the full eligible corpus. The budget stops only after a saved shard.", flush=True)
    try:
        progress = encode_corpus(metadata, model_dir, encodings, corpus=corpus, device="cuda",
                                 batch_size=args.batch_size, shard_size=2048,
                                 resume=(encodings / "config.json").exists(),
                                 time_budget_seconds=args.time_budget_hours * 3600)
    finally:
        # Also preserve committed progress on a normal exception or Ctrl-C, when possible.
        if (encodings / "config.json").is_file():
            checkpoint = export_checkpoint(encodings, output / "dense-checkpoints.zip")
            print(f"Checkpoint export: {checkpoint}", flush=True)
    config = json.loads((encodings / "config.json").read_text())
    _, count, _ = read_shards(encodings, config)
    if config["coverage"] != "full" or config["target_documents"] != bundle["eligible_documents"]:
        raise ValueError("This job must select the entire shared eligible corpus")
    summary = {"completed": progress["completed"], "encoded_documents": count,
               "target_documents": bundle["eligible_documents"], "source_sha256": bundle["source_sha256"],
               "model_revision": bundle["model_revision"], "coverage": "full", "progress": progress,
               "checkpoint_archive": str(output / "dense-checkpoints.zip"),
               "evaluation": "Draft rankings only; human judgments and relevance metrics are still pending"}
    if not progress["completed"]:
        write_json(output / "job_summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)
        print("Budget reached. Save this version's outputs, then resume from dense-checkpoints.zip.", flush=True)
        return summary

    dense = job / "indexes/dense"
    if not dense.exists():
        build_dense_index(encodings, dense, document_index=metadata, model_dir=model_dir, corpus=corpus)
    run = job / "runs/dense-custom-draft"
    if not run.exists():
        run_queries(dense, queries, run, engine_type="dense", document_index=metadata, model_dir=model_dir,
                    corpus=corpus, device="cuda", top_k=1000, run_tag="e5-kaggle-draft")
    # Check even previously completed outputs before exporting them.
    index_manifest = json.loads((dense / "manifest.json").read_text())
    run_manifest = json.loads((run / "manifest.json").read_text())
    if (index_manifest["source_sha256"] != bundle["source_sha256"]
            or index_manifest["model"] != config["model"]
            or index_manifest["indexed_documents"] != bundle["eligible_documents"]
            or run_manifest["query_source_sha256"] != bundle["query_sha256"]
            or run_manifest["index_manifest_sha256"] != sha256_file(dense / "manifest.json")
            or run_manifest["coverage"] != "full"):
        raise ValueError("Existing index/run does not match this complete job")
    for folder, files in ((dense, index_manifest["files"]),
                          (run, {"run.trec": run_manifest["run_sha256"],
                                 "results.jsonl": run_manifest["results_sha256"]})):
        for name, digest in files.items():
            if sha256_file(folder / name) != digest:
                raise ValueError(f"Export identity check failed: {folder / name}")
    results = output / "dense-results.zip"
    temporary = results.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
        for folder in (dense, run):
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, str(path.relative_to(job)))
        archive.write(job / "gpu_benchmark.json", "gpu_benchmark_kaggle.json")
    temporary.replace(results)
    summary.update(results_archive=str(results), results_sha256=sha256_file(results),
                   query_count=run_manifest["query_count"], total_hits=run_manifest["total_hits"])
    write_json(output / "job_summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", help="Uploaded ZIP or its automatically extracted Dataset directory")
    parser.add_argument("--input-root", default="/kaggle/input")
    parser.add_argument("--workspace", default="/kaggle/temp/news_ir_task_b")
    parser.add_argument("--output", default="/kaggle/working")
    parser.add_argument("--resume-archive", help="Previous dense-checkpoints.zip or its extracted directory")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--time-budget-hours", type=float, default=6,
                        help="Encoding-only budget; allow additional time for setup, export, and indexing")
    args = parser.parse_args(argv)
    if args.batch_size < 1 or not math.isfinite(args.time_budget_hours) or args.time_budget_hours <= 0:
        parser.error("Batch size and finite time budget must be positive")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    run_job(args)


if __name__ == "__main__":
    main()
