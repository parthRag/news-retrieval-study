# Project comparison review — 2 November 2026

**Recommendation:** keep `news-retrieval-study` as the main implementation and demo, and incorporate the controlled rewrite experiment from Hamsini's project. Her project currently has the stronger design for studying vocabulary mismatch; ours is the more complete foundation for the assigned news-retrieval submission. Neither project's current evidence justifies a universal claim that one retrieval method is better.

Reviewed peer repository: https://github.com/HamsiniGururaj/robust-news-retrieval at commit `7b73bb339d9ea3827375ec10aa2e1c4bb67bde06`. The original proposal, code, tests, saved runs, per-topic results, rewrite sheet and progress/roadmap documents were inspected. This review does not establish which report the instructor received or whether a domain change has been approved.

## What was verified

- Her **100 tests passed** in an isolated Python 3.12 review environment. These are lightweight tests, including fake-encoder/FAISS fixtures; they do not regenerate real-model corpus embeddings.
- Recomputed evaluation for **15 saved runs**: 12 TREC-COVID runs and three SciFact runs. All **7,200 per-topic metric values** match their saved six-decimal CSVs within rounding tolerance.
- Reproduced all **13 saved significance tables** from the saved per-topic scores, including confidence intervals and Holm-adjusted p-values. Numerical reproducibility does not validate every experimental assumption.
- Reconstructed five RRF runs. Scores agree within approximately `5e-12`; a few internal near-tied ranks differ after score serialization, with unchanged top-1,000 document sets. This is a small reproducibility detail, not evidence the main findings are fabricated.
- Re-ran our existing final-deliverables validator: numerical reproduction and document/package checks pass. Its 153-test and 7,196-native-comparison counts refer to the recorded prior checks, not a newly executed full test/native-evaluation campaign in this review. Individual contribution confirmations remain pending as recorded.
- Full-corpus retrieval/encoding for her project was not rerun: its large data and embeddings are held outside GitHub. Our published reports and scores were not revised by this review.

Evidence is saved in `artifacts/reviews/2026-11-02-project-comparison/`. The peer tests use a temporary evaluation environment, not an exact recreation of her pinned Colab environment.

## Comparison

| Dimension | Our project | Her project | Assessment |
| --- | --- | --- | --- |
| Domain | 594,589 eligible news articles | 171,331 eligible TREC-COVID scientific documents; SciFact smoke test | Ours fits the assigned news problem directly. The larger corpus alone does not make the research stronger. |
| Retrieval systems | BM25, E5-base-v2, exact FAISS search, RRF | The same main retrieval methods | Both have substantive implementations; architecture alone is not a reason to discard either. |
| Existing relevance reference | 57-topic supplied-qrel headline/background-linking adaptation | 50-topic TREC-COVID ad-hoc benchmark with supplied judgments | Hers is a cleaner fit for controlled short-query robustness; ours is a different task and should remain labeled as an adaptation. |
| Vocabulary-mismatch experiment | 40 separate custom needs; no completed original-versus-equivalent-rewrite study | Two rewrites for each of 50 topics, scoring the changes against unchanged qrels | Hers currently answers the vocabulary-robustness question more directly. |
| Required linguistic diagnostics | Ten custom queries each for vocabulary mismatch, negation, homonyms and temporal constraints | Mainly paraphrase/de-anchoring/alias rewrites; one temporal rewrite; NevIR negation evaluation is pending | Ours covers the requested categories. Her completed rewrite suite is not a substitute for the assignment's negation/homonym tests. |
| Custom ground truth | 1,444 evidence-backed preliminary AI decisions; human review not completed | Benchmark qrels reused for self-verified rewrites; no new article relevance labeling needed if intent is preserved | Hers avoids our custom-label subjectivity, but only while rewrite equivalence and judgment coverage hold. |
| Statistics and diagnostics | Query/family intervals, gain sensitivity, coverage and quality/input-visibility analyses | Paired changes, randomization tests, bootstrap intervals, Holm correction, judged-only nDCG and bpref | Her controlled comparisons and incomplete-judgment metrics are worth adopting. Our evidence and family-uncertainty handling are worth retaining. |
| Demo and delivery | Working local article-inspection/live-search demo; four-page brief; 19-page supporting report; reproducibility release | CLI/Colab pipeline and an eight-page original proposal; final report, error-analysis tool and demo are listed as pending | Ours is further along for presentation and submission. |

Raw scores across these projects are not directly comparable: corpus, task, topics, judgment pools and metric cutoffs differ. Her TREC-COVID nDCG@10 cannot be ranked against our news nDCG@5 as if they were the same test.

## What her research establishes, and what needs tightening

The reproduced TREC-COVID standard nDCG@10 values show a useful pattern:

| System | Original keywords | Rewrite A | Rewrite B |
| --- | ---: | ---: | ---: |
| BM25 | 0.6389 | 0.3029 | 0.2398 |
| E5 | 0.5627 | 0.4301 | 0.3972 |
| RRF | 0.7312 | 0.4541 | 0.3945 |

