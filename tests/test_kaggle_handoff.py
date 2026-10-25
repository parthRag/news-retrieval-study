"""Cloud handoff tests use local fixtures, never Kaggle credentials or a GPU claim."""

import ast
import importlib.util
import ensurepip
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from news_ir.data import DocumentStore, sha256_file
from news_ir.dense import encode_corpus, read_shards
from test_dense import FixtureEncoder


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kaggle_driver", ROOT / "scripts/run_kaggle_dense.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def test_notebook_is_executable_and_uses_background_safe_inputs():
    notebook = json.loads((ROOT / "notebooks/News_IR_Kaggle_Encoding.ipynb").read_text())
    code = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            ast.parse(source)
            assert cell["execution_count"] is None and not cell["outputs"]
            code.append(source)
    source = "\n".join(code)
    for required in ["/kaggle/input", "RESUME_ARCHIVE", "--resume-archive", "--time-budget-hours",
                     "GPU_PYTHON", "torch==2.9.1", "cu126", "x@x", "594589"]:
        assert required in source
    assert "files.upload" not in source and "--limit" not in source


def test_setup_bypasses_ensurepip_and_bootstraps_before_installing(monkeypatch, tmp_path):
    """Execute the actual setup cell without remote package installs or a GPU."""
    import urllib.request

    notebook = json.loads((ROOT / "notebooks/News_IR_Kaggle_Encoding.ipynb").read_text())
    source = next("".join(cell["source"]) for cell in notebook["cells"]
                  if cell["cell_type"] == "code" and '"-m", "venv"' in "".join(cell["source"]))
    commands, downloads = [], []
    def record(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(subprocess, "run", record)
    monkeypatch.setattr(urllib.request, "urlretrieve", lambda url, path: downloads.append((url, path)))
    monkeypatch.setenv("USE_TF", "0")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    # Relocate only the notebook's temporary root for execution in the local sandbox.
    source = source.replace('/kaggle/temp', str(tmp_path))
    context = {}
    exec(compile(source, "kaggle_dependency_cell", "exec"), context)
    assert commands[0][1:4] == ["-m", "venv", "--without-pip"]
    assert downloads[0][0] == "https://bootstrap.pypa.io/get-pip.py"
    assert commands[1] == [context["GPU_PYTHON"], str(downloads[0][1]), "--quiet"]
    assert commands[2][0] == commands[3][0] == context["GPU_PYTHON"]
    assert "torch==2.9.1" in commands[2]


def test_environment_creation_works_with_ensurepip_unavailable(tmp_path):
    """Exercise creation of a real pip-free environment and offline pip seeding."""
    import os

    blocker = tmp_path / "blocked"
    blocker.mkdir()
    (blocker / "ensurepip.py").write_text("raise RuntimeError('ensurepip intentionally unavailable')\n")
    env = {**os.environ, "PYTHONPATH": str(blocker)}
    unavailable = subprocess.run([sys.executable, "-m", "ensurepip"], env=env,
                                 capture_output=True, text=True)
    assert unavailable.returncode != 0 and "intentionally unavailable" in unavailable.stderr
    target = tmp_path / "isolated"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(target)], env=env, check=True)
    python = target / "bin/python"
    probe = subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True, text=True)
    assert probe.returncode != 0
    # Use an already installed Python distribution's wheel to avoid networking in tests.
    wheel = next((Path(ensurepip.__file__).parent / "_bundled").glob("pip-*.whl"))
    subprocess.run([sys.executable, "-m", "pip", "--python", str(python), "install", "--no-index",
                    "--no-deps", "--no-cache-dir", str(wheel)], env=env, check=True, capture_output=True)
    probe = subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True, text=True, check=True)
    assert str(target) in probe.stdout


@pytest.mark.parametrize("member", ["../escape", "/absolute", "safe/../../escape", "bad\\path"])
def test_zip_path_traversal_rejected_before_extracting(tmp_path, member):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("first.txt", "must not be written")
        output.writestr(member, "invalid")
    with pytest.raises(ValueError, match="Unsafe"):
        driver.unpack_checked(archive, tmp_path / "destination")
    assert not (tmp_path / "destination/first.txt").exists()


def test_bundle_discovery_handles_zip_and_automatic_extraction(tmp_path):
    with pytest.raises(ValueError, match="found 0"):
        driver.find_bundle(tmp_path)
    archive = tmp_path / "news_ir_kaggle.zip"
    archive.touch()
    assert driver.find_bundle(tmp_path) == archive
    archive.unlink()
    payload = tmp_path / "dataset"
    (payload / "scripts").mkdir(parents=True)
    (payload / "bundle.json").write_text("{}")
    (payload / "scripts/run_kaggle_dense.py").touch()
    assert driver.find_bundle(tmp_path) == payload
    archive.touch()
    with pytest.raises(ValueError, match="found 2"):
        driver.find_bundle(tmp_path)


