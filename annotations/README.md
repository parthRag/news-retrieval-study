# Custom query suite and assessment records

The current custom comparison uses thorough, full-article AI judgments as a preliminary reference. Human review is planned next and has not yet been completed; see the [assessment method and review plan](../reports/ASSESSMENT_METHOD.md). The original `qrel.jsonl` continues to label only the original 57 queries.

`custom_queries.draft.jsonl` contains the 20 previously drafted questions: five each for vocabulary mismatch, negation, word sense and temporal constraints. Every query has inclusion/exclusion rules and a 0–2 rubric. Temporal windows refer to events evidenced in article text; publication dates are unavailable. A missing assertion is not proof of its negation.

The exact query/rubric bytes are frozen in [ai_study_v1/queries.jsonl](ai_study_v1/queries.jsonl). Historical `draft_requires_human_review` fields are preserved for compatibility with existing run hashes. [The new protocol](ai_study_v1/protocol.json) records the assessment method, freeze timing, evidence rules and evaluation limits. `query_review.csv` is a blank query-definition review sheet; future article-level reviews belong under `human_review/`.

Both full-corpus depth-1,000 runs are ready:

- BM25: `artifacts/runs/bm25-custom-draft-depth1000/`
- E5: `artifacts/runs/dense-custom-draft/`

Their equal-depth top-20 union contains **737 query–article pairs**, including **188** in either engine's top five. Full articles in deterministic hash order are under `artifacts/assessments/custom20-v1/articles.blinded.jsonl`; this local packet omits engine, rank and score. Private rank provenance is stored separately. Corpus-text packets are excluded from code commits. The assistant has seen some earlier results, so perfect blindness is not claimed.

The current `assessments.depth20.jsonl` contains **737 assessments covering the complete top-20 union for all 20 queries**. It preserves all **188** earlier top-five records, including the **16** calibration-pilot assessments. Each stores a source-content hash, exact quotations and Unicode character offsets, rationale, confidence, assessor provenance and a full-available-article reading acknowledgment. Empty bodies remain empty; no external article is substituted. Thirteen same-query exact-content reuses have explicit source-ID provenance. See [the complete report](../reports/CUSTOM_20_DEPTH20.md) and [all 737 decisions with evidence](../reports/CUSTOM_20_DEPTH20_EVIDENCE.md). The earlier top-five and pilot snapshots remain intact.

Files under `ai_study_v1/`:

- `assessments.pilot.jsonl`: actual assistant decisions and evidence; no keyword-based grading.
- `qrels.pilot.jsonl`: 0–2 labels derived from those decisions, for these two queries only.
- `validation.pilot.json`: coverage and source-evidence validation.
- `metrics.pilot.json`: top-five pilot metrics, with linear primary and exp2 sensitivity gains.
- `evidence_visibility.pilot.json`: exact-tokenizer audit of evidence inside E5's input budget.

Current-study files are `assessments.depth20.jsonl`, `evidence_visibility.depth20.json` and `content_quality.depth20.json`. Metrics, derived qrels, coverage, 588 native cross-checks, category results, uncertainty and grade sensitivity are under `artifacts/evaluations/custom20-depth20-v1/`. All designated pairs are assessed; 398 have grade 0, 110 grade 1, and 229 grade 2. Historical `*.top5.*` files and `custom20-top5-v1/` evaluation outputs are preserved.

The evaluator requires complete designated-pool coverage before publishing pooled MAP. The ideal ranking uses known assessed positives and changes as the pool deepens; this explains the difference from the historical top-five nDCG. Current nDCG@5 is **0.462126 BM25 / 0.489668 E5**, pooled MAP@1000 **0.400600 / 0.468318**. MAP remains a shallow-pool estimate: only about 3% of each top-1,000 run is judged. Unjudged articles retain their original ranks with zero metric contribution and are not confirmed irrelevant. No independent human agreement statistic is available.

```sh
.venv/bin/python scripts/prepare_ai_assessment.py --output artifacts/assessments/custom20-v1-rebuilt
.venv/bin/python scripts/report_current_study.py
.venv/bin/python scripts/validate_custom_depth20.py
.venv/bin/python scripts/evaluate_custom_depth20.py --output artifacts/evaluations/custom20-depth20-rechecked
.venv/bin/python scripts/report_custom_depth20.py
```

Preparation never assigns grades. The report script reads canonical saved artifacts and validates existing pilot decisions. Existing pool outputs are never overwritten. Preserve the pilot snapshot when extending assessment into a new versioned file.

## Forty-query extension

[`custom40_v2/`](custom40_v2/README.md) preserves these 20 query records byte-for-byte and adds five new queries to each category, giving ten per category. New-query texts, rubrics and event windows were frozen before extension retrieval. This is a follow-up designed after seeing the original results; it is not a preregistration or an independent held-out study. The extension is complete:707 added decisions give 1,444 pairs across 40 queries. Human validation is the next planned stage. The original 737 judgments remain unchanged.
