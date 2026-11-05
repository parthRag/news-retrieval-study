import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from news_ir import platform_support as portable
from news_ir import runtime
from news_ir.data import DocumentStore


@pytest.mark.parametrize("old_path", ["/old/mac/project/corpus.jsonl", "Z:\\old\\project\\corpus.jsonl"])
def test_binary_offsets_without_pread_unicode_crlf_relocation_and_threads(tmp_path, monkeypatch, old_path):
    monkeypatch.delattr(os, "pread", raising=False)
    root = tmp_path / "project with spaces café"
    index = root / "artifacts/indexes/bm25"
    index.mkdir(parents=True)
    docs = [{"_id": f"café-{i}", "title": "東京", "text": "One\r\nTwo — naïve"} for i in range(8)]
    encoded = [(json.dumps(d, ensure_ascii=False) + "\r\n").encode("utf-8") for d in docs]
    corpus = root / "corpus.jsonl"
    corpus.write_bytes(b"".join(encoded))
    with sqlite3.connect(index / "documents.sqlite3") as db:
        db.execute("CREATE TABLE documents(doc_id TEXT, byte_offset INTEGER, line_bytes INTEGER, eligible INTEGER)")
        offset = 0
        for doc, raw in zip(docs, encoded, strict=True):
            db.execute("INSERT INTO documents VALUES(?,?,?,1)", (doc["_id"], offset, len(raw)))
            offset += len(raw)
    (index / "manifest.json").write_text(json.dumps({"source": {"path": old_path,
        "bytes": corpus.stat().st_size, "mtime_ns": 0, "sha256": hashlib.sha256(corpus.read_bytes()).hexdigest()}}), encoding="utf-8")
    with DocumentStore(index) as store:
        with ThreadPoolExecutor(max_workers=8) as workers:
            actual = list(workers.map(store.get, [d["_id"] for d in docs] * 20))
        expected = [{"doc_id": d["_id"], "title": d["title"], "text": d["text"]} for d in docs]
        assert [d.to_dict() for d in actual] == expected * 20
        assert store.corpus == corpus
    assert store._stream.closed
    corpus.write_bytes(corpus.read_bytes().replace(b"One", b"Bad"))
    with pytest.raises(ValueError, match="hash differs"):
        DocumentStore(index)


@pytest.mark.parametrize("stored", ["/old/mac/repo/artifacts/runs/example", "C:\\old\\repo\\artifacts\\runs\\example"])
def test_saved_paths_relocate_without_rewriting_manifest(tmp_path, stored):
    candidate = tmp_path / "artifacts/runs/example"
    candidate.mkdir(parents=True)
    assert portable.resolve_saved_path(stored, root=tmp_path) == candidate


def test_saved_existing_path_and_missing_path_are_not_redirected(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    assert portable.resolve_saved_path(original, root=tmp_path / "other") == original
    missing = tmp_path / "missing"
    assert portable.resolve_saved_path(missing, root=tmp_path) == missing


@pytest.mark.parametrize("separator", [":", ";"])
def test_java_classpath_preserves_spaces_and_windows_drive_colons(monkeypatch, separator):
    monkeypatch.setattr(runtime.os, "pathsep", separator)
    assert runtime.java_classpath("C:\\Program Files\\Java\\one.jar", "D:\\two.jar") == (
        "C:\\Program Files\\Java\\one.jar" + separator + "D:\\two.jar")


def test_windows_java_exe_and_dll_directories(monkeypatch, tmp_path):
    home = tmp_path / "Java home"
    (home / "bin/server").mkdir(parents=True)
    (home / "bin/java.exe").touch()
    monkeypatch.setenv("JAVA_HOME", str(home))
    monkeypatch.setattr(runtime, "WINDOWS", True)
    monkeypatch.setattr(runtime, "_DLL_HANDLES", {})
    added = []
    monkeypatch.setattr(os, "add_dll_directory", lambda p: added.append(p) or object(), raising=False)
    assert runtime.java_executable() == str(home / "bin/java.exe")
    assert len(added) == 2
    runtime.java_executable()
    assert len(added) == 2
    (home / "bin/java.exe").unlink()
    with pytest.raises(ValueError, match="java.exe"):
        runtime.java_executable()


def test_windows_process_group_and_taskkill(monkeypatch):
    monkeypatch.setattr(portable, "WINDOWS", True)
    assert "creationflags" in portable.process_options()
    calls = []
    polls = iter([None, 0])
    process = SimpleNamespace(pid=123, poll=lambda: next(polls), wait=lambda **kw: None,
                              kill=lambda: pytest.fail("taskkill already ended the process"))
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append(args))
    portable.terminate_process_tree(process)
    assert calls == [["taskkill.exe", "/PID", "123", "/T", "/F"]]


def test_windows_cleanup_falls_back_if_taskkill_is_unavailable(monkeypatch):
    monkeypatch.setattr(portable, "WINDOWS", True)
    killed = []
    def missing(*args, **kw):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", missing)
    process = SimpleNamespace(pid=123, poll=lambda: None, kill=lambda: killed.append(True), wait=lambda **kw: None)
    portable.terminate_process_tree(process)
    assert killed == [True]


def test_posix_process_group_escalation(monkeypatch):
    monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(portable, "WINDOWS", False)
    assert portable.process_options() == {"start_new_session": True}
    signals = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: signals.append((pid, sig)), raising=False)
    waited = []
    def wait(**kw):
        waited.append(True)
        if len(waited) == 1:
            raise subprocess.TimeoutExpired("fixture", 1)
    portable.terminate_process_tree(SimpleNamespace(pid=123, wait=wait))
    assert signals == [(123, signal.SIGTERM), (123, signal.SIGKILL)]


def test_browser_discovers_windows_edge_without_mac_path(monkeypatch, tmp_path):
    monkeypatch.delenv("NEWS_IR_BROWSER", raising=False)
    monkeypatch.setattr(portable.shutil, "which", lambda value: None)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    browser = tmp_path / "Microsoft/Edge/Application/msedge.exe"
    browser.parent.mkdir(parents=True)
    browser.touch()
    # Explicit path also handles spaces without shell quoting.
    assert portable.find_browser(str(browser)) == str(browser)
    monkeypatch.setattr(portable, "WINDOWS", True)
    assert portable.find_browser() == str(browser)


def test_real_owned_process_cleanup_also_stops_grandchild(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    child = ("import pathlib,time; p=pathlib.Path(" + repr(str(heartbeat)) + "); "
             "exec('while True:\\n p.write_text(str(time.time()))\\n time.sleep(.02)')")
    parent = "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); print(p.pid,flush=True); p.wait()"
    process = subprocess.Popen([sys.executable, "-u", "-c", parent], stdout=subprocess.PIPE,
                               text=True, encoding="utf-8", **portable.process_options())
    grandchild = int(process.stdout.readline().strip())
    try:
        deadline = time.monotonic() + 10
        while not heartbeat.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert heartbeat.exists()
        portable.terminate_process_tree(process)
        before = heartbeat.stat().st_mtime_ns
        time.sleep(.15)
        assert heartbeat.stat().st_mtime_ns == before
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            portable.terminate_process_tree(process)
        try:
            os.kill(grandchild, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        process.stdout.close()
