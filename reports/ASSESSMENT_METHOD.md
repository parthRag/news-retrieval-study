# Assessment method and planned human review

The custom-query results are a **preliminary comparison using thorough, full-article AI judgments**. Human review is planned as the next validation stage and has **not yet been completed**. The separate 57-topic benchmark uses the supplied TREC relevance judgments.

For the 40 custom information needs, the reference covers all 1,444 query–article pairs in the union of BM25 and E5's top 20. Assessors read the full available title and body, applied the frozen 0–2 relevance rubric, and recorded a rationale, source hash, literal quotations and character offsets. Exact same-query/full-content duplicates could reuse a documented decision. A targeted review of five difficult extension cases was completed before scoring; one event-date judgment was revised, with both the original decision and audit preserved.

Coverage and evidence checks verify the recorded source text and reproducibility. They do not establish that every relevance decision is correct. Current custom nDCG and pooled MAP therefore measure agreement with this preliminary reference. The shallow pool and full-body versus E5-prefix input difference remain separate limitations.

## Next validation stage

1. Begin human review with a balanced selection across all 40 queries and both engines' candidates, including relevant articles, hard negatives, borderline grades and unsupported temporal dates. Keep engine identities, scores and ranks hidden during assessment where practical.
2. Have reviewers read the complete available articles against the same frozen rubric. Record their own grades and evidence separately; do not replace the preliminary labels in place.
3. Independently double-review part of the selection and adjudicate disagreements. Report agreement only for articles actually reviewed independently by multiple people, and publish the achieved review coverage.
4. Expand review beyond the initial selection as resources allow. Recompute a separately versioned human-reviewed comparison once its stated coverage is complete, then compare it with the preserved preliminary results.

No human-reviewed metric or agreement result is claimed yet. Planned review should not be described as completed validation.

## Records and review sheets

- `annotations/custom40_v2/assessments.all40.jsonl` preserves the current reference and its assessor provenance. Frozen queries, labels, protocols and numerical evaluation artifacts remain unchanged.
- `annotations/query_review.csv` is an unfilled **query-definition review** sheet for the original 20 questions. It is not a set of human article-relevance judgments.
- `annotations/human_review/reviews.template.csv` is an empty template for future article-level reviews. Completed reviews should be saved as a new version with reviewer identity, grade, rationale and evidence.
- Historical progress reports describe the stage reached at their saved milestone. This document records the current interpretation and next validation step.
