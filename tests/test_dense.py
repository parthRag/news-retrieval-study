import json
from pathlib import Path

import numpy as np
import pytest
import torch

from news_ir.dense import DenseEngine, build_dense_index, encode_corpus, read_shards
from news_ir.embedding import E5Encoder, masked_mean_pool, validate_vectors


class FixtureEncoder:
    """Deterministic synthetic vectors for pipeline tests; never a model benchmark."""
    dimension = 4
    spec = {"dimension": 4, "revision": "fixture", "model_id": "test-only"}
    runtime = {"device": "test", "precision": "float32"}

    def __init__(self, fail_on_call=None):
        self.calls = 0
        self.fail_on_call = fail_on_call

    def encode(self, texts, *, kind):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("simulated interrupted encoding")
        vectors = np.array([[text.lower().count(word) + 0.1 for word in
                             ["cricket", "insect", "sport", "quasar"]] for text in texts], dtype=np.float32)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors

    def synchronize(self):
        pass


def test_masked_pool_ignores_padding():
    hidden = torch.tensor([[[1., 2.], [3., 4.], [1000., 1000.]]])
    mask = torch.tensor([[1, 1, 0]])
    assert torch.equal(masked_mean_pool(hidden, mask), torch.tensor([[2., 3.]]))


@pytest.mark.parametrize("array", [np.zeros((1, 4)), np.ones((1, 4)),
    np.array([[float("nan"), 0, 0, 0]]), np.ones((4,)), np.ones((1, 3))])
def test_bad_vectors_are_rejected(array):
    with pytest.raises(ValueError):
        validate_vectors(array, dimension=4, rows=1)


@pytest.fixture
def encoded(tiny_index, tmp_path):
    root = tmp_path / "encodings"
    result = encode_corpus(tiny_index["index"], "unused", root, batch_size=2, shard_size=3,
                           encoder=FixtureEncoder())
    assert result["encoded_documents"] == 9 and result["coverage"] == "full"
    return root


def test_checkpoint_resume_matches_uninterrupted_encoding(tiny_index, tmp_path):
    interrupted, reference = tmp_path / "interrupted", tmp_path / "reference"
    with pytest.raises(RuntimeError, match="interrupted"):
        encode_corpus(tiny_index["index"], "unused", interrupted, batch_size=2, shard_size=2,
                      encoder=FixtureEncoder(fail_on_call=2))
    assert len(list((interrupted / "shards").glob("shard-*"))) == 1
    result = encode_corpus(tiny_index["index"], "unused", interrupted, batch_size=2, shard_size=2,
                           encoder=FixtureEncoder(), resume=True)
    assert result["documents_this_session"] == 7
    encode_corpus(tiny_index["index"], "unused", reference, batch_size=2, shard_size=2,
                  encoder=FixtureEncoder())
    for first in (reference / "shards").glob("shard-*"):
        for name in ["ids.jsonl", "vectors.npy"]:
            assert (first / name).read_bytes() == (interrupted / "shards" / first.name / name).read_bytes()
    assert encode_corpus(tiny_index["index"], "unused", interrupted, shard_size=2,
                         encoder=FixtureEncoder(), resume=True)["documents_this_session"] == 0


def test_reject_resume_configuration_changes(tiny_index, encoded):
    with pytest.raises(ValueError, match="settings"):
        encode_corpus(tiny_index["index"], "unused", encoded, shard_size=4, resume=True,
                      encoder=FixtureEncoder())
    with pytest.raises(FileExistsError):
        encode_corpus(tiny_index["index"], "unused", encoded, encoder=FixtureEncoder())


def test_corrupt_shard_is_detected(encoded):
    config = json.loads((encoded / "config.json").read_text())
    shard = next((encoded / "shards").glob("shard-*"))
    with (shard / "vectors.npy").open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="Corrupt"):
        read_shards(encoded, config)


def test_exact_cosine_ranks_and_cutoff_ties(tiny_index, encoded, tmp_path):
    target = tmp_path / "dense"
    manifest = build_dense_index(encoded, target, document_index=tiny_index["index"], model_dir="unused")
    assert manifest["indexed_documents"] == 9
    with DenseEngine(target, encoder=FixtureEncoder()) as engine:
        assert engine.search("cricket insect")[0].doc_id == "insect"
        assert engine.search("cricket sport")[0].doc_id == "sport"
        query = FixtureEncoder().encode(["completely unseen terms"], kind="query")[0]
        config = json.loads((encoded / "config.json").read_text())
        shards, _, _ = read_shards(encoded, config)
        vectors = np.concatenate([np.load(folder / "vectors.npy") for folder, _ in shards])
        reference = sorted(zip((vectors @ query).tolist(), engine.ids), key=lambda pair: (-pair[0], pair[1]))
        hits = engine.search("completely unseen terms", 3)
        assert [hit.doc_id for hit in hits] == [doc_id for _, doc_id in reference[:3]]
        assert [hit.score for hit in hits] == pytest.approx([score for score, _ in reference[:3]], abs=1e-6)
        assert engine.get_document(hits[0].doc_id) is not None
        assert engine.search(" ") == []
        assert len(engine.search("cricket", 100)) == 9
        for invalid in [0, -1, True, 10001]:
            with pytest.raises(ValueError):
                engine.search("cricket", invalid)
        assert engine.search("cricket") == engine.search("cricket")
    with pytest.raises(ValueError, match="closed"):
        engine.search("cricket")
    with pytest.raises(FileExistsError):
        build_dense_index(encoded, target, document_index=tiny_index["index"], model_dir="unused")


