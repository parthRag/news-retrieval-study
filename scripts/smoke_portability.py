"""Exercise real CLI/native engines and headless PDF rendering on each OS.

Uses a tiny synthetic corpus and no downloaded model or research judgments.
All scratch data stays in a temporary directory with spaces and Unicode.
"""
import argparse
import base64
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from news_ir.benchmark import crosscheck
from news_ir.data import sha256_file
from news_ir.evaluation import evaluate_rankings, load_run
from news_ir.platform_support import configure_text_streams, find_browser, process_options, terminate_process_tree
from inspect_pdf import inspect


def browser_smoke(root, executable):
    from websockets.sync.client import connect

    source = root / "two pages café.html"
    source.write_text('<!doctype html><meta charset="utf-8"><title>café 東京</title>'
        '<style>@page{size:A4}section{break-after:page}section:last-child{break-after:auto}</style>'
        '<section><h1>First page café</h1><a href="https://example.com/">Source link</a></section>'
        '<section><h1>Second page</h1></section>', encoding="utf-8", newline="\n")
    profile = root / "browser profile"
    process = subprocess.Popen([executable, "--headless", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
        "--user-data-dir=" + str(profile), "about:blank"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, **process_options())
    try:
        active = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 30
        while not active.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Browser exited before creating its debugging endpoint")
            time.sleep(.1)
        port = active.read_text(encoding="utf-8").splitlines()[0]
        with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
            target = next(t for t in json.load(response) if t["type"] == "page")
        with connect(target["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
            sequence = 0
            def call(method, params=None):
                nonlocal sequence
                sequence += 1
                ws.send(json.dumps({"id": sequence, "method": method, "params": params or {}}))
                while True:
                    message = json.loads(ws.recv(timeout=30))
                    if message.get("id") == sequence:
                        if "error" in message:
                            raise RuntimeError(message["error"])
                        return message.get("result", {})
            call("Page.enable")
            call("Page.navigate", {"url": source.as_uri()})
            for _ in range(100):
                value = call("Runtime.evaluate", {"expression": "document.readyState==='complete' && document.title==='café 東京'", "returnByValue": True})
                if value["result"].get("value"):
                    break
                time.sleep(.1)
            else:
                raise RuntimeError("Unicode HTML did not load")
            printed = call("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True})
            pdf = root / "two pages.pdf"
            pdf.write_bytes(base64.b64decode(printed["data"]))
        result = inspect(pdf, root / "pdf inspection")
        if result["page_count"] != 2 or not any("example.com" in url for p in result["pages"] for url in p["links"]):
            raise ValueError("PDF page/link inspection failed")
        return {"status": "passed", "executable": executable, "pdf_pages": 2, "unicode_html": True,
                "pdf_links_verified": True}
    finally:
        terminate_process_tree(process)


def main():
    configure_text_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(repo / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    def cli(*arguments):
        result = subprocess.run([sys.executable, "-m", "news_ir", *map(str, arguments)],
            capture_output=True, text=True, encoding="utf-8", env=env, check=False, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr[-4000:])
        return json.loads(result.stdout)
    with tempfile.TemporaryDirectory(prefix="news-ir café with spaces-") as temporary:
        root = Path(temporary)
        corpus, index = root / "corpus.jsonl", root / "index"
        records = [{"_id": "café-id", "title": "Cricket insect", "text": "cricket insect lifecycle 東京"},
                   {"_id": "sport", "title": "Cricket sport", "text": "cricket match highlights"},
                   {"_id": "empty", "title": "", "text": ""}]
        corpus.write_bytes(b"\r\n".join(json.dumps(r, ensure_ascii=False).encode("utf-8") for r in records))
        built = cli("index", "--corpus", corpus, "--output", index, "--threads", 1)
        search = cli("search", "cricket insect", "--index", index)
        if search["hits"][0]["doc_id"] != "café-id":
            raise ValueError("Unexpected lexical ranking")
        document = cli("document", "café-id", "--index", index)
        if "東京" not in json.dumps(document, ensure_ascii=False):
            raise ValueError("Unicode article lookup failed")
        queries = root / "queries.jsonl"
        queries.write_text(json.dumps({"_id": "q", "text": "cricket insect"}) + "\n", encoding="utf-8", newline="\n")
        run = root / "run"
        cli("run", "--queries", queries, "--output", run, "--index", index, "--top-k", 1000)
        ranked, _ = load_run(run, queries, {"café-id", "sport"}, expected_source_sha256=sha256_file(corpus))
        labels = {"q": {"café-id": 2, "sport": 0}}
        checked = crosscheck(labels, ranked, evaluate_rankings(ranked, labels), root / "evaluation", name="portable")
        result = {"status": "passed", "platform": platform.platform(), "python": platform.python_version(),
            "cli_index_search_document_run": "passed", "crlf_binary_offsets": "passed",
            "unicode_and_space_paths": "passed", "utf8_mode_disabled_in_cli": True,
            "indexed_documents": built["documents"]["indexed"], "native_metric_crosscheck": checked,
            "browser": {"status": "skipped by explicit flag"} if args.skip_browser else browser_smoke(root, find_browser())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
