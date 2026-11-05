"""Portable paths, browser discovery and cleanup for owned child processes."""
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path, PurePosixPath

WINDOWS = sys.platform == "win32"


def resolve_saved_path(value, *, root=None):
    """Locate moved project artifacts without editing their frozen manifests.

    Original existing paths take precedence. Fallbacks are restricted to known
    project directories, and callers still verify the recorded content hashes.
    Explicit user arguments should be resolved normally, not through this helper.
    """
    original = Path(value).expanduser()
    if original.exists():
        return original.resolve()
    roots = [Path(root).resolve()] if root is not None else [Path.cwd(), Path(__file__).resolve().parents[2]]
    parts = PurePosixPath(str(value).replace("\\", "/")).parts
    relative = []
    if not original.is_absolute() and ":" not in str(value):
        relative.append(original)
    for anchor in ("artifacts", "annotations", "studies"):
        if anchor in parts:
            relative.append(Path(*parts[parts.index(anchor):]))
    for base in roots:
        for suffix in relative:
            candidate = base / suffix
            if candidate.exists():
                return candidate.resolve()
    return original.resolve()


def process_options():
    if WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)}
    return {"start_new_session": True}


def terminate_process_tree(process, *, timeout=5):
    """Stop an owned process and its descendants, including the FAISS worker."""
    if WINDOWS:
        if process.poll() is not None:
            return
        try:
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=timeout)
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=timeout)


def find_browser(explicit=None):
    requested = explicit or os.environ.get("NEWS_IR_BROWSER")
    if requested:
        found = shutil.which(requested)
        if found:
            return found
        if Path(requested).is_file():
            return str(Path(requested).resolve())
        raise FileNotFoundError(f"Browser not found: {requested}")
    for name in ("google-chrome", "chromium", "chromium-browser", "msedge", "chrome", "brave-browser"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [] if WINDOWS else [
        Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if os.environ.get(variable):
            base = Path(os.environ[variable])
            candidates.extend(base / suffix for suffix in (
                "Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe",
                "BraveSoftware/Brave-Browser/Application/brave.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError("Install Chrome, Edge or Brave, or pass --browser /path/to/browser")


def configure_text_streams():
    """UTF-8 JSON is consistent when a Windows command is piped or redirected."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
