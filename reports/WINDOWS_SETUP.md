# Windows setup and verification

Use **64-bit Python 3.12** and **JDK 21** on Windows 10/11. The native BM25, dense search, demo and evaluation commands run from PowerShell; WSL is optional. Download the JDK from [Eclipse Temurin](https://adoptium.net/temurin/releases/?version=21) and set `JAVA_HOME` to the JDK directory, rather than its `bin` subdirectory. Open a new terminal after installation.

## Create a Windows environment

From the project directory in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements-portable.txt
.\.venv\Scripts\python.exe scripts/check_environment.py
```

Create this environment on Windows. A `.venv` copied from a Mac contains executables for the wrong OS. `requirements-lock.txt` records the earlier ARM Mac environment; `requirements-portable.txt` lets pip select the appropriate Windows wheels while keeping the project's pinned retrieval and evaluation dependencies. The portable install uses the same model revision and retrieval settings.

These commands invoke the environment's Python directly, so PowerShell activation permissions do not matter. Command Prompt accepts the same executable paths, with the leading `.\` optional. You can also activate the environment and use `python` for the remaining commands.

If Java discovery fails, use your actual JDK folder in the current PowerShell session:

```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\your-jdk-21-folder"
& "$env:JAVA_HOME\bin\java.exe" -version
.\.venv\Scripts\python.exe scripts/check_environment.py
```

Use `;` between multiple Java classpath entries on Windows. The code constructs classpaths with `os.pathsep`; a drive-letter colon such as `C:` must remain part of its path. Arguments are passed as a subprocess list, so spaces in the JDK or project path do not require manual command-string assembly.

## Run the project

```powershell
.\.venv\Scripts\python.exe -m news_ir.demo
```

Open **http://127.0.0.1:8765**. For direct retrieval:

```powershell
.\.venv\Scripts\python.exe -m news_ir search "cricket insect lifecycle" --top-k 5
.\.venv\Scripts\python.exe -m news_ir dense-search "cricket insect lifecycle" --top-k 5 --device cpu
```

The repository does not include the multi-gigabyte corpus, models or indexes. Reuse the exact `corpus.jsonl`, `artifacts/indexes/bm25/`, `artifacts/indexes/dense/` and `artifacts/models/e5-base-v2/` from the existing project, retaining their relative layout. Saved runs and evaluation files are also needed for experiment replay. Copy data files and indexes, rather than the old virtual environment.

The application locates moved project artifacts without rewriting frozen manifests. A relocated corpus is checked against its recorded size and SHA-256; copying or converting the corpus to CRLF will invalidate its original byte offsets and hash. Preserve the exact bytes. Git attributes likewise prevent automatic newline conversion of hash-bound files during clone/checkout.

To build a fresh index for a different corpus, use a new output directory:

```powershell
.\.venv\Scripts\python.exe -m news_ir index --corpus corpus.jsonl --output artifacts/indexes/bm25-new
```

## Verify the installation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke_portability.py --output artifacts/windows-smoke.json
```

The smoke test builds a tiny synthetic index in a directory containing spaces and Unicode, reads CRLF-delimited records by binary offsets, exercises real CLI retrieval and native evaluation, and renders/inspects a two-page PDF. It downloads no model and creates no relevance judgments. Chrome, Edge or Brave is needed for its browser portion; pass `--skip-browser` if you only need the retrieval checks. The ordinary test suite also checks FAISS against NumPy, concurrent document access, copied manifests, Java path separators, and child/grandchild cleanup.

The [compatibility workflow](../.github/workflows/compatibility.yml) runs native Windows and Linux checks. Its artifacts contain test XML and the smoke result, so native execution can be distinguished from a simulated Windows branch in a Mac test.

## PDFs and browser verification

```powershell
.\.venv\Scripts\python.exe scripts/build_final_documents.py
.\.venv\Scripts\python.exe scripts/render_final_pdfs.py
.\.venv\Scripts\python.exe scripts/inspect_pdf.py deliverables/5_NewsIR_BM25_Dense.pdf artifacts/pdf-review/brief-new
.\.venv\Scripts\python.exe scripts/inspect_pdf.py deliverables/RESEARCH_REPORT.pdf artifacts/pdf-review/research-new
```

Browser helpers detect Edge/Chrome/Brave on each OS; `--browser "C:\path\to\chrome.exe"` selects a specific executable where supported. `NEWS_IR_BROWSER` supplies an alternative for all browser helpers. The Python PDF inspector checks pages, text and hyperlinks without Swift or PDFKit. Raster screenshots remain available through the browser verification scripts. The original Swift inspector remains an optional macOS tool.

Historical milestone reports and the preserved cloud notebooks may show their original platform commands. Kaggle/Colab cells execute on Linux in those services. Use this guide's commands for the active Windows project.