def test_pilot_requires_explicit_acknowledgement(tiny_index, tmp_path):
    root, target = tmp_path / "encodings", tmp_path / "dense"
    encode_corpus(tiny_index["index"], "unused", root, limit=2, encoder=FixtureEncoder())
    with pytest.raises(ValueError, match="Pilot"):
        build_dense_index(root, target, document_index=tiny_index["index"], model_dir="unused")
    build_dense_index(root, target, document_index=tiny_index["index"], model_dir="unused", allow_partial=True)
    with pytest.raises(ValueError, match="pilot"):
        DenseEngine(target, encoder=FixtureEncoder())
    with DenseEngine(target, encoder=FixtureEncoder(), allow_partial=True) as engine:
        assert engine.num_docs == 2


def test_incomplete_encoding_cannot_be_indexed(tiny_index, tmp_path):
    root = tmp_path / "incomplete"
    with pytest.raises(RuntimeError):
        encode_corpus(tiny_index["index"], "unused", root, batch_size=2, shard_size=2,
                      encoder=FixtureEncoder(fail_on_call=2))
    with pytest.raises(ValueError, match="incomplete"):
        build_dense_index(root, tmp_path / "dense", document_index=tiny_index["index"], model_dir="unused")


def test_timed_stop_retains_full_target_and_resumes_exactly(tiny_index, tmp_path):
    root = tmp_path / "timed"
    result = encode_corpus(tiny_index["index"], "unused", root, shard_size=3,
                           time_budget_seconds=1e-12, encoder=FixtureEncoder())
    assert result["completed"] is False
    assert result["coverage"] == "full"
    assert result["encoded_documents"] == 3 and result["target_documents"] == 9
    config = json.loads((root / "config.json").read_text())
    assert config["target_documents"] == 9 and config["coverage"] == "full"
    with pytest.raises(ValueError, match="incomplete"):
        build_dense_index(root, tmp_path / "index", document_index=tiny_index["index"], model_dir="unused")
    resumed = encode_corpus(tiny_index["index"], "unused", root, shard_size=3,
                            encoder=FixtureEncoder(), resume=True)
    assert resumed["completed"] is True and resumed["documents_this_session"] == 6
    ids = [json.loads(line) for path in sorted((root / "shards").glob("*/ids.jsonl"))
           for line in path.read_text().splitlines()]
    assert ids == [row["_id"] for row in tiny_index["rows"] if row["_id"] != "empty"]


@pytest.mark.parametrize("budget", [0, -1, float("nan"), float("inf"), True])
def test_reject_invalid_time_budget(tiny_index, tmp_path, budget):
    with pytest.raises(ValueError, match="time_budget_seconds"):
        encode_corpus(tiny_index["index"], "unused", tmp_path / "invalid", encoder=FixtureEncoder(),
                      time_budget_seconds=budget)


MODEL = Path(__file__).resolve().parents[1] / "artifacts/models/e5-base-v2"


@pytest.mark.skipif(not (MODEL / "encoder.json").exists(), reason="Real E5 weights not downloaded; no network in tests")
def test_real_e5_prefix_normalization_padding_and_truncation():
    encoder = E5Encoder(MODEL, device="cpu")
    texts = ["a cricket insect", "a long article about cricket matches and sporting events"]
    together = encoder.encode(texts, kind="passage")
    alone = encoder.encode(texts[:1], kind="passage")
    assert together.shape == (2, 768)
    assert np.allclose(together[0], alone[0], atol=1e-5)
    assert np.allclose(np.linalg.norm(together, axis=1), 1, atol=1e-5)
    query = encoder.encode(texts[:1], kind="query")
    assert not np.allclose(query, alone)
    long = encoder.tokenizer("passage: " + "word " * 2000, max_length=512, truncation=True)
    assert len(long["input_ids"]) == 512
    assert encoder.encode([], kind="query").shape == (0, 768)
    assert encoder.model.training is False
