"""BM25 search with identical index/query analysis and original article lookup."""

import math
from dataclasses import asdict, dataclass

from .data import DocumentStore
from .indexing import ANALYZER
from .runtime import initialize_jvm


@dataclass(frozen=True)
class SearchHit:
    doc_id: str
    rank: int
    score: float

    def to_dict(self):
        return asdict(self)


class BM25Engine:
    def __init__(self, index_dir, *, corpus=None, k1=None, b=None):
        self.store = DocumentStore(index_dir, corpus)
        self._searcher = None
        self._closed = False
        try:
            manifest = self.store.manifest
            if manifest.get("schema_version") != 1 or manifest.get("engine") != "lucene-bm25":
                raise ValueError("Unsupported index manifest")
            if manifest["analyzer"] != ANALYZER:
                raise ValueError("Index analyzer differs from supported query analyzer")
            self.k1 = float(manifest["bm25"]["k1"] if k1 is None else k1)
            self.b = float(manifest["bm25"]["b"] if b is None else b)
            if not math.isfinite(self.k1) or self.k1 <= 0:
                raise ValueError("BM25 k1 must be finite and greater than zero")
            if not math.isfinite(self.b) or not 0 <= self.b <= 1:
                raise ValueError("BM25 b must be finite and between zero and one")
            initialize_jvm()
            from pyserini.analysis import Analyzer, get_lucene_analyzer
            from pyserini.pyclass import autoclass

            java_analyzer = get_lucene_analyzer(stemming=False, stopwords=False)
            self._analyzer = Analyzer(java_analyzer)
            # Pyserini 1.5's search package eagerly imports API encoders, one of
            # which constructs a credentialed client even for local BM25. Use
            # the exact same Anserini searcher through its Java bridge instead.
            SimpleSearcher = autoclass('io.anserini.search.SimpleSearcher')
            self._searcher = SimpleSearcher(str(self.store.root / "lucene"))
            self._searcher.set_analyzer(java_analyzer)
            self._searcher.set_bm25(self.k1, self.b)
            if self._searcher.get_total_num_docs() != manifest["documents"]["indexed"]:
                raise ValueError("Index document count differs from manifest")
        except BaseException:
            self.close()
            raise

    @property
    def num_docs(self):
        return self._searcher.get_total_num_docs()

    def analyze(self, text):
        if self._closed:
            raise ValueError("Search engine is closed")
        if not isinstance(text, str):
            raise TypeError("Query must be a string")
        return self._analyzer.analyze(text)

    def search(self, query, top_k=10):
        if type(top_k) is not int or not 1 <= top_k <= 10000:
            raise ValueError("top_k must be an integer between 1 and 10000")
        tokens = self.analyze(query)
        if not tokens:
            return []
        if len(tokens) > 512:
            raise ValueError("Query exceeds the supported limit of 512 analyzed tokens")
        # The upstream searcher applies deterministic external-ID tie handling.
        hits = self._searcher.search(query, top_k)
        return [SearchHit(hit.docid, rank, float(hit.score))
                for rank, hit in enumerate(hits, 1)]

    def get_document(self, doc_id):
        return self.store.get(doc_id)

    def close(self):
        if not self._closed:
            try:
                if self._searcher is not None:
                    self._searcher.close()
            finally:
                self.store.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
