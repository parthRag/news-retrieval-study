# Final deliverables and submission steps

The local submission package is implemented and generated. Group 5, all four member names/IDs, Information Retrieval and faculty mentor Abhinav Kumar are filled. The public repository is https://github.com/parthRag/news-retrieval-study. This public repository publishes a final source/report snapshot. The original development repository and history are private. The contribution matrix distinguishes assigned component responsibility of completed team components from confirmed personal work.

| Deliverable | File / location | Purpose |
| --- | --- | --- |
| Four-page submission PDF | `deliverables/5_NewsIR_BM25_Dense.pdf` | Main submission: objectives, dataset, related-paper findings/links, architecture/reasoning, current results, innovations, stretch work and milestones; verified public link; confirm individual contribution attribution before upload |
| Extended research report | `deliverables/RESEARCH_REPORT.pdf` | Methods, related work, results, failure diagnosis, uncertainty, ablation, limitations, references and query/evidence appendices |
| Editable report sources | Matching `.md` and `.html` files in `deliverables/` | Inspect text, review layout, regenerate after metadata edits |
| Runnable demo | `src/news_ir/demo.py` and `src/news_ir/web/` | Saved BM25/E5/RRF comparisons, full articles and evidence, live unjudged CPU search |
| Reproducibility archive | `deliverables/NewsIR_Reproducibility_Package.zip` | Code, tests, notebooks, reports, judgments, saved rankings, metric outputs and manifests; excludes corpus/model/index files |
| Release integrity | `deliverables/release_manifest.json` and `deliverables/final_validation.json` | File hashes, PDF page counts, checks and outstanding metadata |
| Quantitative snapshot | `deliverables/results_snapshot.json` | Machine-readable original/custom/quality results used by the documents |
| Architecture and contributions | `deliverables/architecture.svg`, `configs/submission.json`, `deliverables/contribution_matrix.csv` | Editable figure and component responsibility / confirmed-contribution records |
| Demo presentation sequence | `reports/DEMO_GUIDE.md` | Cases to show, controls, commands and live timing expectations |

Public downloads are provided in the [GitHub submission release](https://github.com/parthRag/news-retrieval-study/releases/latest). Submit the four-page PDF; the research report and ZIP are supporting artifacts.

## Run the working demo

From this repository with its existing environment and local data:

```sh
.venv/bin/python -m news_ir.demo
```

Open **http://127.0.0.1:8765**. Use `--port 8766` if another server already occupies the default port. Saved comparisons cover97 distinct queries:57 supplied topics and 40 custom needs; the original 20 custom view is also retained. Live queries search both full indexes and fuse their rankings; they receive no inferred relevance labels or evaluation metrics. No additional GPU job or API key is needed. Stop with Ctrl+C.

## Finish repository and contribution verification

Group/member/course/mentor details are already set in `configs/submission.json`. The public GitHub repository is created and verified, with `repository_status` set to `created`. Have each member confirm individual completed-work attribution after doing the assigned review. See `CONTRIBUTING.md` and `reports/GITHUB_HANDOFF.md`. Component responsibility is recorded separately from confirmed individual work. Then regenerate:

```sh
.venv/bin/python scripts/build_final_documents.py
.venv/bin/python scripts/render_final_pdfs.py
```

Rendering uses the installed Brave Chromium binary by default; `--browser /path/to/chromium` selects a compatible browser. It uses a separate temporary browser profile and local files. Editable HTML can also be opened and printed with A4 paper, background graphics enabled and 100% scale, but the automated render is the verified route. Do not rename an unchanged placeholder PDF and assume its internal metadata has been replaced.

On macOS, inspect the regenerated PDF's page count/text and render previews with:

```sh
CLANG_MODULE_CACHE_PATH=/private/tmp/news-ir-clang-cache SWIFT_MODULECACHE_PATH=/private/tmp/news-ir-swift-cache swift scripts/inspect_pdf.swift deliverables/5_NewsIR_BM25_Dense.pdf artifacts/pdf-review/brief
```

The Group 5 filename is already set. The brief must remain at most four pages. Rebuild/recheck the release archive after any final changes:

```sh
.venv/bin/python scripts/package_final_deliverables.py
.venv/bin/python scripts/validate_final_deliverables.py
```

Only one group member should submit the **four-page brief**, using the actual `<GroupNo>_<ShortProjectTitle>.pdf` name. The longer report is supporting material; it exceeds the stated submission limit. The submission PDF includes all required section types; individual completed-work confirmations remain outstanding before upload.

The latest instructions allow up to six pages, and the user specifically requests four. The main PDF is exactly four pages and covers both the original proposal details and the implementation evidence. `reports/FOUR_PAGE_REQUIREMENTS_REVIEW.md` maps each requirement to its page and records the accuracy checks.

## What the archive includes and excludes

The archive includes active source, preprocessing and cloud notebooks, frozen custom queries/labels, original query/qrel files, saved rank files, metric outputs, reports and PDF sources. It excludes `.venv`, caches, corpus text, full-article assessment packets, model weights, vector shards and built indexes. This keeps it reviewable and avoids redistributing the corpus. Existing quoted assessment evidence remains explicitly identified in the study.

The archive is sufficient to review code and audit numerical results from the saved rankings. A fresh machine needs the dataset, model and rebuilt or transferred indexes for actual article lookup or live search. Main retrieval/demo initialization requires the BM25 lookup store, so it does not run directly from the small archive alone. Follow the root README and Kaggle return guide to restore these data dependencies. Some historical manifests record the original absolute paths: preserve them as provenance; use fresh versioned outputs when rebuilding on a new machine rather than rewriting frozen manifests.

After extracting the archive, numerical and file-integrity checks can run from its root with Python 3.12, without the corpus, Java, GPU or model:

```sh
PYTHONPATH=src python3.12 scripts/validate_final_deliverables.py
```

This verifies the extracted members against `PACKAGE_MANIFEST.json` and reproduces the reported numerical results. It uses the packaged PDFKit inspection evidence for PDF structure/text; it does not rerender the PDFs or re-establish full-corpus ID coverage without the data files.

## Research conclusions and limits

The original 57-topic reference uses supplied benchmark judgments. The separate 40-query study is a preliminary comparison using 1,444 full-article AI judgments in the complete designated top-20 union. Human review is planned next; see [assessment method and review plan](reports/ASSESSMENT_METHOD.md). Its MAP is a shallow-pool estimate, not exhaustive corpus relevance, and both custom overall score-difference intervals include zero. The quality ablation is post-hoc and bounded to judged candidates. Human review has not yet been completed. Controlled peak RAM, warmed latency distributions, custom-RRF metrics and polarity-pair experiments remain further work.

The final code suite has 153 passing tests. Independent native metric checks total7,196 across the original baselines, original RRF and custom study. All117 saved-view rows (97 distinct queries), article views and mobile layout pass the updated browser check; the prior real live-query check is retained separately. PDF page counts, content checks and archive hashes are recorded in the final validation artifact.

## Versioned query extension

[The extension plan and current status](reports/CUSTOM_40_EXTENSION.md) expand the custom suite to 40 queries, ten in each category. The archive includes all 40 query/rubric records, the 20 new-query runs, and candidate IDs with rank provenance. Full article packets remain local. All707 added pairs are assessed; PDFs and the demo now include combined 40 results. The original 20 results remain available separately. Run `.venv/bin/python scripts/validate_custom40_extension.py` with the local corpus and indexes to check extension provenance and full-text pool coverage.
