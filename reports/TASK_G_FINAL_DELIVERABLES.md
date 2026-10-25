# Task G: final local deliverables

> Historical milestone: current assessment status and planned human review are described in [Assessment method](ASSESSMENT_METHOD.md).

The final-deliverables request supersedes the earlier instruction to defer PDF assembly. The local implementation and document package are complete, with explicit placeholders for metadata not provided by the user. No repository or submission has been published.

## Produced files

- `deliverables/GROUP_PENDING_NewsIR_BM25_Dense.pdf`: the required **four-page** status/submission brief, including identity/repository placeholders, implementation status, architecture, IR pipeline, baseline results, resources, remaining-work plan, stretch status and contribution matrix.
- `deliverables/RESEARCH_REPORT.pdf`: **15-page** research report with abstract, questions, related work, corpus/query design, methods, assessment/evaluation protocol, original/custom results, uncertainty, evidence-based failures, content-quality experiment, engineering, limitations, references and all-query/evidence appendices.
- Matching Markdown and HTML sources, architecture SVG, contribution CSV and machine-readable results snapshot.
- `deliverables/NewsIR_Reproducibility_Package.zip`: explicitly selected code, tests, notebooks, judgments, original query/qrel files, saved runs, reports, metrics and provenance. Corpus/model/index files, article packets and environment caches are excluded.
- `deliverables/release_manifest.json` and `deliverables/final_validation.json`: archive/member hashes, PDF content/page checks and numerical reproduction evidence.

`DELIVERABLES.md` explains which PDF to submit, how to replace metadata and regenerate, how to run the demo, and which data files a fresh machine must restore.

## Final diagnostic experiment

The symmetric quality ablation applies fixed rules within each original top 20 and never refills beyond that horizon. All candidates are already judged. Empty-body removal raises E5 nDCG@5 **0.489668 → 0.549151**, P@5 **0.53 → 0.60**, with BM25 unchanged. Exact duplicate removal is evaluated separately; a distinct unique-content measure prevents repeated content receiving repeated gain. No new relevance labels, corpus edits, threshold fitting or encoding were used.

These are post-hoc results motivated by observed failures, without held-out confirmation. They do not replace baseline scores or establish the sole reason for E5 errors. See `reports/QUALITY_ABLATION.md` and `artifacts/evaluations/quality-top20-v1/`. A fresh-output rerun exactly reproduces the quantitative files.

## Review and verification

The full suite passed **140 tests**. Native independent metric checks total **5,460** across original BM25/E5, original RRF and the custom suite. The 737-pair validator recomputes custom results, checks source/evidence consistency and preserves all earlier judgments. Final release validation recomputes original primary, custom linear/exponential and all quality-policy per-query/aggregate values from saved artifacts, without requiring a GPU or model.

The PDFs were rendered with a separate temporary Chromium profile. macOS PDFKit checked page counts and extracted text, bound to the PDF SHA-256. Page images were reviewed, including the result tables, references and appendices; a merged Markdown table was corrected during that review. The final brief has four pages and the research report fifteen. Required numerical content and all twenty query IDs are checked. No missing figures or horizontal overflow were detected by the print-layout audit.

The full-article source review also corrected two presentation descriptions: N03 is about reporting that Ebola is not airborne, and H03 concerns Apple's iPhone-unlocking dispute. Frozen query texts, article judgments and metrics were unchanged. The report treats article assertions as retrieval evidence, not clinical or legal guidance.

## Required user-supplied metadata

Group number, all member names, actual completed contribution ownership and a real GitHub repository URL still need to replace the placeholders in `configs/submission.json`. Regenerate the documents and archive after that change, verify the PDF remains within four pages, then have one group member submit the brief. The 15-page report is supporting material and exceeds the stated interim submission limit.

Human review is now the planned next validation stage, described in the method linked above. Controlled peak RAM, warmed query-latency measurement and a controlled polarity-pair experiment remain further work. Current results are preliminary and use shallow pooled references.
