# Integrated news and controlled-rewrite study


The main project keeps the existing news corpus, BM25/E5 indexes and article-inspection demo. Hamsini G’s controlled TREC-COVID experiment is imported byte-for-byte with attribution, and the design is applied to 50 Core 2018 topics on the available news corpus. Scores are always separate by dataset and formulation.


## Separate effectiveness results


**nDCG@5**
| Separate experiment | BM25 | E5 | RRF |
| --- | --- | --- | --- |
| News · original titles | 0.4454 | 0.3878 | 0.4453 |
| News · provisional rewrites | 0.2868 | 0.4113 | 0.4447 |
| News · official descriptions | 0.3796 | 0.3736 | 0.4129 |
| COVID · original keywords | 0.6687 | 0.5746 | 0.7504 |
| COVID · rewrite A | 0.3269 | 0.4208 | 0.4792 |
| COVID · rewrite B | 0.2694 | 0.4303 | 0.4200 |


**nDCG@10**
| Separate experiment | BM25 | E5 | RRF |
| --- | --- | --- | --- |
| News · original titles | 0.3859 | 0.3630 | 0.4222 |
| News · provisional rewrites | 0.2629 | 0.4045 | 0.4184 |
| News · official descriptions | 0.3405 | 0.3625 | 0.4133 |
| COVID · original keywords | 0.6389 | 0.5627 | 0.7312 |
| COVID · rewrite A | 0.3029 | 0.4301 | 0.4541 |
| COVID · rewrite B | 0.2398 | 0.3972 | 0.3945 |


**MAP@1000**
| Separate experiment | BM25 | E5 | RRF |
| --- | --- | --- | --- |
| News · original titles | 0.2068 | 0.2040 | 0.2573 |
| News · provisional rewrites | 0.1275 | 0.2208 | 0.2266 |
| News · official descriptions | 0.1664 | 0.1855 | 0.2344 |
| COVID · original keywords | 0.2030 | 0.2040 | 0.2617 |
| COVID · rewrite A | 0.0560 | 0.1542 | 0.1278 |
| COVID · rewrite B | 0.0532 | 0.1357 | 0.1139 |


## core18: paired changes and uncertainty



**ndcg_at_5**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite − bm25_title | -0.158580 | [-0.257731, -0.064878] | 0.016798 | 14/5/31 |
| dense_rewrite − dense_title | +0.023426 | [-0.050183, +0.097049] | 1.000000 | 22/10/18 |
| rrf_rewrite − rrf_title | -0.000609 | [-0.082141, +0.084715] | 1.000000 | 20/6/24 |
| dense_rewrite-dense_title − bm25_rewrite-bm25_title | +0.182006 | [+0.078417, +0.290456] | 0.016798 | 30/3/17 |
| bm25_description − bm25_title | -0.065817 | [-0.150852, +0.016475] | 0.820718 | 20/7/23 |
| dense_description − dense_title | -0.014225 | [-0.093440, +0.064262] | 1.000000 | 21/12/17 |
| rrf_description − rrf_title | -0.032416 | [-0.104634, +0.037950] | 1.000000 | 18/14/18 |
| dense_description-dense_title − bm25_description-bm25_title | +0.051592 | [-0.055550, +0.165539] | 1.000000 | 25/3/22 |


**ndcg_at_10**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite − bm25_title | -0.122947 | [-0.199356, -0.047477] | 0.016098 | 15/2/33 |
| dense_rewrite − dense_title | +0.041549 | [-0.017671, +0.104077] | 1.000000 | 27/6/17 |
| rrf_rewrite − rrf_title | -0.003785 | [-0.075223, +0.071010] | 1.000000 | 23/4/23 |
| dense_rewrite-dense_title − bm25_rewrite-bm25_title | +0.164497 | [+0.084803, +0.249818] | 0.001600 | 37/0/13 |
| bm25_description − bm25_title | -0.045400 | [-0.122315, +0.028744] | 1.000000 | 18/4/28 |
| dense_description − dense_title | -0.000419 | [-0.065464, +0.064300] | 1.000000 | 26/6/18 |
| rrf_description − rrf_title | -0.008876 | [-0.070619, +0.055139] | 1.000000 | 22/5/23 |
| dense_description-dense_title − bm25_description-bm25_title | +0.044980 | [-0.044033, +0.137190] | 1.000000 | 27/1/22 |


