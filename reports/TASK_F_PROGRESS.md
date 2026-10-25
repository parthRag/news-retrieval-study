# Task F: complete custom evaluation and working demo

> Historical milestone: current assessment status and planned human review are described in [Assessment method](ASSESSMENT_METHOD.md).

This milestone completes the remaining custom article assessments, publishes the complete designated-pool evaluation, and adds a tested local comparison demo. The original 57-query benchmark, corpus, frozen custom queries, existing retrieval rankings and all earlier judgments are preserved. The user requested leaving the final PDF until the implementation selected for submission is ready.

## Assessment and evaluation

All **737/737 query–article pairs** in the equal-depth top-20 union are assessed, adding **549** to the preserved 188-pair snapshot. The distribution is **398 grade 0, 110 grade 1, 229 grade 2**. All labels carry full-available-text reading acknowledgments, source hashes, literal evidence with Unicode offsets, rationale, confidence and AI disclosure. Thirteen same-query exact-content reuses explicitly identify their source decision; no identical-content grade conflicts remain. These full-article AI judgments support preliminary comparison, with human review planned next under the method linked above.

| Evaluation set / metric | BM25 | E5 dense | RRF hybrid |
| --- | ---: | ---: | ---: |
| Original 57 nDCG@5 | 0.397464 | 0.457588 | 0.490028 |
| Original 57 MAP@1000 | 0.232874 | 0.276498 | 0.333199 |
| Custom 20 nDCG@5 | 0.462126 | 0.489668 | Not evaluated |
| Custom 20 pooled MAP@1000 | 0.400600 | 0.468318 | Not evaluated |
| Custom 20 Precision@5 | 0.530000 | 0.530000 | Not evaluated |

The custom MAP denominator includes all known positives in the completed shallow pool. It does not establish exhaustive corpus recall. Only about 3% of each top-1,000 list is judged, although all top-20 hits are judged. Both custom mean-difference bootstrap intervals include zero. V05 remains in the average with zero known relevant pool documents.

The deeper pool changes ideal-ranking denominators, so nDCG@5 differs from the historical top-five snapshot despite unchanged top-five ranks and labels. Precision@5 remains 0.53 for both. E5 leads vocabulary mismatch and word sense means, BM25 leads temporal means, and negation depends on the metric: E5 slightly leads nDCG@5 while BM25 leads pooled MAP. This supports query-level diagnosis over a general model-superiority claim.

The evaluator validates complete pool membership and component ranks, source and run hashes, all quote spans, all query coverage, and preservation of earlier records. It publishes to a fresh directory atomically. Primary linear gains and exponential-gain sensitivity were independently cross-checked with **588 native `trec_eval` comparisons**, all passing. Further scenarios remove medium-confidence positive credit or grade-1 relevance; they are sensitivity scenarios, not label-accuracy intervals.

See [the full results](CUSTOM_20_DEPTH20.md), [737-decision evidence appendix](CUSTOM_20_DEPTH20_EVIDENCE.md), `artifacts/evaluations/custom20-depth20-v1/`, and six PNG/SVG/PDF research figures under `reports/figures/custom20-depth20/`. The input-visibility audit now covers all 737 pairs; 568 truncate at the E5 token budget. Content quality remains measured without changing the baselines: dense has 38 empty-body top-20 slots, BM25 zero.

## Demo implementation

`src/news_ir/demo.py` serves a local interface using the Python standard library. The HTML/CSS/JavaScript assets are packaged with the project; there is no frontend build step. Startup binds saved queries, runs, qrels and evaluation files to their hashes and the shared corpus. The UI offers:

- Two-engine comparisons for the 20 custom queries and three-engine comparisons for the 57 original topics.
- Five, ten or twenty saved results per engine, per-query scores, overlap counts, aggregate results and frozen relevance rules.
- Full article dialogs with grades, rationales, exact evidence highlights and an E5 retained-input toggle.
- Live CPU retrieval with BM25, E5 and RRF; progress, error recovery and explicit unjudged results without fabricated relevance metrics.
- Responsive desktop/mobile layouts, local-only HTTP binding, a static asset allowlist and no shell interpolation of query text.

Live BM25 and E5 execute sequentially in separate processes to respect the Mac's memory limit. Fusion uses both complete top-1,000 lists. Live experiments never write over saved rankings or judgments. Query text is passed as a literal argument after `--`; article text is rendered through safe text nodes. Evidence uses Unicode code points to match Python offsets even when text contains supplementary characters.

Run `.venv/bin/python -m news_ir.demo`, then open **http://127.0.0.1:8765**. See [DEMO_GUIDE.md](DEMO_GUIDE.md) for required files and a presentation sequence. Saved comparisons need no model inference or GPU. The live smoke query completed in roughly 50 seconds of server work including cold process/model startup; this is not a controlled speed benchmark.

## Review and test evidence

The complete automated suite passed: **138 tests**. New coverage exercises incomplete-pool publication refusal, earlier-record preservation, exact pool ranks, atomic failure cleanup, native metric agreement, evidence validation, duplicate reuse rules, stable pending-reader positions, query-specific demo grades, live isolation/fusion, failure recovery, HTTP parsing and routes. A legacy test fixture was updated to supply its own CLI argument list after the assessment recorder gained `--scope`; application argument validation remains strict.

The real-browser check verified **all 77 saved queries at depth 20 and 77 selected full-article endpoints**. It also exercised custom/original switching, three-engine display, full-body equality, evidence highlights matching literal quotes, retained input length, a 390-pixel viewport without horizontal overflow, and actual full-corpus live retrieval. Live results correctly had no inferred labels or metrics. No JavaScript exceptions were observed. Scientific figures and browser screenshots were visually inspected.

| Evidence | Location |
| --- | --- |
| Full automated results | `artifacts/test-results-depth20-demo.xml` |
| Frozen input/output hashes, recomputed metrics and 737 source/visibility checks | `artifacts/custom20_depth20_validation.json` |
| Real-browser and live-search results/screenshots | `artifacts/demo-validation/` |
| Original and custom native metric outputs | Corresponding `artifacts/evaluations/` folders |

`pip check` found no broken requirements. Repeat normal checks with:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
.venv/bin/python scripts/validate_custom_depth20.py
```

## Remaining work and submission readiness

The required retrieval, 20-query suite, nDCG/MAP evaluation, failure analysis and runnable demo are implemented. Next, select one bounded diagnostic experiment rather than adding another large model. A symmetric empty-body/duplicate-content ablation can test whether the measured dense failures are sensitive to corpus quality. Controlled negation pairs can test ranking sensitivity separately, but require judgments for changed information needs; existing labels cannot simply be reused after a polarity change.

Then consolidate the existing methods, results and failure evidence into a paper narrative. The four-page interim submission needs a concise architecture/status summary, generated results, limitations, resource measurements, remaining-work plan and contribution matrix. Index disk sizes and one cold demo query are measured; controlled peak RAM and a representative warmed latency distribution remain unmeasured. Do not report disk size as memory use.

Group number, member identities, actual contribution ownership and GitHub URL remain explicit placeholders. No repository has been published and no member contributions are invented. The final four-page PDF is deferred as requested. [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) tracks every required submission item.
