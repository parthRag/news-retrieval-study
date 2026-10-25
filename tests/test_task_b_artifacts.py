import ast
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from news_ir.embedding import read_model_spec
from news_ir.data import DocumentStore, sha256_file


ROOT = Path(__file__).resolve().parents[1]


def test_twenty_draft_queries_and_temporal_rubrics():
    rows = [json.loads(line) for line in (ROOT / "annotations/custom_queries.draft.jsonl").read_text().splitlines()]
    assert len(rows) == len({row["_id"] for row in rows}) == 20
    assert Counter(row["category"] for row in rows) == {
        "negation": 5, "homonym": 5, "temporal": 5, "vocabulary_mismatch": 5}
    for row in rows:
        assert row["status"] == "draft_requires_human_review"
        assert row["relevant_if"] and row["exclude_if"]
        if row["category"] == "temporal":
            window = row["event_window"]
            assert date.fromisoformat(window["start_inclusive"]) <= date.fromisoformat(window["end_inclusive"])


def test_colab_notebook_code_and_checkpoint_controls():
    notebook = json.loads((ROOT / "notebooks/News_IR_Dense_Encoding.ipynb").read_text())
    assert notebook["nbformat"] == 4
    code = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            text = "".join(cell["source"])
            ast.parse(text)
            assert cell["execution_count"] is None and cell["outputs"] == []
            code.append(text)
    joined = "\n".join(code)
    for required in ["torch.cuda.is_available()", "source_sha256", "model_revision", "--resume", "drive.mount"]:
        assert required in joined
    assert "--limit" not in joined


def test_dense_imports_without_pyserini_dependency():
    code = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('pyserini'):
            raise ImportError('Pyserini intentionally unavailable in this encoding-only runtime')
sys.meta_path.insert(0, Block())
from news_ir.dense import DenseEngine, encode_corpus, build_dense_index
from news_ir.embedding import E5Encoder
print('portable')
'''
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "portable"


def test_colab_source_relocation_cell_writes_valid_metadata(tiny_index, tmp_path, monkeypatch):
    import huggingface_hub
    import news_ir.embedding

    corpus = tmp_path / "corpus.jsonl"
    corpus.write_bytes(tiny_index["corpus"].read_bytes())
    metadata = tmp_path / "corpus_metadata"
    metadata.mkdir()
    for name in ("manifest.json", "documents.sqlite3"):
        shutil.copy2(tiny_index["index"] / name, metadata / name)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", lambda **kwargs: str(corpus))
    monkeypatch.setattr(news_ir.embedding, "download_model", lambda *args, **kwargs: {"files": {}})
    notebook = json.loads((ROOT / "notebooks/News_IR_Dense_Encoding.ipynb").read_text())
    source = next("".join(cell["source"]) for cell in notebook["cells"]
                  if cell["cell_type"] == "code" and "manifest_path.write_text" in "".join(cell["source"]))
    context = {"Path": Path, "json": json, "ROOT": tmp_path,
               "BUNDLE": {"source_sha256": sha256_file(corpus), "corpus_repository": "fixture",
                          "model_revision": "fixture", "model_files": {}}}
    exec(compile(source, "colab_relocation_cell", "exec"), context)
    with DocumentStore(metadata) as store:
        assert store.get("sport").doc_id == "sport"


@pytest.mark.parametrize("field,value", [("query_prefix", "passage: "),
    ("normalization", "none"), ("pooling", "CLS")])
def test_model_configuration_tampering_is_rejected(tmp_path, field, value):
    model = ROOT / "artifacts/models/e5-base-v2/encoder.json"
    if not model.exists():
        pytest.skip("Model not downloaded")
    spec = json.loads(model.read_text())
    spec[field] = value
    (tmp_path / "encoder.json").write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        read_model_spec(tmp_path, verify=False)
