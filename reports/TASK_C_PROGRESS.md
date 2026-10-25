# Task C: evaluation of the 57 original queries

> Historical milestone: current assessment status and planned human review are described in [Assessment method](ASSESSMENT_METHOD.md).

Later update (25 October): the original milestone below is preserved. Custom AI assessment is now authorized and underway; the hybrid extension is evaluated. See [TASK_D_PROGRESS.md](TASK_D_PROGRESS.md) for current status.

Status on 24 October 2026: **complete** for the original benchmark requested by the user. Both full-corpus engines have depth-1,000 runs for all 57 queries, and all primary and sensitivity metrics have passed independent evaluation. The 20 custom queries remain a separate, deferred experiment.

## Implemented

- `src/news_ir/evaluation.py`: strict qrel/run loading, graded nDCG@5/10, AP@1000, Recall@1000, Precision@5/10, reciprocal rank and judged coverage. Missing positives remain in the primary denominators; missing queries cannot disappear from macro averages.
- `src/news_ir/benchmark.py`: paired comparison, direct-grade and exponential gain variants, original NIST gain sensitivity, available-corpus sensitivity, deterministic bootstrap intervals, per-query CSV, manifests and atomic output publication.
- `news-ir evaluate`: a reproducible CLI using the saved full-corpus runs and original qrels. No model API, additional GPU job or new labels are needed.
- Independent verification through native `trec_eval` in the existing Anserini JAR, invoked in a subprocess. All **3,248** per-topic/aggregate comparisons passed within native four-decimal output precision.
- `scripts/audit_original_benchmark.py`: complete match of all 15,655 supplied judgment pairs with NIST, with the documented grade-to-gain conversion; canonical source-article lookup against the real corpus.
- `scripts/report_original_benchmark.py`: main report, four measured cases, exact Lucene query-token diagnostics for full text versus E5's retained prefix, and four plots in SVG/PDF/PNG formats.

## Measured result

| Metric | BM25 | E5 dense |
| --- | ---: | ---: |
| nDCG@5, linear gain | 0.397464 | 0.457588 |
| MAP@1000 | 0.232874 | 0.276498 |
| Recall@1000 | 0.668104 | 0.773767 |

For nDCG@5, E5 wins 31 queries, BM25 wins 21 and five tie. For AP@1000, E5 wins 36 and BM25 wins 21. The paired 95% percentile bootstrap interval for mean nDCG@5 difference is [-0.004629, +0.129424], so its average advantage is uncertain at that interval level. The corresponding AP interval is [+0.003196, +0.085179]. These results apply to this original query set and incomplete reference judgments.

The fresh BM25 TREC file is byte-identical to the earlier original-query run. Dense retrieval exports 57,000 eligible-document hits with pinned model identity. Both engines use the same query snapshot and corpus. Existing source data and earlier runs are unchanged.

## Validation and limitations

The complete suite now passes **107 tests**, with zero failures/skips. New tests include hand-calculated scores, cutoff behavior, missing-positive denominators, zero/empty-query policies, malformed/duplicate judgments, deterministic paired resampling, run corruption detection, three independent gain-convention cross-checks and a real tiny-corpus end-to-end comparison with failed-check cleanup.

The 57-query primary analysis retains all 65 judgments referring to 57 unavailable article IDs, including three positive judgments. Its available-corpus sensitivity is separately named. The main nDCG convention uses supplied grades as gains, matching BEIR/trec_eval; additional gain mappings are explicitly labeled.

Top-five judgment coverage is 96.49% for BM25 and 79.30% for E5. Unjudged E5 articles cannot be called confirmed failures. The report also distinguishes the headline/background-linking task from the custom linguistic challenge study, identifies dense 512-token truncation versus full-text BM25 as a confound, and records the lack of publication-date and near-duplicate filters. Retrieval latencies overlapped local development and memory pressure, so no controlled speed conclusion is made.

## Evidence and outputs

- [Main benchmark report](ORIGINAL_57_BENCHMARK.md)
- [Measured case studies](ORIGINAL_57_CASE_STUDIES.md)
- `artifacts/evaluations/original-57/`: metrics, per-query CSV, paired intervals, independent raw outputs and provenance manifest.
- `artifacts/original_benchmark_provenance.json`
- `artifacts/runs/bm25-original-benchmark/`
- `artifacts/runs/dense-original/`
- `artifacts/analysis/original-57/case_evidence.json`
- `reports/figures/original-57/`: four standalone figures in three formats.
- `artifacts/test-results-original-benchmark.xml`

Next is review and assessment of the separate 20-query suite, followed by its evaluation, the comparison demo and final paper. These 57-query results must not be copied onto the new query IDs or described as negation/temporal robustness measurements.
