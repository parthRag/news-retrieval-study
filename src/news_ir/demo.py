"""Local comparison demo: verified experiment replay and isolated live searches."""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .data import DocumentStore, sha256_file, valid_id
from .evaluation import load_run
from .fusion import reciprocal_rank_fusion


class DemoService:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.store = DocumentStore(self.root / "artifacts/indexes/bm25")
        self.catalog, self.runs, self.scores, self.judgments, self.visibility = {}, {}, {}, {}, {}
        self.jobs, self.lock, self.live_slot = {}, threading.Lock(), threading.Lock()
        self.live_runner = self._run_engine
        try:
            self._load_saved()
        except BaseException:
            self.store.close()
            raise

    def _load_saved(self):
        eligible = {r[0] for r in self.store._db.execute("SELECT doc_id FROM documents WHERE eligible=1")}
        source = self.store.manifest["source"]["sha256"]
        configurations = {
            "custom": ("annotations/ai_study_v1/queries.jsonl", "custom20-depth20-v1", "linear",
                       {"bm25": "bm25-custom-draft-depth1000", "dense": "dense-custom-draft"}),
            "original": ("queries.jsonl", "rrf-original-57", "primary",
                         {"bm25": "bm25-original-benchmark", "dense": "dense-original", "rrf": "rrf-original-k60"})}
        if (self.root / "artifacts/evaluations/custom40-depth20-v2/manifest.json").exists():
            configurations["expanded"] = ("annotations/custom40_v2/queries.all40.jsonl", "custom40-depth20-v2", "linear",
                                          {"bm25": "bm25-custom40-v2", "dense": "dense-custom40-v2"})
        for suite, (queryfile, evaluation, policy, runnames) in configurations.items():
            querypath = self.root / queryfile
            queries = list(map(json.loads, querypath.read_text().splitlines()))
            folder = self.root / "artifacts/evaluations" / evaluation
            manifest = json.loads((folder / "manifest.json").read_text())
            for f, digest in manifest["files"].items():
                if sha256_file(folder / f) != digest:
                    raise ValueError(f"Saved evaluation artifact changed: {f}")
            if manifest["corpus_sha256"] != source:
                raise ValueError("Saved evaluation corpus differs from local store")
            expected_queries = manifest.get("query_source_sha256", manifest.get("queries_sha256"))
            if sha256_file(querypath) != expected_queries:
                raise ValueError("Demo queries differ from evaluated snapshot")
            self.scores[suite] = json.loads((folder / "metrics.json").read_text())[policy]
            self.catalog[suite] = queries
            self.runs[suite] = {}
            for engine, runname in runnames.items():
                runfolder = self.root / "artifacts/runs" / runname
                expected_manifest = manifest["runs"][engine]["manifest_sha256"]
                if sha256_file(runfolder / "manifest.json") != expected_manifest:
                    raise ValueError("Demo run differs from evaluated snapshot")
                load_run(runfolder, querypath, eligible, expected_source_sha256=source)
                self.runs[suite][engine] = {r["query_id"]: r["hits"] for r in
                    map(json.loads, (runfolder / "results.jsonl").read_text().splitlines())}
            if suite in {"custom", "expanded"}:
                labels = self.root / ("annotations/custom40_v2/assessments.all40.jsonl" if suite == "expanded"
                                      else "annotations/ai_study_v1/assessments.depth20.jsonl")
                if sha256_file(labels) != manifest["assessments_sha256"]:
                    raise ValueError("Custom labels differ from evaluated snapshot")
                self.judgments[suite] = {(r["query_id"], r["doc_id"]): r for r in map(json.loads, labels.read_text().splitlines())}
            else:
                qrels = self.root / "qrel.jsonl"
                # Original evaluation manifest uses qrels_sha256.
                if sha256_file(qrels) != manifest["qrels_sha256"]:
                    raise ValueError("Original qrels differ from evaluated snapshot")
                self.judgments[suite] = {(r["query-id"], r["corpus-id"]): {"grade": int(r["score"]), "assessor_type": "supplied benchmark qrels"}
                                         for r in map(json.loads, qrels.read_text().splitlines())}
        visibility = self.root / "annotations/ai_study_v1/evidence_visibility.depth20.json"
        if visibility.exists():
            audit = json.loads(visibility.read_text())
            self.visibility = {(r["query_id"], r["doc_id"]): r for r in audit["documents"]}
        expanded_visibility = self.root / "annotations/custom40_v2/evidence_visibility.all40.json"
        if expanded_visibility.exists():
            audit = json.loads(expanded_visibility.read_text())
            self.visibility.update({(r["query_id"], r["doc_id"]): r for r in audit["documents"]})

    def catalog_data(self):
        return {"suites": self.catalog, "aggregate": {s: {e: v["aggregate"] for e, v in es.items()} for s, es in self.scores.items()},
                "eligible_documents": self.store.manifest["documents"]["indexed"],
                "custom_assessed_pairs": len(self.judgments.get("expanded", self.judgments["custom"])),
                "evaluated_query_count": len({(q["_id"], q["text"]) for qs in self.catalog.values() for q in qs}),
                "live_enabled": True}

    @staticmethod
    def validate_query(query):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError("Enter a query between 1 and 2,000 characters")
        return query.strip()

    def _enrich(self, hits, suite=None, qid=None, k=5):
        output = []
        for hit in hits[:k]:
            doc = self.store.get(hit["doc_id"])
            if doc is None:
                raise ValueError("A ranked article is absent from the corpus")
            label = self.judgments.get(suite, {}).get((qid, doc.doc_id))
            output.append({**hit, "title": doc.title or "Untitled article", "snippet": doc.text[:450],
                           "empty_body": not doc.text.strip(), "assessment": label})
        return output

    def replay(self, suite, qid, k=5):
        if suite not in self.catalog or qid not in self.runs[suite]["bm25"]:
            raise ValueError("Choose a query from the experiment suite")
        if type(k) is not int or not 1 <= k <= 20:
            raise ValueError("Display depth must be between 1 and 20")
        query = next(q for q in self.catalog[suite] if q["_id"] == qid)
        selected = {e: hits[qid] for e, hits in self.runs[suite].items()}
        overlap = set(h["doc_id"] for h in selected["bm25"][:k]) & set(h["doc_id"] for h in selected["dense"][:k])
        return {"mode": "saved", "suite": suite, "query_id": qid, "query": query["text"], "rubric": query,
                "overlap": len(overlap), "k": k,
                "engines": {e: {"hits": self._enrich(hits, suite, qid, k),
                                 "metrics": self.scores[suite][e]["per_query"][qid]} for e, hits in selected.items()}}

    def document(self, doc_id, suite=None, qid=None):
        if not valid_id(doc_id) or len(doc_id) > 200:
            raise ValueError("Invalid article ID")
        doc = self.store.get(doc_id)
        if doc is None:
            raise KeyError("Article not found")
        result = doc.to_dict()
        result["contents"] = doc.contents
        result["assessment"] = self.judgments.get(suite, {}).get((qid, doc_id))
        visible = self.visibility.get((qid, doc_id)) if suite in {"custom", "expanded"} else None
        if visible:
            import hashlib
            if hashlib.sha256(doc.contents.encode()).hexdigest() != visible["contents_sha256"]:
                raise ValueError("Input visibility audit differs from the source article")
        result["e5_input_end"] = visible["retained_contents_end_exclusive"] if visible else None
        return result

    def _run_engine(self, engine, query):
        command = [sys.executable, "-m", "news_ir", "search" if engine == "bm25" else "dense-search", "--top-k", "1000"]
        if engine == "dense":
            command += ["--device", "cpu"]
        command += ["--", query]
        environment = {**os.environ, "TOKENIZERS_PARALLELISM": "false", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        with subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=environment, start_new_session=True) as process:
            try:
                stdout, stderr = process.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                raise ValueError(f"{engine} exceeded its five-minute live-search limit")
            if process.returncode:
                raise ValueError(f"{engine} search failed: {stderr[-1200:]}")
            return json.loads(stdout)

    def start_live(self, query):
        query = self.validate_query(query)
        if not self.live_slot.acquire(blocking=False):
            raise RuntimeError("A live search is running. Wait for it to finish before starting another.")
        job_id = uuid.uuid4().hex
        with self.lock:
            # Keep bounded in-memory history; never write live rankings over experiments.
            if len(self.jobs) >= 5:
                self.jobs.pop(next(iter(self.jobs)))
            self.jobs[job_id] = {"status": "running", "stage": "BM25", "query": query}
        threading.Thread(target=self._live_job, args=(job_id, query), daemon=True).start()
        return {"job_id": job_id}

    def _live_job(self, job_id, query):
        try:
            start, results = time.perf_counter(), {}
            for engine in ("bm25", "dense"):
                with self.lock:
                    self.jobs[job_id]["stage"] = "BM25" if engine == "bm25" else "E5 dense"
                stage_start = time.perf_counter()
                raw = self.live_runner(engine, query)
                hits = [{k: h[k] for k in ("doc_id", "rank", "score")} for h in raw["hits"]]
                results[engine] = {"hits": hits, "engine_search_ms": raw["search_latency_ms"],
                                   "elapsed_ms_with_startup": (time.perf_counter()-stage_start)*1000, "metrics": None}
            fused = reciprocal_rank_fusion([[h["doc_id"] for h in results[e]["hits"]] for e in ("bm25", "dense")])
            results["rrf"] = {"hits": fused, "metrics": None}
            overlap = len(set(h["doc_id"] for h in results["bm25"]["hits"][:5]) & set(h["doc_id"] for h in results["dense"]["hits"][:5]))
            for result in results.values():
                result["hits"] = self._enrich(result["hits"], k=20)
            response = {"mode": "live", "query": query, "engines": results, "overlap": overlap,
                        "k": 5, "elapsed_ms_with_startup": (time.perf_counter()-start)*1000}
            with self.lock:
                self.jobs[job_id] = {"status": "complete", "result": response}
        except Exception as exc:
            with self.lock:
                self.jobs[job_id] = {"status": "failed", "error": str(exc)}
        finally:
            self.live_slot.release()

    def job(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError("Search job not found")
            return dict(self.jobs[job_id])

    def close(self):
        self.store.close()


def make_handler(service):
    assets = Path(__file__).parent / "web"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def reply(self, status, body, mime="application/json; charset=utf-8"):
            data = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, (dict, list)) else body
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.local_host():
                return self.reply(403, {"error": "Use the local demo address"})
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            arg = lambda key, default="": params.get(key, [default])[0]
            try:
                static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/style.css": ("style.css", "text/css; charset=utf-8")}
                if parsed.path in static:
                    filename, mime = static[parsed.path]
                    self.reply(200, (assets / filename).read_bytes(), mime)
                elif parsed.path == "/api/catalog":
                    self.reply(200, service.catalog_data())
                elif parsed.path == "/api/replay":
                    self.reply(200, service.replay(arg("suite"), arg("qid"), int(arg("k", "5"))))
                elif parsed.path == "/api/document":
                    self.reply(200, service.document(arg("id"), arg("suite"), arg("qid")))
                elif parsed.path.startswith("/api/job/"):
                    self.reply(200, service.job(parsed.path.rsplit("/", 1)[-1]))
                else:
                    self.reply(404, {"error": "Not found"})
            except KeyError as exc:
                self.reply(404, {"error": str(exc)})
            except (ValueError, TypeError) as exc:
                self.reply(400, {"error": str(exc)})
            except Exception:
                self.reply(500, {"error": "Could not read the experiment. Check local artifacts."})

        def do_POST(self):
            if not self.local_host():
                return self.reply(403, {"error": "Use the local demo address"})
            if self.path != "/api/live":
                return self.reply(404, {"error": "Not found"})
            # Browser requests must originate from this local demo; no cross-site jobs.
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                return self.reply(403, {"error": "Cross-origin requests are disabled"})
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                return self.reply(400, {"error": "Send application/json"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 12000:
                    raise ValueError("Invalid request length")
                supplied = json.loads(self.rfile.read(length))
                if not isinstance(supplied, dict):
                    raise ValueError("Request must be an object")
                self.reply(202, service.start_live(supplied.get("query")))
            except RuntimeError as exc:
                self.reply(409, {"error": str(exc)})
            except (ValueError, TypeError) as exc:
                self.reply(400, {"error": str(exc)})

        def local_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535")
    service = DemoService(args.root)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(service))
        print(f"News IR demo: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    finally:
        service.close()


if __name__ == "__main__":
    main()