**ap_at_1000**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite − bm25_title | -0.079314 | [-0.118929, -0.041474] | 0.002100 | 13/0/37 |
| dense_rewrite − dense_title | +0.016797 | [-0.006310, +0.042751] | 0.772323 | 28/0/22 |
| rrf_rewrite − rrf_title | -0.030667 | [-0.066690, +0.006247] | 0.504450 | 19/0/31 |
| dense_rewrite-dense_title − bm25_rewrite-bm25_title | +0.096111 | [+0.059463, +0.135286] | 0.000800 | 37/0/13 |
| bm25_description − bm25_title | -0.040414 | [-0.080927, -0.000519] | 0.312569 | 18/0/32 |
| dense_description − dense_title | -0.018459 | [-0.054732, +0.019383] | 0.772323 | 27/0/23 |
| rrf_description − rrf_title | -0.022858 | [-0.058995, +0.015355] | 0.772323 | 19/0/31 |
| dense_description-dense_title − bm25_description-bm25_title | +0.021955 | [-0.021533, +0.064833] | 0.772323 | 30/0/20 |


**condensed_ndcg_at_10**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite − bm25_title | +0.004383 | [-0.063259, +0.075760] | 1.000000 | 23/1/26 |
| dense_rewrite − dense_title | +0.058115 | [+0.011934, +0.107096] | 0.147985 | 29/6/15 |
| rrf_rewrite − rrf_title | +0.051637 | [-0.004910, +0.114655] | 0.677532 | 29/2/19 |
| dense_rewrite-dense_title − bm25_rewrite-bm25_title | +0.053732 | [-0.016145, +0.123649] | 0.833317 | 31/0/19 |
| bm25_description − bm25_title | -0.005870 | [-0.073813, +0.061337] | 1.000000 | 20/4/26 |
| dense_description − dense_title | -0.005523 | [-0.065459, +0.054981] | 1.000000 | 24/4/22 |
| rrf_description − rrf_title | +0.018560 | [-0.036843, +0.076961] | 1.000000 | 24/3/23 |
| dense_description-dense_title − bm25_description-bm25_title | +0.000348 | [-0.077578, +0.078878] | 1.000000 | 24/1/25 |


**bpref**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite − bm25_title | -0.035475 | [-0.077263, +0.006460] | 0.620338 | 20/1/29 |
| dense_rewrite − dense_title | +0.041351 | [+0.014155, +0.073450] | 0.045495 | 29/3/18 |
| rrf_rewrite − rrf_title | +0.010385 | [-0.021399, +0.044422] | 1.000000 | 24/0/26 |
| dense_rewrite-dense_title − bm25_rewrite-bm25_title | +0.076827 | [+0.033896, +0.120157] | 0.006399 | 33/0/17 |
| bm25_description − bm25_title | -0.019781 | [-0.055857, +0.017086] | 1.000000 | 19/2/29 |
| dense_description − dense_title | -0.001631 | [-0.041902, +0.041490] | 1.000000 | 24/3/23 |
| rrf_description − rrf_title | -0.001456 | [-0.035588, +0.034878] | 1.000000 | 26/1/23 |
| dense_description-dense_title − bm25_description-bm25_title | +0.018150 | [-0.023959, +0.060492] | 1.000000 | 27/1/22 |


**Judgment coverage:**
| Formulation | BM25 Judged@10 | E5 Judged@10 | RRF Judged@10 |
| --- | --- | --- | --- |
| title | 0.9600 | 0.7160 | 0.9340 |
| description | 0.7260 | 0.6960 | 0.8280 |
| rewrite | 0.6020 | 0.7460 | 0.8040 |


## covid: paired changes and uncertainty



**ndcg_at_5**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite_a − bm25_original | -0.341788 | [-0.438331, -0.243596] | 0.000800 | 8/4/38 |
| dense_rewrite_a − dense_original | -0.153852 | [-0.251718, -0.061008] | 0.004600 | 13/7/30 |
| rrf_rewrite_a − rrf_original | -0.271248 | [-0.369038, -0.170067] | 0.000800 | 11/4/35 |
| dense_rewrite_a-dense_original − bm25_rewrite_a-bm25_original | +0.187936 | [+0.084563, +0.292615] | 0.003000 | 31/3/16 |
| bm25_rewrite_b − bm25_original | -0.399303 | [-0.512360, -0.283316] | 0.000800 | 9/0/41 |
| dense_rewrite_b − dense_original | -0.144288 | [-0.257006, -0.027556] | 0.018698 | 15/4/31 |
| rrf_rewrite_b − rrf_original | -0.330395 | [-0.434187, -0.224909] | 0.000800 | 11/1/38 |
| dense_rewrite_b-dense_original − bm25_rewrite_b-bm25_original | +0.255015 | [+0.132526, +0.379532] | 0.001200 | 39/0/11 |


