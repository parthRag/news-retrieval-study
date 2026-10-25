"""E5 download provenance and offline, attention-mask-aware embeddings."""

import json
import importlib.metadata
import platform
import re
from pathlib import Path

import numpy as np

from .data import sha256_file


DEFAULT_MODEL = "intfloat/e5-base-v2"


def download_model(output, *, revision="main"):
    from huggingface_hub import HfApi, snapshot_download

    target = Path(output).resolve()
    if (target / "encoder.json").exists():
        spec = read_model_spec(target)
        if revision not in {"main", spec["revision"]}:
            raise ValueError("Existing model directory belongs to a different revision")
        return spec
    info = HfApi().model_info(DEFAULT_MODEL, revision=revision, token=False)
    if not re.fullmatch(r"[0-9a-f]{40}", info.sha):
        raise ValueError("Hub did not resolve an immutable model revision")
    snapshot_download(DEFAULT_MODEL, revision=info.sha, local_dir=target, token=False,
                      allow_patterns=["config.json", "model.safetensors", "tokenizer.json",
                                      "tokenizer_config.json", "special_tokens_map.json", "vocab.txt"],
                      max_workers=3)
    config = json.loads((target / "config.json").read_text())
    spec = {"model_id": DEFAULT_MODEL, "revision": info.sha,
            "dimension": config["hidden_size"], "max_length": 512,
            "query_prefix": "query: ", "passage_prefix": "passage: ",
            "pooling": "attention-mask-aware mean", "normalization": "L2",
            "files": {p.name: sha256_file(p) for p in sorted(target.iterdir())
                      if p.is_file() and p.suffix in {".json", ".txt", ".safetensors"}}}
    if "model.safetensors" not in spec["files"] or "tokenizer.json" not in spec["files"]:
        raise ValueError("Missing required E5 model/tokenizer files")
    temp = target / "encoder.json.tmp"
    temp.write_text(json.dumps(spec, indent=2) + "\n")
    temp.replace(target / "encoder.json")
    return spec


def read_model_spec(path, *, verify=True):
    root = Path(path)
    spec = json.loads((root / "encoder.json").read_text())
    if spec["model_id"] != DEFAULT_MODEL or not re.fullmatch(r"[0-9a-f]{40}", spec["revision"]):
        raise ValueError("Unsupported or unpinned encoder")
    if spec["dimension"] != 768 or spec["max_length"] != 512:
        raise ValueError("Unexpected E5 architecture/input configuration")
    if spec.get("query_prefix") != "query: " or spec.get("passage_prefix") != "passage: ":
        raise ValueError("Invalid E5 input prefixes")
    if spec.get("pooling") != "attention-mask-aware mean" or spec.get("normalization") != "L2":
        raise ValueError("Invalid E5 pooling/normalization configuration")
    if not {"model.safetensors", "config.json", "tokenizer.json"}.issubset(spec["files"]):
        raise ValueError("Model manifest omits required files")
    if verify:
        for name, digest in spec["files"].items():
            if Path(name).name != name or sha256_file(root / name) != digest:
                raise ValueError(f"Model file identity check failed: {name}")
    return spec


def masked_mean_pool(last_hidden_state, attention_mask):
    mask = attention_mask.unsqueeze(-1).to(last_hidden_state.dtype)
    return (last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)


def validate_vectors(vectors, *, dimension, rows=None):
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != dimension or (rows is not None and len(array) != rows):
        raise ValueError("Embedding dimensions/row count do not match the encoder")
    if not np.isfinite(array).all():
        raise ValueError("Embeddings contain non-finite values")
    if not np.allclose(np.linalg.norm(array, axis=1), 1, atol=1e-4):
        raise ValueError("Embeddings must be nonzero L2-normalized vectors")
    return np.ascontiguousarray(array)


class E5Encoder:
    def __init__(self, model_dir, *, device="auto", threads=4):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.spec = read_model_spec(model_dir)
        if type(threads) is not int or threads < 1:
            raise ValueError("threads must be a positive integer")
        torch.set_num_threads(threads)
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        if device not in {"cpu", "cuda", "mps"}:
            raise ValueError("device must be auto, cpu, cuda or mps")
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA is unavailable")
        if device == "mps" and not torch.backends.mps.is_available():
            raise ValueError("Apple MPS acceleration is unavailable")
        self.device, self.dimension = device, self.spec["dimension"]
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True,
                                                       trust_remote_code=False)
        self.model = AutoModel.from_pretrained(str(model_dir), local_files_only=True,
                                               trust_remote_code=False, use_safetensors=True)
        self.model.to(device)
        self.model.eval()
        self.runtime = {"torch": torch.__version__, "device": device, "threads": threads,
                        "precision": "float32", "attention_implementation": self.model.config._attn_implementation,
                        "transformers": importlib.metadata.version("transformers"), "platform": platform.platform(),
                        "device_name": torch.cuda.get_device_name(0) if device == "cuda" else device}

    def synchronize(self):
        import torch
        if self.device == "cuda":
            torch.cuda.synchronize()
        elif self.device == "mps":
            torch.mps.synchronize()

    def encode(self, texts, *, kind):
        import torch

        if kind not in {"query", "passage"}:
            raise ValueError("Embedding kind must be query or passage")
        if not isinstance(texts, (list, tuple)) or not all(isinstance(t, str) for t in texts):
            raise TypeError("texts must be a list of strings")
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        inputs = [self.spec[f"{kind}_prefix"] + text for text in texts]
        tokens = self.tokenizer(inputs, max_length=self.spec["max_length"], padding=True,
                                truncation=True, return_tensors="pt")
        tokens = {key: value.to(self.device) for key, value in tokens.items()}
        with torch.inference_mode():
            output = self.model(**tokens).last_hidden_state
            vectors = masked_mean_pool(output, tokens["attention_mask"])
            vectors = torch.nn.functional.normalize(vectors.float(), p=2, dim=1)
        return validate_vectors(vectors.cpu().numpy(), dimension=self.dimension, rows=len(texts))
