# Symmetric content-quality ablation

This is a post-hoc diagnostic over the original 20-query study. No baseline ranks or judgments were changed. Each rule applies equally to each engine’s original top 20, preserves surviving order and never refills from rank 21 or later. All possible replacements are already assessed.

| Rule | BM25 nDCG@5 | E5 nDCG@5 | BM25 P@5 | E5 P@5 |
| --- | ---: | ---: | ---: | ---: |
| Frozen baseline | 0.462126 | 0.489668 | 0.530000 | 0.530000 |
| Remove empty bodies | 0.462126 | 0.549151 | 0.530000 | 0.600000 |
| Exact deduplication | 0.466366 | 0.505305 | 0.530000 | 0.560000 |
| Both | 0.466366 | 0.543424 | 0.530000 | 0.600000 |

Empty-body removal raises E5 nDCG@5 by +0.059483 and P@5 by +0.07, while BM25 is unchanged. The India-cricket query H02 rises from zero to 0.4788; N03 rises from 0.1461 to 0.3601 but remains below the BM25 baseline. These observations show sensitivity to article quality without establishing the sole cause of a failure or generalization to held-out queries.

Empty means a body containing no non-whitespace characters, regardless of title. Duplicate means identical SHA-256 of the complete shared title-plus-body contents; only the first occurrence survives. No relevance threshold or near-duplicate heuristic is used.

Fixed-reference nDCG retains all original document labels and ideal-ranking gains. A separate unique-content nDCG@5 credits a content hash only once, leaves duplicate ranks in place at zero gain and computes IDCG from all unique contents in the joint pool. It is a different measure and is labeled accordingly.

| Rule | BM25 unique-content nDCG@5 | E5 unique-content nDCG@5 |
| --- | ---: | ---: |
| baseline | 0.458148 | 0.482057 |
| no_empty_body | 0.458148 | 0.541540 |
| deduplicate | 0.473559 | 0.515281 |
| no_empty_body_and_deduplicate | 0.473559 | 0.553400 |

Both rules retain five results per engine for every query, but this was observed, not guaranteed by the filtering logic. P@5 always divides by five. Ordinary document-level nDCG can credit repeated positively judged content; it should not be presented as a diversity measure. No MAP is reported on these bounded candidate lists.

The result was motivated by observed errors and is exploratory, without a held-out test. It evaluates candidate filtering, not a cleaned full-corpus index. Detailed rankings, per-query CSV, metrics and hashes are under `artifacts/evaluations/quality-top20-v1/`. The recheck output reproduces the numerical result.

```sh
.venv/bin/python scripts/evaluate_quality_ablation.py --output artifacts/evaluations/quality-rechecked
```