**ndcg_at_10**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite_a − bm25_original | -0.336068 | [-0.419084, -0.253161] | 0.000800 | 5/1/44 |
| dense_rewrite_a − dense_original | -0.132672 | [-0.215444, -0.055255] | 0.003600 | 13/0/37 |
| rrf_rewrite_a − rrf_original | -0.277063 | [-0.366428, -0.185094] | 0.000800 | 8/0/42 |
| dense_rewrite_a-dense_original − bm25_rewrite_a-bm25_original | +0.203396 | [+0.119058, +0.290379] | 0.000800 | 34/0/16 |
| bm25_rewrite_b − bm25_original | -0.399126 | [-0.500860, -0.294010] | 0.000800 | 8/0/42 |
| dense_rewrite_b − dense_original | -0.165514 | [-0.262694, -0.066164] | 0.003600 | 15/2/33 |
| rrf_rewrite_b − rrf_original | -0.336717 | [-0.430769, -0.242391] | 0.000800 | 9/1/40 |
| dense_rewrite_b-dense_original − bm25_rewrite_b-bm25_original | +0.233612 | [+0.132316, +0.336900] | 0.000800 | 37/0/13 |


**ap_at_1000**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite_a − bm25_original | -0.147002 | [-0.189869, -0.106846] | 0.000800 | 5/0/45 |
| dense_rewrite_a − dense_original | -0.049755 | [-0.084423, -0.016582] | 0.005399 | 16/0/34 |
| rrf_rewrite_a − rrf_original | -0.133904 | [-0.175934, -0.095173] | 0.000800 | 7/0/43 |
| dense_rewrite_a-dense_original − bm25_rewrite_a-bm25_original | +0.097247 | [+0.062932, +0.134250] | 0.000800 | 41/0/9 |
| bm25_rewrite_b − bm25_original | -0.149820 | [-0.199418, -0.103001] | 0.000800 | 6/0/44 |
| dense_rewrite_b − dense_original | -0.068283 | [-0.106078, -0.030320] | 0.001400 | 13/0/37 |
| rrf_rewrite_b − rrf_original | -0.147808 | [-0.197094, -0.098898] | 0.000800 | 7/0/43 |
| dense_rewrite_b-dense_original − bm25_rewrite_b-bm25_original | +0.081537 | [+0.053449, +0.111448] | 0.000800 | 40/0/10 |


**condensed_ndcg_at_10**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite_a − bm25_original | -0.116821 | [-0.196024, -0.041256] | 0.040796 | 16/1/33 |
| dense_rewrite_a − dense_original | -0.022034 | [-0.068311, +0.024255] | 0.408859 | 19/6/25 |
| rrf_rewrite_a − rrf_original | -0.043517 | [-0.101781, +0.012738] | 0.408859 | 21/3/26 |
| dense_rewrite_a-dense_original − bm25_rewrite_a-bm25_original | +0.094788 | [+0.013925, +0.173333] | 0.132487 | 33/0/17 |
| bm25_rewrite_b − bm25_original | -0.122880 | [-0.206359, -0.035920] | 0.061594 | 14/0/36 |
| dense_rewrite_b − dense_original | -0.047233 | [-0.108869, +0.013538] | 0.408859 | 17/2/31 |
| rrf_rewrite_b − rrf_original | -0.078686 | [-0.137682, -0.019110] | 0.077992 | 15/2/33 |
| dense_rewrite_b-dense_original − bm25_rewrite_b-bm25_original | +0.075646 | [-0.011846, +0.161102] | 0.401560 | 33/0/17 |


