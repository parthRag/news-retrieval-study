# Task D: custom AI assessment setup and hybrid experiment

> Historical milestone: current assessment status and planned human review are described in [Assessment method](ASSESSMENT_METHOD.md).

Status on 25 October 2026: **first stage complete; full custom-query study remains in progress**. The user authorized assistant full-article relevance assessment and deferred the submission PDF. No human approval is required to continue this diagnostic study. Group details, member contributions and GitHub URL remain placeholders.

## Completed in this stage

| Component | Result |
| --- | --- |
| Fixed hybrid retrieval | RRF over both saved top-1,000 rankings, equal weights, k=60, deterministic document-ID tie break |
| Hybrid benchmark | All 57 original queries, four evaluation policies, per-query results, descriptive paired bootstrap |
| Independent verification | 1,624 additional native `trec_eval` comparisons passed |
| Custom suite freeze | All 20 exact query/rubric records preserved; five queries in each category |
| Equal-depth article pool | 737 query–article pairs from top 20 per engine; 188 cover the top-five union |
| AI assessment pilot | 16 full available article records read, graded and evidenced; N03 and H01 top-five unions complete |
| Evidence validation | Exact quotations, Unicode character offsets, source-content hashes, pool membership, AI disclosure |
| Input visibility audit | Exact local E5 tokenizer; 10/16 pilot records truncated, two empty-body records |
| Reports and figures | Hybrid report, pilot failure analysis, PNG/SVG/PDF research figures; submission PDF deferred |

The current hybrid is a saved-run retrieval component. It is not yet exposed through a live comparison interface. No additional GPU run or corpus re-encoding was needed.

## Measured results

These are the **original 57-query benchmark** results, with linear supplied-grade gains:

| Metric | BM25 | E5 dense | RRF hybrid |
| --- | ---: | ---: | ---: |
| nDCG@5 | 0.397464 | 0.457588 | 0.490028 |
| MAP@1000 | 0.232874 | 0.276498 | 0.333199 |
| Recall@1000 | 0.668104 | 0.773767 | 0.804364 |
| P@5 | 0.529825 | 0.557895 | 0.642105 |

The hybrid has higher means under all tested gain conventions. Its nDCG@5 difference interval against E5 is **[-0.015396, +0.078998]**, which includes zero. The AP difference interval against E5 is **[+0.033320, +0.080961]**. These are descriptive paired percentile intervals over this query set, not a new held-out generalization claim. Existing judgment coverage remains incomplete and differs by engine.

The custom pilot illustrates two contrasting outcomes, using newly recorded AI grades:

| Custom query | BM25 nDCG@5 | E5 nDCG@5 | Observation |
| --- | ---: | ---: | --- |
| N03: explicit non-airborne explanation plus contact conditions | 0.660840 | 0.146068 | E5 retrieves opposite-polarity/sparse records; BM25 also has one failing top result |
| H01: cricket farming for human food | 0.794498 | 1.000000 | BM25 drifts into crop-agriculture articles; E5 keeps the required food entity |

These **two queries are a pilot**, not the full 20-query result. Grades concern the requested information need, not the truth of every statement in an article. The ideal ranking uses assessed positives and may change with deeper pooling. MAP is withheld until the designated pool is complete. E5 is a pretrained embedding encoder; this experiment is not testing an LLM generating answers.

See [RRF_EXPERIMENT.md](RRF_EXPERIMENT.md) and [CUSTOM_AI_PILOT.md](CUSTOM_AI_PILOT.md) for per-query rankings, uncertainty, sensitivity and interpretation limits.

## Implementation changes

`src/news_ir/fusion.py` adds validated saved-run fusion and three-system evaluation. Inputs must match corpus/query identity and full coverage; component engine identities, index manifests and counts are checked. Run files carry hashes and provenance. The evaluator checks that compared baselines are the actual fusion components. Outputs publish atomically and existing directories are never overwritten. The new CLI is `news-ir fuse`; `scripts/evaluate_fusion.py` evaluates it against original qrels.

`src/news_ir/assessment.py` freezes query bytes, pools equal-depth candidates, separates article packets from rank provenance, validates individual AI decisions and gates top-five evaluation on complete per-query coverage. It rejects fabricated/misaligned quotes, duplicate/out-of-pool decisions, invalid grades, missing AI disclosure and missing full-reading acknowledgment. Validation cannot prove that a reader understood an article; the actual decisions and rationales remain reviewable.

`scripts/prepare_ai_assessment.py` prepares packets but **does not generate relevance grades**. `scripts/report_current_study.py` validates existing decisions, audits actual tokenizer visibility and regenerates reports/figures. The 16 pilot decisions were made by the assistant reading the stored articles; source evidence offsets are computed and verified afterward.

`evaluation.py` now accepts validated RRF run files alongside existing engine exports. The original two-engine benchmark command retains its engine-role checks. Original data, qrels and ranked outputs were preserved. Documentation now reflects AI authorization instead of waiting for human labels. Primary custom gains are linear, with exp2 sensitivity explicitly retained; the earlier blueprint's exp2-primary choice is recorded as superseded, without claiming preregistration.

## Verification

- Full suite: **115 tests passed** in 32.42 seconds; the eight new fusion/assessment cases also passed after the final scoring-output changes.
- New coverage includes hand-calculated fusion overlap/ties, invalid parameters and duplicate ranks, saved-run evaluation and component provenance, independent native metrics, evidence tampering, partial-pool evaluation gating, and cleanup after failure.
- Dependency check: **no broken requirements**.
- Hybrid native evaluator: **1,624 additional checks passed** across primary, exp2, NIST-gain and available-corpus policies. Together with the earlier baseline work, 4,872 benchmark metric comparisons have passed.
- Pilot: all **16** decision records validated against source text; 100% assessed top-five coverage for the two reported queries. There are **172** remaining top-five-priority pairs and **721** total unassessed pool pairs.
- Figures were generated as PNG, SVG and PDF and visually inspected. Figure PDFs are individual research plots, not the deferred submission document.

## Remaining project work, in order

1. Read and assess the remaining 18 queries' top-five unions. Date-constrained queries require event-time evidence; uncertain cases stay pending.
2. Complete the depth-20 pool and calculate custom pooled nDCG@5/MAP@1000, judged coverage, per-category results and failure analysis. Preserve the pilot version and use a new expanded assessment file.
3. Build the comparison demo with saved-result mode and clearly identified live search, side-by-side rankings, full articles, constraints and evidence. Respect the Mac's 8 GiB memory limit.
4. Run one targeted robustness extension: constraint-flip pairs or content-quality/deduplication ablation. Keep its runs and claims separate from the fixed baseline.
5. Assemble the interim PDF after the selected experiments and demo are ready. Group identities, contributions, repository URL and final filename remain placeholders until supplied.

We cannot yet claim that only 20–25% remains: assessment, the interface and report assembly are substantial outstanding deliverables. The submission checklist tracks actual completion rather than assigning an unsupported percentage.