E5 loses less than BM25 under these rewrites, and RRF's large original-query advantage mostly disappears. This is a stronger vocabulary-mismatch result than comparing unrelated easy and hard queries. It remains conditional on the rewrite set and incomplete reference labels.

1. **Re-check semantic equivalence independently.** The rewrite sheet records single-annotator verification, not an independent second assessor. Topic 5's narrative includes drug testing in animal models and cell culture, whereas a rewrite lists infection in mice, hamsters and monkeys. Topic 12's narrative includes exposed and infected people, whereas rewrite A mentions exposed people. These are concrete candidates for review, not a claim that all rewrites are invalid. If a genuine correction follows inspection of results, document it and retain the original version.
2. **Do not treat judgment coverage as a correction factor.** BM25 Judged@10 falls from 0.958 to 0.408/0.396, and E5 from 0.686 to 0.534/0.506. Judged-only nDCG and bpref are useful sensitivity checks, but do not supply the missing labels or identify the true size of the drops. Her progress report acknowledges this; some stronger causal wording should be softened.
3. **Cluster pooled feature analyses by topic.** The feature/permutation analysis pools 100 rewrites derived from 50 original topics. Resample or permute at the topic level. Importantly, each current phenomenon group contains distinct topic IDs (42 paraphrase, 34 de-anchoring, 16 alias, seven entity-description, one temporal); the dependence issue should not be used to dismiss every phenomenon-specific test or the separately analyzed 50-topic A/B comparisons.
4. **Finish the required diagnostics.** NevIR is planned, not implemented in the reviewed checkout. There is no completed homonym suite; its single temporal paraphrase is not a broad test of before/after constraints. Add the assignment's nDCG@5 alongside existing @10 metrics.
5. **Harden resume identity before reusing the encoder.** `encode_shards` skips a shard when its completion JSON exists without checking source/model/prefix identity. A tiny probe replacing `d1` with `d2` and changing the prefix silently reused `d1`. Our pipeline's stronger source/config checks should be kept. This is a future reuse risk, not proof her published embeddings were wrong.
6. **Measure truncation in model tokens.** The statement that few documents exceed 400 whitespace words does not establish that 512-token E5 truncation is negligible, particularly for scientific text. Report actual token coverage before making that claim.

Our main limitation also needs direct attention: the 40-query custom study uses preliminary AI labels and compares different information needs. It is useful as a diagnostic, but currently cannot isolate the causal effect of vocabulary mismatch. Our 57-topic benchmark uses supplied judgments, so the entire project should not be characterized as AI-judged.

## A useful integration path: Core 2018 on the existing news corpus

Her repository already includes 50 Core 2018 topics and 26,233 exported qrel rows. Read-only lookup in our local document store found:

| Coverage check | Count |
| --- | ---: |
| Exported judgment rows | 26,233 |
| Rows whose document ID is present locally | 26,226 |
| Missing rows | 7 |
| Positive judgment rows | 3,948 |
| Positive rows with an eligible local document | 3,947 (99.97%) |

This removes much of the practical need to abandon the news domain. NIST publishes the [50 topics and assessor judgments](https://trec.nist.gov/data/core2018.html). All 26,233 exported query–document grades were also compared with the official NIST file and match exactly; source hashes are recorded in the coverage evidence.

**ID overlap is not full corpus equivalence.** Before scoring or presenting this as a benchmark, audit our corpus version/text/eligibility, retain the missing positive in the primary denominator and report the missing-document sensitivity. The local collection has a different document count from the intended full WaPo v2 collection. Any resulting scores must be labeled as a Core 2018 evaluation on the available corpus unless official equivalence is established; high qrel coverage does not make it an official reproduction.

Once that audit passes, the existing news vectors and BM25 index can be reused. No new document-encoding job is needed if the indexed text and model settings remain fixed. New original and rewritten queries still need retrieval and evaluation. The COVID rewrites themselves cannot be transplanted into news topics: new news rewrites must preserve those topics' own narratives.

## Recommended next work

1. Keep our engine/demo/package as the main codebase. Preserve her experiment artifacts and authorship as an identifiable contribution.
2. Complete the Core 2018 corpus/reference audit, then run the 50 original ad-hoc news topics on the existing engines.
3. Apply her rewrite protocol to a fixed, manageable selection of those news topics, with a second person's intent review before retrieval. Use topic-level paired changes, nDCG@5/@10, MAP, coverage and incomplete-judgment sensitivities.
4. Keep our 40-query suite as a separate diagnostic and carry out the planned human relevance review. Retain her TREC-COVID results as a separate cross-domain robustness experiment if the report has room; do not pool news/COVID/custom scores into one mean.
5. Write one group report around news retrieval, controlled vocabulary robustness and separate constraint diagnostics. Record actual contributions now supported by the independent work. Acknowledge remaining validity limits rather than selecting whichever benchmark gives the preferred winner.

If the instructor has explicitly approved a scientific-domain project and only one unmerged research study can be continued, her controlled rewrite study has the stronger research design. Under the stated news-retrieval assignment and the requirement for a working demo, our implementation plus her experimental design is the stronger practical route.
