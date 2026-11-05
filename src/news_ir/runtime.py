"""Configure this process's JVM without modifying the user's shell settings."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .platform_support import WINDOWS

_DLL_HANDLES = {}


def java_classpath(*paths):
    """Java uses ';' on Windows and ':' on POSIX; preserve drive-letter colons."""
    return os.pathsep.join(str(path) for path in paths)


def java_executable():
    if WINDOWS and not os.environ.get("JAVA_HOME"):
        found = shutil.which("java")
        if found:
            home = Path(found).resolve().parent.parent
            if (home / "bin/server/jvm.dll").is_file():
                os.environ["JAVA_HOME"] = str(home)
    if os.environ.get("JAVA_HOME"):
        home = Path(os.environ["JAVA_HOME"].strip('"'))
        java = home / "bin" / ("java.exe" if WINDOWS else "java")
        if not java.is_file():
            raise ValueError(f"JAVA_HOME does not contain bin/{java.name}")
        if WINDOWS and hasattr(os, "add_dll_directory"):
            for folder in (home / "bin", home / "bin/server"):
                if folder.is_dir() and str(folder) not in _DLL_HANDLES:
                    _DLL_HANDLES[str(folder)] = os.add_dll_directory(str(folder))
        return str(java)
    return "java"


def configure_java():
    if not os.environ.get("JAVA_HOME") and sys.platform == "darwin":
        result = subprocess.run(
            ["/usr/libexec/java_home", "-v", "21"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            os.environ["JAVA_HOME"] = result.stdout.strip()
    result = subprocess.run([java_executable(), "-version"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=True)
    return (result.stderr or result.stdout).strip()


def initialize_jvm():
    configure_java()
    import jnius_config

    if not jnius_config.vm_running:
        jnius_config.add_options("-Xmx2g")
    from pyserini.pyclass import autoclass

    # Keep Java logging out of the CLI's machine-readable JSON stdout.
    system = autoclass("java.lang.System")
    system.setOut(system.err)
