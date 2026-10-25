# Fixed reciprocal-rank fusion: original 57-query benchmark

This exploratory extension combines the saved full-corpus BM25 and E5 top-1,000 rankings. It uses equal weights and **k=60**, with score `sum(1 / (60 + rank))`, retains the top 1,000 unique IDs, and breaks score ties by ascending document ID. No relevance labels, training, parameter search or additional GPU encoding were used.

| Metric | BM25 | E5 dense | RRF hybrid |
| --- | ---: | ---: | ---: |
| nDCG@5, linear gains | 0.397464 | 0.457588 | 0.490028 |
| MAP@1000 | 0.232874 | 0.276498 | 0.333199 |
| Recall@1000 | 0.668104 | 0.773767 | 0.804364 |
| P@5 | 0.529825 | 0.557895 | 0.642105 |
| Judged fraction at 5 | 0.964912 | 0.792982 | 0.926316 |

![Three-engine comparison](figures/current-study/original_57_three_engines.png)

## Paired uncertainty

Descriptive paired bootstrap over queries, 10,000 draws, seed 20261025. This is an exploratory third-system comparison, not a confirmatory new held-out experiment.

| Difference | Measure | Mean | 95% percentile interval | Hybrid wins / ties / losses |
| --- | --- | ---: | --- | --- |
| RRF − BM25 | ndcg_at_5 | +0.092564 | [+0.043437, +0.141907] | 35 / 6 / 16 |
| RRF − BM25 | ap_at_1000 | +0.100325 | [+0.076740, +0.125850] | 50 / 1 / 6 |
| RRF − E5 dense | ndcg_at_5 | +0.032440 | [-0.015396, +0.078998] | 32 / 6 / 19 |
| RRF − E5 dense | ap_at_1000 | +0.056701 | [+0.033320, +0.080961] | 44 / 0 / 13 |

The hybrid has higher means, but its nDCG@5 interval against E5 includes zero. The AP difference intervals against both baselines exclude zero under this descriptive bootstrap. Incomplete and unequal judgment coverage still limits interpretation.

## Sensitivity and validation

| Gain/policy | BM25 nDCG@5 | E5 nDCG@5 | RRF nDCG@5 |
| --- | ---: | ---: | ---: |
| primary | 0.397464 | 0.457588 | 0.490028 |
| exp2_gain | 0.336885 | 0.395883 | 0.414015 |
| news2019_gain | 0.354580 | 0.411801 | 0.436894 |
| available_corpus | 0.397464 | 0.458154 | 0.490028 |

All **1,624** additional RRF comparisons against independent native `trec_eval` passed across four policies. Derived ordinal scores preserve published rank order during cross-checking. The original 57-query baselines reproduce exactly. All original qrels, queries and engine rankings are preserved. These are original background-linking results, not results on the custom linguistic stress queries.

Fusion averages about **0.69 ms/query over saved rankings** on this run. This excludes both searches, startup, file loading and article lookup; it is not end-to-end hybrid latency. Live hybrid search still incurs both engines' costs. No extra vector index is required; the existing BM25 and dense index folders occupy approximately 367.6 MiB and 1.72 GiB on disk, respectively. Disk size is not peak RAM.

## Reproduce

```sh
.venv/bin/news-ir fuse --output artifacts/runs/rrf-original-k60-new
.venv/bin/python scripts/evaluate_fusion.py --fusion-run artifacts/runs/rrf-original-k60-new --output artifacts/evaluations/rrf-original-57-new
.venv/bin/python scripts/report_current_study.py
```

The report script reads the canonical saved evaluation. Evaluation and retrieval commands refuse to overwrite existing outputs.

Method reference: [Cormack, Clarke and Buettcher, SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).
