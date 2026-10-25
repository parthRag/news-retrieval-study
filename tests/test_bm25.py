import math

import pytest

from conftest import write_corpus
from news_ir.indexing import build_index
from news_ir.retrieval import BM25Engine


def test_query_analysis_preserves_negation_numbers_and_inflections(tiny_index):
    with BM25Engine(tiny_index["index"]) as engine:
        assert engine.analyze("NOT without running 2016 cricket") == ["not", "without", "running", "2016", "cricket"]
        assert engine.analyze("!!!") == []


def test_bm25_matches_independent_single_term_calculation(tmp_path):
    corpus = tmp_path / "score.jsonl"
    texts = ["quasar quasar comet", "quasar comet", "comet comet comet", "meteor"]
    write_corpus(corpus, [{"_id": str(i), "title": "", "text": text} for i, text in enumerate(texts)])
    index = tmp_path / "index"
    build_index(corpus, index, threads=1)
    with BM25Engine(index) as engine:
        hits = engine.search("quasar")
    n, df, avgdl, k1, b = 4, 2, 9 / 4, 0.9, 0.4
    idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
    expected = {}
    for doc_id, tf, length in [("0", 2, 3), ("1", 1, 2)]:
        # Lucene omits the query-constant (k1+1) factor from its BM25 scores.
        expected[doc_id] = idf * tf / (tf + k1 * (1 - b + b * length / avgdl))
    assert [hit.doc_id for hit in hits] == sorted(expected, key=expected.get, reverse=True)
    from pyserini.index.lucene import LuceneIndexReader
    reader = LuceneIndexReader(str(index / "lucene"))
    try:
        for hit in hits:
            raw_weight = reader.compute_bm25_term_weight(hit.doc_id, "quasar", analyzer=None, k1=k1, b=b)
            assert raw_weight == pytest.approx(expected[hit.doc_id], abs=1e-6)
            # Anserini's search API rounds to 1e-4 before adjusting tied scores.
            assert hit.score == pytest.approx(round(expected[hit.doc_id], 4), abs=1e-7)
    finally:
        reader.reader.close()


def test_word_sense_context_and_title_only_retrieval(tiny_index):
    with BM25Engine(tiny_index["index"]) as engine:
        assert engine.num_docs == 9
        assert engine.search("cricket insect lifecycle")[0].doc_id == "insect"
        assert engine.search("cricket match championship")[0].doc_id == "sport"
        assert engine.search("quasar")[0].doc_id == "title-only"
        assert engine.search("marathon")[0].doc_id == "body-only"
        assert engine.search("café")[0].doc_id == "0007-é"
        assert [h.doc_id for h in engine.search("not")] == ["negative"]
        assert engine.search("quasarnotinthecorpus") == []
        assert engine.search(" \n ") == []
        assert engine.search("!!!") == []


def test_stable_ties_top_k_and_bag_of_words_semantics(tiny_index):
    with BM25Engine(tiny_index["index"]) as engine:
        first = engine.search("tieprobe")
        assert len(first) == 2
        assert [hit.doc_id for hit in first] == ["tie-a", "tie-z"]
        assert engine.search("tieprobe") == first
        assert engine.search("tieprobe", 1) == first[:1]
        # Capitalized NOT is a term, not a hard Boolean exclusion operator.
        assert "positive" in {h.doc_id for h in engine.search("policy NOT drones")}


@pytest.mark.parametrize("value", [0, -1, True, 1.5, 10001])
def test_invalid_top_k(tiny_index, value):
    with BM25Engine(tiny_index["index"]) as engine:
        with pytest.raises(ValueError, match="top_k"):
            engine.search("cricket", value)


@pytest.mark.parametrize("kwargs", [{"k1": 0}, {"k1": float("nan")}, {"k1": float("inf")},
    {"b": -0.1}, {"b": 1.1}, {"b": float("nan")}])
def test_invalid_bm25_parameters(tiny_index, kwargs):
    with pytest.raises(ValueError, match="BM25"):
        BM25Engine(tiny_index["index"], **kwargs)


def test_invalid_query_and_closed_engine(tiny_index):
    engine = BM25Engine(tiny_index["index"])
    with pytest.raises(TypeError):
        engine.search(None)
    with pytest.raises(ValueError, match="512"):
        engine.search("term " * 513)
    engine.close()
    engine.close()
    with pytest.raises(ValueError, match="closed"):
        engine.search("cricket")
