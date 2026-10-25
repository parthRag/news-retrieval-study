import io
import json
from types import SimpleNamespace

import pytest

from news_ir.demo import DemoService, make_handler


@pytest.fixture
def demo(tiny_index, tmp_path, monkeypatch):
    import news_ir.demo
    from news_ir.data import DocumentStore

    monkeypatch.setattr(news_ir.demo, "DocumentStore", lambda _: DocumentStore(tiny_index["index"]))
    def fixture(self):
        self.catalog = {"custom": [{"_id": "q", "text": "cricket insect", "relevant_if": "insect"}]}
        self.runs = {"custom": {"bm25": {"q": [{"doc_id": "sport", "rank": 1, "score": 2.}]},
                                "dense": {"q": [{"doc_id": "insect", "rank": 1, "score": .8}]}}}
        self.judgments = {"custom": {("q", "insect"): {"grade": 2, "assessor_type": "AI"}}}
        self.scores = {"custom": {e: {"aggregate": {}, "per_query": {"q": {"ndcg_at_5": 0.}}} for e in ("bm25", "dense")}}
    monkeypatch.setattr(DemoService, "_load_saved", fixture)
    service = DemoService(tmp_path)
    yield service
    service.close()


def test_replay_labels_are_query_specific_and_articles_are_complete(demo):
    result = demo.replay("custom", "q")
    assert result["overlap"] == 0
    assert result["engines"]["dense"]["hits"][0]["assessment"]["grade"] == 2
    assert result["engines"]["bm25"]["hits"][0]["assessment"] is None
    doc = demo.document("insect", "custom", "q")
    assert doc["contents"] == (doc["title"]+"\n"+doc["text"]).strip()
    assert demo.document("insect", "custom", "other")["assessment"] is None
    with pytest.raises(ValueError):
        demo.replay("custom", "missing")
    with pytest.raises(ValueError):
        demo.replay("custom", "q", 1000)
    with pytest.raises(KeyError):
        demo.document("absent")


@pytest.mark.parametrize("query", ["", "   ", None, [], "x"*2001])
def test_live_rejects_invalid_queries_before_acquiring_slot(demo, query):
    with pytest.raises(ValueError):
        demo.start_live(query)
    assert not demo.live_slot.locked()


def test_live_engine_isolation_fusion_and_no_relevance_fabrication(demo):
    calls = []
    def runner(engine, query):
        calls.append((engine, query))
        return {"search_latency_ms": 3., "hits": [{"doc_id": "insect" if engine == "dense" else "sport", "rank": 1, "score": .7}]}
    demo.live_runner = runner
    # Run synchronously with the same acquired-slot contract as start_live.
    demo.live_slot.acquire()
    demo.jobs["job"] = {}
    demo._live_job("job", "cricket insect")
    result = demo.job("job")
    assert result["status"] == "complete"
    assert calls == [("bm25", "cricket insect"), ("dense", "cricket insect")]
    assert len(result["result"]["engines"]["rrf"]["hits"]) == 2
    assert all(h["assessment"] is None for e in result["result"]["engines"].values() for h in e["hits"])
    assert all(e["metrics"] is None for e in result["result"]["engines"].values())
    assert not demo.live_slot.locked()


def test_live_failure_and_busy_job_release_slot(demo):
    demo.live_slot.acquire()
    with pytest.raises(RuntimeError, match="running"):
        demo.start_live("query")
    def fail(*a):
        raise ValueError("simulated model failure")
    demo.live_runner = fail
    demo.jobs["failed"] = {}
    demo._live_job("failed", "query")
    assert demo.job("failed")["status"] == "failed"
    assert "simulated" in demo.job("failed")["error"]
    assert not demo.live_slot.locked()


def call_http(service, method, path, body=b"", extra_headers=None):
    """Exercise actual HTTP parsing/routing without opening a sandbox port."""
    headers = {"Host": "127.0.0.1:8765", "Content-Type": "application/json", "Content-Length": str(len(body)), **(extra_headers or {})}
    request = f"{method} {path} HTTP/1.0\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
    class Socket:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(request.encode()+body)
        def sendall(self, data):
            output.write(data)
    output = io.BytesIO()
    make_handler(service)(Socket(), ("127.0.0.1", 1), SimpleNamespace(server_port=8765))
    raw = output.getvalue()
    head, result = raw.split(b"\r\n\r\n", 1)
    return int(head.split()[1]), result, head


def test_http_reads_errors_static_allowlist_and_origin_policy(demo):
    status, body, headers = call_http(demo, "GET", "/api/replay?suite=custom&qid=q")
    assert status == 200 and json.loads(body)["query_id"] == "q"
    assert b"nosniff" in headers
    assert call_http(demo, "GET", "/api/replay?suite=custom&qid=q&k=bad")[0] == 400
    assert call_http(demo, "GET", "/api/document?id=absent")[0] == 404
    assert call_http(demo, "GET", "/../corpus.jsonl")[0] == 404
    assert call_http(demo, "GET", "/", extra_headers={"Host": "elsewhere.test:8765"})[0] == 403
    assert call_http(demo, "GET", "/")[0] == 200
    assert call_http(demo, "POST", "/api/live", b"{}", {"Origin": "https://elsewhere.test"})[0] == 403
    assert call_http(demo, "POST", "/api/live", b"{}")[0] == 400
    assert call_http(demo, "POST", "/api/live", b"invalid")[0] == 400
    assert call_http(demo, "POST", "/api/live", b"[]")[0] == 400


def test_http_live_handoff_and_job_polling(demo, monkeypatch):
    monkeypatch.setattr(demo, "start_live", lambda q: {"job_id": "fixture"})
    status, body, _ = call_http(demo, "POST", "/api/live", b'{"query":"new query"}')
    assert status == 202 and json.loads(body)["job_id"] == "fixture"
    demo.jobs["fixture"] = {"status": "running", "stage": "BM25"}
    assert json.loads(call_http(demo, "GET", "/api/job/fixture")[1])["status"] == "running"
    assert call_http(demo, "GET", "/api/job/missing")[0] == 404
