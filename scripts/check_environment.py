"""Print actionable environment diagnostics without loading native libraries together."""
import importlib.metadata
import json
import platform
import struct
import sys

from news_ir.platform_support import configure_text_streams, find_browser
from news_ir.runtime import configure_java, java_executable


def main():
    configure_text_streams()
    result = {"python": platform.python_version(), "platform": platform.platform(),
              "bits": struct.calcsize("P") * 8, "executable": sys.executable, "packages": {}}
    errors = []
    if sys.version_info[:2] != (3, 12):
        errors.append("Use Python 3.12, as required by this project's pinned engine versions")
    if result["bits"] != 64:
        errors.append("Use 64-bit Python and a 64-bit JDK")
    for package in ("news-ir", "pyserini", "pyjnius", "numpy", "torch", "transformers", "faiss-cpu", "ir-measures"):
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"Missing {package}; install the project extras listed in reports/WINDOWS_SETUP.md")
    try:
        result["java_version"] = configure_java()
        result["java_executable"] = java_executable()
        if 'version "21' not in result["java_version"]:
            errors.append("Use JDK 21 and set JAVA_HOME to its installation directory")
    except (OSError, ValueError) as exc:
        errors.append(f"Java check failed: {exc}")
    try:
        result["browser"] = find_browser()
    except FileNotFoundError:
        result["browser"] = "optional; install Chrome/Edge/Brave for PDF and browser checks"
    result["status"] = "passed" if not errors else "needs setup"
    result["errors"] = errors
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