def test_checkpoint_roundtrip_excludes_uncommitted_shards(tiny_index, tmp_path):
    root = tmp_path / "original"
    encode_corpus(tiny_index["index"], "unused", root, shard_size=3,
                  time_budget_seconds=1e-12, encoder=FixtureEncoder())
    abandoned = root / "shards/.writing-interrupted"
    abandoned.mkdir()
    (abandoned / "vectors.npy").write_bytes(b"unfinished")
    archive = driver.export_checkpoint(root, tmp_path / "checkpoint.zip")
    with zipfile.ZipFile(archive) as contents:
        assert not any(".writing" in name for name in contents.namelist())
    restored = tmp_path / "restored"
    driver.restore_checkpoint(archive, restored)
    config = json.loads((restored / "config.json").read_text())
    assert read_shards(restored, config)[1] == 3
    # A changed batch size is permitted, and the original full selection is retained.
    result = encode_corpus(tiny_index["index"], "unused", restored, shard_size=3,
                           batch_size=1, resume=True, encoder=FixtureEncoder())
    assert result["completed"] and result["documents_this_session"] == 6
    driver.restore_checkpoint(archive, restored)
    assert read_shards(restored, config)[1] == 9
    extracted = tmp_path / "auto-extracted"
    driver.unpack_checked(archive, extracted)
    restored_directory = tmp_path / "restored-from-directory"
    driver.restore_checkpoint(extracted, restored_directory)
    assert read_shards(restored_directory, config)[1] == 3


def test_relocated_metadata_checks_source_and_lookup(tiny_index, tmp_path):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    shutil.copy2(tiny_index["index"] / "manifest.json", metadata)
    shutil.copy2(tiny_index["index"] / "documents.sqlite3", metadata)
    corpus = tmp_path / "corpus.jsonl"
    shutil.copy2(tiny_index["corpus"], corpus)
    info = {"source_bytes": corpus.stat().st_size, "source_sha256": sha256_file(corpus),
            "eligible_documents": 9}
    driver.relocate_metadata(metadata, corpus, info)
    with DocumentStore(metadata) as store:
        assert store.get("0007-é").title == "Montréal — café"
    with pytest.raises(ValueError, match="differs"):
        driver.relocate_metadata(metadata, corpus, {**info, "source_sha256": "wrong"})


def test_driver_stops_before_download_if_gpu_is_missing(tmp_path, monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="No CUDA"):
        driver.run_job(SimpleNamespace())


def test_driver_timed_export_then_resume_build_and_run(tiny_index, tmp_path, monkeypatch):
    """Actual shards/FAISS/run ZIP; only remote resources and neural inference are faked."""
    import huggingface_hub
    import news_ir.dense
    import news_ir.embedding
    import torch

    payload = tmp_path / "input/dataset"
    (payload / "annotations").mkdir(parents=True)
    (payload / "corpus_metadata").mkdir()
    shutil.copytree(ROOT / "src", payload / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "scripts", payload / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("manifest.json", "documents.sqlite3"):
        shutil.copy2(tiny_index["index"] / name, payload / "corpus_metadata" / name)
    query = payload / "annotations/custom_queries.draft.jsonl"
    query.write_text(json.dumps({"_id": "test", "text": "cricket insect"}) + "\n")
    bundle = {"source_bytes": tiny_index["corpus"].stat().st_size,
              "source_sha256": sha256_file(tiny_index["corpus"]), "eligible_documents": 9,
              "corpus_repository": "fixture", "model_revision": "fixture", "model_files": {},
              "query_sha256": sha256_file(query)}
    (payload / "bundle.json").write_text(json.dumps(bundle))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda *args: "fixture-no-real-gpu")
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", lambda **kwargs: str(tiny_index["corpus"]))
    monkeypatch.setattr(news_ir.embedding, "download_model", lambda *args, **kwargs: {"files": {}})

    class Encoder(FixtureEncoder):
        def __init__(self, *args, **kwargs):
            super().__init__()
    monkeypatch.setattr(news_ir.dense, "E5Encoder", Encoder)
    original_encode = news_ir.dense.encode_corpus
    monkeypatch.setattr(news_ir.dense, "encode_corpus", lambda *args, **kwargs:
                        original_encode(*args, **{**kwargs, "shard_size": 3}))
    original_run = subprocess.run
    def mock_benchmark(command, **kwargs):
        if len(command) > 1 and command[1].endswith("benchmark_dense.py"):
            Path(command[-1]).write_text(json.dumps({"fixture_only": True}))
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, **kwargs)
    monkeypatch.setattr(subprocess, "run", mock_benchmark)
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "src"))
    monkeypatch.setattr(sys, "path", sys.path.copy())
    args = SimpleNamespace(bundle=str(payload), workspace=str(tmp_path / "workspace"),
                           output=str(tmp_path / "first-output"), resume_archive=None,
                           batch_size=2, time_budget_hours=1e-12)
    first = driver.run_job(args)
    assert first["completed"] is False and first["encoded_documents"] == 3
    assert not (Path(args.output) / "dense-results.zip").exists()
    args.resume_archive = str(Path(args.output) / "dense-checkpoints.zip")
    args.output = str(tmp_path / "second-output")
    args.time_budget_hours = 1
    second = driver.run_job(args)
    assert second["completed"] and second["encoded_documents"] == 9
    assert second["query_count"] == 1 and second["total_hits"] == 9
    with zipfile.ZipFile(second["results_archive"]) as archive:
        assert "indexes/dense/vectors.faiss" in archive.namelist()
        assert "runs/dense-custom-draft/run.trec" in archive.namelist()
        assert not any("corpus.jsonl" in name for name in archive.namelist())
        ids = [line.split()[2] for line in archive.read("runs/dense-custom-draft/run.trec").decode().splitlines()]
        assert ids[0] == "insect" and len(ids) == len(set(ids)) == 9
    # Rerun with writable progress: verify/reuse existing index and run without overwriting.
    manifest_path = Path(args.output) / "news_ir_job/indexes/dense/manifest.json"
    original_manifest = manifest_path.read_bytes()
    assert driver.run_job(args)["progress"]["documents_this_session"] == 0
    assert manifest_path.read_bytes() == original_manifest
