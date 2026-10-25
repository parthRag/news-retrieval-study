"""Own a persistent FAISS subprocess to avoid incompatible native OpenMP runtimes."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path


def worker_environment():
    env = dict(os.environ)
    package_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = package_root + os.pathsep + env.get("PYTHONPATH", "")
    return env


def build_faiss(encodings, output):
    result = subprocess.run([sys.executable, "-m", "news_ir.faiss_backend", "--build", str(encodings),
                             "--output", str(output)], capture_output=True, text=True,
                            env=worker_environment(), check=False)
    if result.returncode:
        raise RuntimeError(f"FAISS build failed: {result.stderr[-3000:]}")
    return json.loads(result.stdout)


class VectorWorker:
    def __init__(self, index_dir):
        self._lock = threading.Lock()
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-m", "news_ir.faiss_backend", "--index", str(index_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=worker_environment(),
        )
        line = self.process.stdout.readline()
        if not line:
            self.process.wait()
            raise RuntimeError(f"FAISS worker failed to start (exit {self.process.returncode})")
        self.info = json.loads(line)

    def search(self, vector, top_k):
        with self._lock:
            if self.process.poll() is not None:
                raise RuntimeError("FAISS worker is no longer running")
            self.process.stdin.write(json.dumps({"method": "search", "vector": vector.tolist(), "top_k": top_k}) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("FAISS worker stopped during search")
            result = json.loads(line)
            if "error" in result:
                raise ValueError(result["error"])
            return result["hits"]

    def close(self):
        with self._lock:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('{"method":"close"}\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    self.process.kill()
                    self.process.wait()
            self.process.stdin.close()
            self.process.stdout.close()
