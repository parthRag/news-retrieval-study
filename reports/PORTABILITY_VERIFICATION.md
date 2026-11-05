# Windows compatibility and regression verification

Verified 5 November 2026. The retrieval settings, model revision, saved runs, source corpus and reference judgments are preserved. The [native CI run](https://github.com/parthRag/news-retrieval-study/actions/runs/42075124081) tested commit `6144083bfb2f83dfd85be97f0e01d9528df81612` on real Windows and Linux runners. The setup commands are in [WINDOWS_SETUP.md](WINDOWS_SETUP.md).

## Changes and reasons

- Document lookup now performs binary seek/read under the existing lock instead of using POSIX-only `os.pread`. UTF-8 multibyte text, CRLF record separators, byte offsets and concurrent readers are tested together.
- Java discovery handles `java.exe`, JDK directories containing spaces, Windows DLL search paths and `JAVA_HOME`. Classpaths use the OS separator, preserving drive-letter colons. Mac Java discovery remains supported.
- Windows evaluation uses the compiled `pytrec-eval-terrier==0.5.11` reference extension because the Anserini JAR contains no Windows `trec_eval` executable. Mac/Linux retain the wrapper. Both routes use ordinal scores, the same gain transform and the same empty-topic macro denominator; the backend is recorded in new output metadata.
- Stored project paths can relocate across OSs without editing their frozen manifests. Corpus and artifact hashes still validate the actual content.
- Active text reads/writes explicitly use UTF-8, with deterministic LF exports. Git attributes preserve byte-bound files across Windows checkouts. Manifest and ZIP member paths use forward slashes. Archive validation checks original member names before Windows normalization, including drive-relative paths, UNC paths and embedded NULs.
- FAISS reads/writes index files through Python binary streams, allowing Unicode Windows paths. The persistent isolated worker and exact cosine ranking remain in place.
- Owned process cleanup supports Windows process trees and POSIX process groups, including descendant workers. Browser tools discover Chrome/Edge/Brave. A Python PDF inspector replaces the required use of Swift/PDFKit.
- The portable requirements file and PowerShell guide replace reliance on the ARM Mac lock and `.venv/bin` commands for native Windows setup.

## Verification results

| Platform | Passed | Skipped | Failed/errors | Native CLI + browser/PDF | Saved benchmark reproduction |
|---|---:|---:|---:|---|---|
| Windows Server 2025 x64, Python 3.12.10 | 196 | 4 | 0 | Passed | Passed |
| Linux x64, Python 3.12.15 | 196 | 4 | 0 | Passed | Passed |
| macOS ARM, Python 3.12.9 | 200 | 0 | 0 | Passed | Passed locally |

The four native-CI skips require the downloaded E5 model. CI tests the dense pipeline against deterministic synthetic vectors and independent NumPy scores; the Mac additionally runs the model-dependent checks with the existing pinned weights. A native Windows runner is stronger evidence than a mocked Windows code branch, but it is not a run on every teammate's physical Windows laptop or a full-corpus encoding job.

The real CLI smoke tests create a tiny CRLF corpus in a directory containing spaces and Unicode. They disable Python UTF-8 mode in the child CLI, build a real Lucene index, search, retrieve the original Unicode article, export and reload rankings, and cross-check metrics. Chrome renders a two-page PDF whose page count, text loading and hyperlinks are checked without Swift.

Both native platforms pass the full package hash/metric validator: the 57-query benchmark, initial/added/combined custom suites, quality sensitivities and Core/COVID integrated results reproduce. The validator verifies the preserved 10,409 historical native metric comparisons; it does not claim to have rerun all of those historical native binaries. The integrated check recomputes 8,400 standard metric values across Core/COVID, along with their sensitivities and paired tests. All 122 files of the attributed imported source snapshot remain unchanged.

On the Mac, the real browser rechecked all 267 saved views and 267 article endpoints, 4,140 hybrid explanations, evidence/prefix display and mobile layout, with no JavaScript exceptions. A real live query also completed BM25, E5 and RRF, retaining unjudged status and reconstructable fusion scores from both full top-1,000 source lists. Its single observed elapsed time was about 51 seconds including startup; this is an operational smoke result, not a new latency comparison.

## Reproduction and evidence

```sh
python -m pip install -r requirements-portable.txt
python scripts/check_environment.py
python -m pytest -q
python scripts/smoke_portability.py --output artifacts/platform-smoke-recheck.json
python scripts/validate_final_deliverables.py
```

Use the Windows environment's `Scripts/python.exe` as shown in the setup guide when it is not activated. Do not copy a Mac virtual environment to Windows. Preserve exact corpus bytes when transferring indexes.

Machine-readable evidence is [summary.json](../artifacts/portability-validation/summary.json); CI artifacts include each platform's test XML, smoke result and numerical validation. The original four-page PDF, research PDF and v1.1.0 release assets are historical submission artifacts and were not regenerated for this maintenance work. No human review or new relevance labels are claimed.
