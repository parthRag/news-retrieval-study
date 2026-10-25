"""Configure this process's JVM without modifying the user's shell settings."""

import os
import subprocess
import sys
from pathlib import Path


def configure_java():
    if not os.environ.get("JAVA_HOME") and sys.platform == "darwin":
        result = subprocess.run(
            ["/usr/libexec/java_home", "-v", "21"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            os.environ["JAVA_HOME"] = result.stdout.strip()
    if os.environ.get("JAVA_HOME"):
        java = Path(os.environ["JAVA_HOME"]) / "bin" / "java"
        if not java.is_file():
            raise ValueError("JAVA_HOME does not contain bin/java")
    else:
        java = Path("java")
    result = subprocess.run([str(java), "-version"], capture_output=True, text=True, check=True)
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