**bpref**
| Comparison (A − B) | Mean change | 95% interval | p Holm | Wins/ties/losses |
| --- | --- | --- | --- | --- |
| bm25_rewrite_a − bm25_original | -0.165932 | [-0.217413, -0.116762] | 0.000800 | 10/0/40 |
| dense_rewrite_a − dense_original | -0.043000 | [-0.085734, -0.001630] | 0.048095 | 17/0/33 |
| rrf_rewrite_a − rrf_original | -0.095229 | [-0.140934, -0.051148] | 0.000800 | 16/0/34 |
| dense_rewrite_a-dense_original − bm25_rewrite_a-bm25_original | +0.122932 | [+0.080650, +0.167209] | 0.000800 | 38/0/12 |
| bm25_rewrite_b − bm25_original | -0.157457 | [-0.215237, -0.100980] | 0.000800 | 10/0/40 |
| dense_rewrite_b − dense_original | -0.061580 | [-0.104266, -0.018649] | 0.012199 | 17/0/33 |
| rrf_rewrite_b − rrf_original | -0.110157 | [-0.161130, -0.058998] | 0.000800 | 13/0/37 |
| dense_rewrite_b-dense_original − bm25_rewrite_b-bm25_original | +0.095877 | [+0.056230, +0.138567] | 0.000800 | 38/0/12 |


**Judgment coverage:**
| Formulation | BM25 Judged@10 | E5 Judged@10 | RRF Judged@10 |
| --- | --- | --- | --- |
| original | 0.9580 | 0.6860 | 0.9340 |
| description | 0.9320 | 0.8220 | 0.9800 |
| rewrite_a | 0.4080 | 0.5340 | 0.5620 |
| rewrite_b | 0.3960 | 0.5060 | 0.5500 |


## What the results can support

The primary robustness estimand is the within-topic change from original to rewritten query. A positive E5-minus-BM25 change difference means E5 held up better; it does not necessarily mean E5 is the best absolute ranker. Bootstrap/sign-flip tests use topics as observations, with Holm adjustment within each metric's eight-comparison family. Cross-domain scores are not pooled.

Core 2018 primary scores retain all 26,233 source qrels, including one unavailable positive. The seven absent and eleven empty-document pairs are listed in the corpus audit. An available-corpus sensitivity reuses the same rankings. High judgment-ID coverage does not establish official WaPo v2 text equivalence, so this is an available-corpus adaptation.

The 50 news rewrites were AI-authored and frozen before retrieval; independent human intent review is pending. Their scores reuse NIST human relevance labels only conditionally on preserving the original narrative. The official-description experiment changes query length/detail and is a formulation diagnostic. Do not describe either as a completed independently human-verified paraphrase experiment.

The imported COVID query rewrites retain their original single-annotator verification status. Topics 5 and 12 were flagged during review; omission sensitivity is saved separately, without editing original queries or primary results. Original score-based CSVs reproduce. Integrated metrics preserve published ranks via ordinal scores, so score-tie handling can cause small differences from the historical CSVs. Added topic-mean feature tests use 50 observations rather than treating 100 related rewrites as independent; their estimand differs from the original pooled feature analysis.

Condensed nDCG and bpref are sensitivity views for incomplete judgments. Neither supplies unjudged relevance or removes all pool bias. The earlier 57-topic background-linking and 40-query custom diagnostics retain their own results; custom relevance labels remain preliminary, with human review planned.

## Attribution, implementation and reproduction

Hamsini G: independently developed the controlled COVID rewrite experiment, rewrite-validation tooling, retrieval/evaluation pipeline and paired statistical analyses. Source commit `7b73bb339d9ea3827375ec10aa2e1c4bb67bde06` and all imported file hashes are recorded under `studies/`.

Integration adds Core 2018 news formulations/audit/runs, explicit @5 metrics, incomplete-judgment sensitivities, rank-preserving evaluation, topic-mean feature analysis, batched query-only retrieval, and demo/report integration. The existing document embeddings and frozen earlier experiments are reused without changing their results.

```sh
.venv/bin/python scripts/evaluate_integrated_study.py --study covid --output artifacts/evaluations/covid-recheck
.venv/bin/python scripts/evaluate_integrated_study.py --study core18 --native --output artifacts/evaluations/core18-recheck
.venv/bin/python scripts/validate_integrated_study.py
.venv/bin/python -m news_ir.demo
```

Install the pinned lock or the `evaluation` optional dependencies. Saved-run numerical verification does not require corpus/model downloads; fresh retrieval and article lookup do. Existing evaluation directories are refused. New human reviews should be saved separately, never silently substituted into frozen results.

