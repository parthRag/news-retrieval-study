# Task E: all 20 queries assessed at top five

> Historical milestone: current assessment status and planned human review are described in [Assessment method](ASSESSMENT_METHOD.md).

Status on 25 October 2026: **complete for the top-five union across all 20 fixed custom queries**. The assistant read and judged the remaining 172 query–article pairs, bringing coverage to 188/188 priority pairs. The previous 16-pair pilot remains intact. The larger depth-20 pool is not yet complete: **549 of 737 pairs remain unassessed**. Custom MAP and the comparison demo remain pending; the PDF is still deferred.

## Results and the negation question

| Category | BM25 nDCG@5 | E5 nDCG@5 | E5 wins / BM25 wins / ties |
| --- | ---: | ---: | --- |
| Vocabulary mismatch | 0.187804 | 0.399308 | 3 / 0 / 2 |
| Negation | 0.643358 | 0.664864 | 3 / 2 / 0 |
| Word sense | 0.726768 | 0.745269 | 4 / 1 / 0 |
| Temporal | 0.501678 | 0.304918 | 2 / 2 / 1 |
| All 20 | 0.514902 | 0.528590 | 12 / 5 / 3 |

Both engines have **P@5 = 0.53** and 100% assessed top-five coverage. Gains are linear 0–2, with exp2 sensitivity retained. V01, V05 and T01 have no positives in this shallow assessed set; they remain in the declared mean with zero scores. That does not mean the corpus contains no relevant documents for them. IDCG uses assessed positives and may change with deeper judgments.

The broader negation result is slightly favorable to E5, unlike the earlier single Ebola example. A semantic bi-encoder can match related content without enforcing logical polarity. BM25 also does not reason about negation. Their results here mix exact matching, available evidence, article coverage, sparse records and duplication. The report links primary research on this distinction and avoids attributing every grade-0 article to failed negation reasoning.

Mean E5-minus-BM25 nDCG is **+0.013688** with descriptive paired bootstrap interval **[-0.166230, +0.178314]**. Neither this interval nor the small category samples establish a general winner. The preliminary labels are full-article AI judgments; human review is planned next under the method linked above.

## Assessment work

All records include the actual corpus ID, 0–2 grade, rationale, confidence, AI origin, source-content hash, full-available-text reading acknowledgment and exact evidence spans. Exact duplicates were read once and retained under their distinct IDs. Only repeated extraction abbreviation glossaries were omitted from the reading display; substantive article bodies were not summarized or clipped for assessment. Any truncated tool output was reread before grading.

The distribution is **91 grade 0, 30 grade 1 and 67 grade 2**, with 164 high- and 24 medium-confidence decisions. Confidence is self-assessment, not calibrated accuracy. Medium-confidence records include scope ambiguity and temporal bounds; their rationales explain the judgment rather than inferring dates from IDs or assumed publication dates.

Several articles contain both requested and opposing evidence. For example, N01's negative-headline article reports a separate Seattle study with no employment reduction. Such articles are assessed on their full content under the frozen mixed-article rule. Temporal records with insufficient timing evidence can receive grade 0 even if topically relevant; this does not establish that their real-world event dates fell outside the interval.

## Additional diagnostics

- E5 retrieves **18 empty-body slots** among its 100 top-five results; BM25 retrieves none. E5 has 20 bodies shorter than 200 characters, versus none for BM25. These are descriptive counts; no baseline filtering was applied.
- There are **9 additional exact-content duplicate slots for E5 and 5 for BM25**, counted within each query's top five. Near-duplicate detection was not applied.
- The exact E5 tokenizer truncates **141/188** assessed records. Every quotation's visibility inside its passage-prefixed, 512-token input is recorded separately from its full-text relevance grade.
- A **fresh local full-index CPU search reproduced H02's exact five IDs and order**, all identical `Results` titles with empty bodies. Scores differed from Kaggle by at most **1.79e-7**. This rules out a one-off cloud-export explanation for that particular pattern; it does not prove the internal scoring cause.
- An exhaustive per-query robustness analysis allows each medium-confidence grade to vary across 0/1/2 while keeping high-confidence grades fixed. The overall difference can range from **-0.122492 to +0.152397**. These are extreme scenarios, not statistical intervals or new labels. High-confidence assessments may also be wrong.

## Code and artifacts

`src/news_ir/custom_study.py` adds complete-suite coverage checks, provenance verification, top-five-only evaluation, independent native checks, descriptive paired uncertainty, extreme grade sensitivity, per-query/category exports and atomic publication. It deliberately does not expose MAP from the incomplete pool.

`scripts/read_assessment_batch.py` prints full stored priority records in fixed packet order and identifies exact duplicates. `scripts/record_top5_decisions.py` saves explicitly supplied assistant decisions after validating source quotes; it does not assign grades. It rejects duplicate decisions and preserves earlier decisions after a failed write.

`scripts/evaluate_custom_top5.py` runs the full-suite top-five evaluation. `scripts/report_custom_top5.py` regenerates the report, evidence appendix, content-quality counts, tokenizer visibility and figures. The previous pilot reporting tool now accepts an explicit scope for the shared tokenizer audit; pilot decisions and metrics are unchanged.

Key outputs:

- `annotations/ai_study_v1/assessments.top5.jsonl`
- `artifacts/evaluations/custom20-top5-v1/` — metrics, 20-row CSV, qrels, native checks, sensitivity, validation and manifest
- `reports/CUSTOM_20_TOP5.md`
- `reports/CUSTOM_20_ASSESSMENT_EVIDENCE.md` — every decision with source evidence
- `annotations/ai_study_v1/evidence_visibility.top5.json` and `content_quality.top5.json`
- `reports/figures/custom20-top5/` — two figures, each in PNG/SVG/PDF
- `artifacts/analysis/custom20-top5/local_h02_search.json`

## Verification and remaining work

The full automated suite passed **121 tests in 29.09 seconds**. All **168** additional native `trec_eval` checks passed, covering both systems' per-query and macro nDCG@5/P@5 under linear and exp2 gains, including zero-positive topics. Source quotes and hashes validate for all 188 decisions. Both new figures were visually inspected.

Reproduce the evaluation into a new directory with:

```sh
.venv/bin/python scripts/evaluate_custom_top5.py --output artifacts/evaluations/custom20-top5-rechecked
.venv/bin/python scripts/report_custom_top5.py
.venv/bin/python -m pytest -q
```

Next is the remaining depth-20 assessment, which enables pooled MAP@1000 and checks whether the shallow nDCG ideal rankings are stable. Then build the demo. The most informative targeted extensions are a symmetric sparse-content/deduplication ablation and minimal-pair negation tests, because they can separate the confounds observed here. Keep any altered runs and labels separate from these fixed baseline results.
