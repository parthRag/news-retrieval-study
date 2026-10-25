# News Retrieval: BM25 vs. Neural Search under Vocabulary Mismatch

Repository separation: the current public final snapshot is https://github.com/parthRag/news-ir-bm25-dense-final; the original development repository is now private. Earlier repository-status entries below are historical.

Current validation plan: preliminary custom comparisons use full-article AI judgments; human review is planned next and has not yet been completed. See [assessment method](reports/ASSESSMENT_METHOD.md). The dated milestones below retain their historical status.

Planning baseline revised: 19 October 2026. Submission target: 23 October 2026, based on the user's five-day deadline. This file translates the original proposal and the subsequently supplied assignment into an implementation and research plan. The assignment defines the required deliverables; the proposal remains the foundation. Recommendations and mentor questions inside the proposal are project material, not additional user instructions.

## 1. The project in plain language

Build a dual-engine news search system: Engine A uses BM25 and Engine B uses a pretrained dense encoder with cosine similarity. Evaluate both on 20 custom complex queries covering negation, homonyms, temporal constraints, and vocabulary mismatch. The deliverables are a working comparison demo and a reproducible research report. Hybrid RRF is an implemented proposal extension evaluated on the original 57-query benchmark; the required custom comparison remains in progress.

The contribution is evidence about robustness, failure cases, and complementary retrieval. It does not require inventing or training a new neural model. Either engine winning, tying, or failing on a query is a valid result if the experiment is controlled and honestly reported. E5 is an embedding encoder; results about this model do not establish the capabilities of every LLM.

## 2. Dataset decision and verified local facts

The proposal recommends Common Core 2018 ad-hoc topics. The available files instead match the structure and topic range of the BEIR-style TREC-NEWS adaptation of the 2019 background-linking task. The user supplied this download source:

https://huggingface.co/datasets/liuqi6777/trec-news/tree/main

The supplied source exposes headline queries and a 0–4 label representation. A complete row-by-row audit on 24 October verified all 15,655 query-document judgment pairs against NIST's 2019 qrels: supplied grade 0 maps to gain 0 and positive grade g maps to 2^g (2, 4, 8, 16). Official topic IDs and canonical source-article IDs were also checked; none of the 57 canonical source articles is present in the local corpus. This verifies judgment/topic provenance, not full corpus or official protocol equivalence. An immutable upstream corpus revision remains unverified.

Full local inspection, recorded in `artifacts/dataset_audit.json`:

| Item | Finding |
|---|---:|
| Corpus records / unique IDs | 594,977 / 594,977 |
| Corpus bytes | 2,449,925,233 |
| Queries | 57 |
| Judgment rows | 15,655 |
| Grades 0 / 1 / 2 / 3 / 4 | 12,614 / 1,677 / 660 / 431 / 273 |
| Empty article bodies | 16,372 |
| Empty article titles | 4,305 |
| Both title and body empty | 388 |
| Median body length | 514 whitespace-separated words |
| 90th / 99th percentile body length | 1,168 / 2,741 words |
| Judged document IDs absent from corpus | 57 |
| Judgment rows referring to absent IDs | 65 |
| Absent-document judgments by grade | 62 grade 0; one each at grades 1, 2, 3 |
| Duplicate document IDs / duplicate judgment pairs | 0 / 0 |

All records parsed successfully. Every query has positive judgments. The schema contains only `_id`, `title`, and `text` for articles: publication dates, URLs, and other original WaPo metadata are unavailable in these files.

Keep the original project identity: **News Retrieval: BM25 vs. Neural Search under Vocabulary Mismatch**, with linguistic stress tests for negation, word sense, and temporal constraints. The downloaded articles can serve as the shared corpus for newly judged news-search queries. We do not need to redefine the main project as headline-based background linking.

Separate two evaluation tracks:

- **Required primary study:** the 20 custom queries and NEW relevance judgments defined for their exact information needs.
- **Supporting benchmark:** the downloaded 57 headline queries and their existing background-linking qrels, reported separately if time permits. These are not Common Core topics and must not be described as such.

The existing qrels cannot be copied to new custom queries. Even queries that mention the same subject can impose different exclusions, senses, dates, or relevance criteria. No further corpus acquisition is required to begin this project. Full equivalence to an official benchmark is not a prerequisite for evaluating custom queries on a documented corpus.

## 3. Objectives and questions

1. Compare BM25 and dense cosine retrieval on the same news corpus with nDCG@5 and MAP.
2. Identify when paraphrases and vocabulary mismatch help or hurt each engine.
3. Test whether rankings respect explicit negation, the intended sense of ambiguous words, and event-time constraints.
4. Diagnose per-query failures using actual article evidence, analyzer behavior, matching terms, and encoder input coverage.
5. Record latency, encoding cost, and index size as supporting practical measures.

Do not implement hard negation filters, automatic sense disambiguation, or date reasoning only for one baseline and then attribute the gain to the retrieval model. Such improvements require separate, labeled ablations. Hypotheses guide the study but must not determine which queries or results are retained.

## 4. Minimum complete system

### Data and document access

Keep source files unchanged. Stream the 2.45 GB corpus rather than loading all article text into Python dictionaries. Preserve IDs exactly as strings. Create a derived mapping from IDs to file offsets for efficient article display, or use SQLite metadata storage if the space budget permits. Convert local JSONL judgments to the evaluation library's required structure without changing grade meaning. Save SHA-256 hashes and record every derived-data policy.

Use the same eligible corpus for every retriever. Retain title-only articles; identify the 388 completely empty records and document whether they remain represented or are excluded consistently. For the optional original-query benchmark, keep original qrels, including missing-document positives in the denominators. Report their impact and an explicitly labeled available-corpus sensitivity analysis rather than silently deleting them.

For the optional original-query benchmark, seven query headlines exactly match titles still in the corpus. A title match alone does not establish that the article is the original query document. Resolve canonical source-article IDs from authoritative topic metadata before applying self-retrieval exclusions. Apply identical filters to all systems and save them in the manifest. Do not infer publication dates from UUIDs. No publication-date filter can be implemented reliably with the supplied metadata alone. The primary custom temporal queries must instead specify event-time conditions whose evidence can be read in the article text.

### BM25 lexical baseline

Use Lucene via Pyserini, indexing title plus full article body. Start with fixed `k1=0.9`, `b=0.4`, and save top 1,000 results for each query. Record the actual analyzer, stemming, stopword handling, title/body concatenation, and version. Decide these before inspecting final system comparisons. Never describe an analyzer as preserving negation without checking its behavior.

Task A now uses a project-local Python 3.12.9 environment and the existing Temurin Java 21.0.4 installation. Pyserini 1.5.0 and the tested dependency set are pinned. The implementation accesses the same Anserini BM25 searcher through Pyserini's Java bridge, avoiding an upstream Python search import that initializes API encoders. The tested analyzer retains stopwords and does not stem, and is identical at indexing and query time. Global Python/Java settings are unchanged.

### Dense baseline

Use `intfloat/e5-base-v2` as the principal encoder. Use its documented `query: ` and `passage: ` prefixes, attention-aware mean pooling, and L2 normalization. Embed title plus the beginning of the body within a **512-token total model input budget**, including prefix and special tokens. This is a token limit, not 512 words. Save model/tokenizer revisions, preprocessing, precision, and embedding dimension.

Store 768-dimensional embeddings and use FAISS `IndexFlatIP` for an initial exact baseline. At 594,977 documents, float32 vector values alone occupy 1,827,769,344 bytes, approximately 1.70 GiB. Keeping both an embedding matrix and FAISS index approximately doubles that vector storage; runtime text, models, and lexical index add more. Do not materialize all query-document scores simultaneously; search queries in batches. Never restrict the corpus to documents known relevant from qrels.

The central confound is document coverage: BM25 sees the full body while this dense baseline sees the beginning. Report it prominently. If resources allow one ablation, run BM25 on the exact same prefix text consumed by E5, alongside full-text BM25. This estimates the effect of input coverage. Passage-level dense indexing is a later extension because it multiplies encoding and storage costs.

### Optional hybrid extension

Fuse the two top-1,000 lists with reciprocal rank fusion:

`RRF(d) = sum(1 / (60 + rank_s(d)))`

Ranks start at one. An article absent from a component list contributes zero for that component. Deduplicate by document ID, use deterministic tie-breaking, and retain the top 1,000 fused results. Keep `k=60` fixed. Do not add raw BM25 and cosine scores, which have different scales.

### Shared research and demo services

Expose one retrieval interface used by both the evaluation runner and the demo. Keep indexing, encoding, ranking, fusion, evaluation, analysis, and presentation separate. A practical planned layout is:

```text
configs/               Frozen settings and experiment manifests
src/                   Data access, retrievers, fusion, evaluation
scripts/               Audit, indexing, encoding, experiment commands
annotations/           Custom queries, pooled relevance labels, review decisions
artifacts/             Audit, indexes, embeddings, saved runs, metrics
reports/               Tables, figures, paper source and exports
demo/                  Search and experiment comparison interface
```

Save TREC run files plus per-topic and aggregate machine-readable metrics. A displayed benchmark result must be traceable to a saved run, config, query file, and corpus hash.

## 5. The required 20-query suite

Use a provisional allocation of five queries per category. This allocation is our design choice; the assignment requires coverage of the named phenomena, not a prescribed category count. Queries can carry secondary phenomenon tags.

| Main category | Count | What it isolates |
|---|---:|---|
| Vocabulary mismatch | 5 | Relevant articles express the need using different terminology |
| Negation/exclusion | 5 | Explicit NOT, without, or exclusion conditions distinguish relevant from tempting nonrelevant articles |
| Homonyms/word sense | 5 | An ambiguous word has competing senses; surrounding context specifies the intended one |
| Temporal constraints | 5 | Events must fall within an explicit period or before/after a named event |

Use news topics actually supported by the corpus. Movie examples and Roman history in the assignment illustrate linguistic phenomena; they do not require changing the dataset. For homonyms, sports versus insect uses of “cricket” is an illustrative candidate, subject to corpus support. More generally, finance, technology, law, sports, and public policy can provide suitable ambiguity and lexical alternatives.

Each query record needs: stable query ID, exact text, primary/secondary categories, information need, mandatory constraints, excluded cases, temporal interpretation where applicable, and a written relevance rubric. For “right after,” define a precise window before evaluation. Distinguish event date from publication date. A query involving absence of a condition requires evidence; merely failing to mention the condition is not proof that it did not occur.

First conduct a feasibility check using corpus browsing and broad neutral searches to establish that plausible relevant articles and challenging alternatives exist. Avoid writing queries around an article one engine already ranks well. Freeze the final query suite and rubrics before the scored comparison. Keep drafts and reasons for any feasibility revisions; do not discard queries later because a system loses on them. Queries with no confirmed relevant articles require an explicit policy and must not silently disappear from aggregate results.

### New relevance judgments

1. Retrieve the top 20 articles from EACH engine for every custom query; union and deduplicate the candidates. This initial pool has at most 800 query-document pairs.
2. Randomize candidate order and hide engine identity, rank, and score from assessors. Read full article evidence for exclusions, sense, and event dates.
3. Judge each pair on a shared 0–2 scale: 0 = irrelevant or violates a mandatory constraint; 1 = relevant but incomplete; 2 = directly useful and satisfies all mandatory constraints. A document violating the query's explicit exclusion or date condition receives 0 even if it discusses the right subject.
4. Save the grade, evidence passage, rationale, assessor, and review status. Human review is required for labels represented as human judgments. Machine-generated suggestions remain provisional until actually reviewed.
5. Prioritize all articles appearing in either system's top five. Independent double-labeling of at least 20% was the original recommendation; it is optional validation under the user's later AI-only assessment authorization. Report actual coverage and any adjudication. Do not invent human agreement or describe a second pass by the same assistant as independent inter-assessor agreement.
6. Report pool depth, judged coverage, missing judgments, and the limitation of incomplete corpus-wide relevance knowledge. Before final metrics, verify that every returned top-five article from both frozen systems is judged. If an additional system or new configuration is reported, extend the pool as necessary and version the labels.

An equal-depth pool treats both engines symmetrically, but it is not an exhaustive relevance set. MAP must be interpreted as measured against the pooled known relevant documents. If capacity permits, deepen the pool and show score stability. Do not allow the existing background-linking labels to substitute for these judgments.

The proposal's meaning-preserving rewrites may be retained as an optional follow-up after this required suite. Negation already belongs in the primary custom study; NevIR is optional external validation, not a substitute for the assignment's custom negation queries.

## 6. Evaluation and statistical analysis

**Required primary measures: nDCG@5 and MAP for BOTH engines on the 20 custom queries.** Save per-query results, the overall mean, and descriptive category breakdowns.

For custom 0–2 judgments, the current AI diagnostic protocol uses linear grade gains (0, 1, 2), with `2^grade - 1` (0, 1, 3) as a saved sensitivity analysis. This revises the earlier exp2-primary plan to align primary gain handling with the original benchmark; the choice followed initial H01 inspection, so it is not preregistered. Use logarithmic rank discount and binary relevance `grade > 0` for average precision. MAP is the mean of per-query AP values. Freeze retrieval depth at 1,000 for saved runs and state this cutoff alongside reported MAP; known relevant documents beyond that depth contribute no precision terms. Include MAP@1000 as an explicit label where appropriate, rather than implying exhaustive full-corpus rankings.

Cross-check metrics on hand-worked small rankings and an established evaluator with the same gain convention. Never assume two libraries implement identical nDCG gain handling by default. A zero-relevant query has a declared zero-score policy and is flagged for interpretation. Unjudged articles are not verified nonrelevant: apply the documented evaluation convention while reporting judged fraction at 5/20 and pooling limitations.

Compare systems with paired query-level differences, win/tie/loss counts, and paired confidence intervals. With only 20 queries and five per category, avoid claiming broad statistical certainty from category means. If queries are paired variants of the same information need, resample the source needs together. Use fixed defaults; do not tune on the same 20 queries used for headline conclusions. Any added ablation must be separately named.

Failure analysis should distinguish observations from explanations. Check whether the query term is missing or stemmed, an ambiguous word has the wrong sense, a constraint is explicitly contradicted, a date lies outside the stated window, or relevant evidence is beyond the dense encoder's truncation boundary. Dense similarity is an observed score, not a faithful explanation of the model's reasoning. Include genuine wins and failures for both engines; do not invent balanced outcomes if the measurements are asymmetric.

The optional 57-query benchmark uses its own original qrels and must have a separate results table. Its 0–4 grades and historical gain conversion are distinct from custom 0–2 judgments. Retain the earlier missing-document audit and explain any sensitivity analysis. Do not mix the two query collections into a single headline average. NevIR, if run, also retains its own labels and paired metric.

## 7. The working demo

Build a dual-engine comparison interface. A user can select one of the 20 custom queries, inspect its category and constraints, or enter a new query. Show BM25 and dense rankings side by side with article titles, snippets, full text, and search latency.

For judged custom queries, show saved nDCG@5/AP, known relevance grades, and assessor evidence. Treat unjudged articles distinctly. An analysis view presents aggregate and per-category metrics, per-query differences, and representative failures linked to actual text. Optional RRF is an additional view after the required dual-engine demo is working.

Arbitrary queries produce live search results and latency, but have no relevance score until valid labels exist. The demo and evaluator share retrieval code. Precomputed benchmark results may support a reliable presentation, but live and saved views must be labeled accurately. Target local operation after models and indexes are available; GPU access should not be needed during the presentation.

## 8. Hardware and encoding plan

Recommended cloud configuration: one NVIDIA L4 with 24 GB VRAM, 4–8 CPU cores, at least 16 GB host RAM (32 GB preferred), and roughly 50 GB available persistent disk. A T4 with 16 GB VRAM is a suitable budget target for E5-base inference using a measured batch size. These are engineering recommendations, not measured throughput guarantees. No multi-GPU setup or from-scratch training is needed.

First benchmark 1,000–5,000 representative articles, including long inputs. Measure articles per second after warmup and peak memory. Estimate full runtime as `594977 / articles_per_second`, then budget separately for loading, tokenization, saving, and interruptions. Use batched inference, optional tested reduced precision, and checkpointed embedding shards with IDs so interrupted sessions resume correctly. Verify that resumed output has exactly one vector per eligible document.

This local machine is an eight-core ARM Mac with approximately 25 GiB free disk at inspection. Available RAM and GPU throughput have not been established. Avoid unnecessary full corpus copies and duplicate embedding formats. Encoding remotely and serving locally is the preferred schedule strategy. A smaller E5 model or explicitly labeled reduced-corpus pilot is a contingency if needed; a pilot cannot be reported as the complete benchmark.

## 9. Delivery plan through 23 October

Preparation began on 18 October with proposal review and corpus auditing. The assignment alignment below supersedes the earlier plan centered on 57 headline topics and 114 rewrites. Keep the original submission target rather than extending it when the calendar date changes.

| Date | Main work | Completion evidence |
|---|---|---|
| 19 Oct | Compatible environment, BM25, custom query/rubric drafting, GPU encoding pilot | Working lexical search; 20 feasible query drafts; encoding checkpoint and measured ETA |
| 20 Oct | Dense index, freeze queries and rubrics, retrieve both engines' candidate pools | Two saved runs; randomized annotation queue; annotation begins |
| 21 Oct | Complete/review custom judgments, evaluate nDCG@5 and MAP, analyze failures | Versioned qrels, per-query metrics, figures and evidence |
| 22 Oct | Complete dual-engine demo; finish report draft | Live comparison and full paper draft with actual results |
| 23 Oct | Reproduction checks, final report, slides and rehearsal | Runnable package, final paper, README, presentation fallback |

The current critical path is BM25 -> dense encoding -> symmetric candidate pooling -> explicitly disclosed AI assessments -> valid custom-query metrics. The user later authorized assistant judgment rather than waiting for human assessors. Human judgments remain optional independent validation; AI decisions must not be represented as human gold.

Mandatory: two engines, the 20-query linguistic stress suite, new judgments, nDCG@5, MAP, failure analysis, demo, report. The original 57-query benchmark and fixed RRF extension are now implemented. Additional paraphrases, NevIR, a reranker and passage indexing remain optional. GPU encoding is complete; the outstanding work is assessment, demo and reporting.

## 10. Research report and assignment coverage

Preserve the original proposal's motivation, literature review, lexical/dense methods, reproducibility controls, and failure-analysis ideas. Update the dataset role, primary query suite, evaluation metrics, and priorities. The original DOCX is unchanged; this blueprint records the revised implementation plan.

| Assignment requirement | Implementation evidence | Report coverage |
|---|---|---|
| Classic IR grounded in Manning Ch. 6/11 | Lucene BM25, documented analyzer and parameters | Ranking foundations, BM25 rationale, implementation |
| Neural embeddings and cosine ranking | E5, normalized vectors, FAISS search | Encoder formatting, representation, similarity, input limits |
| Same corpus for both engines | Shared eligible IDs and manifest | Data provenance, preprocessing, fair comparison |
| 20 complex queries | Frozen suite and relevance rubrics | Query design appendix and category rationale |
| Negation, homonyms, temporal conditions | Explicit examples and custom judgments | Separate descriptive results and failures for each phenomenon |
| nDCG@5 and MAP | Reproducible evaluator, two saved runs, custom qrels | Metric definitions, aggregate and per-query tables |
| Diagnose relative wins and failures | Evidence passages, measured rank differences | Detailed case studies, competing explanations, limitations |
| Working demo | Shared retrieval backend and comparison interface | Architecture, reproducibility and demonstration instructions |

Target roughly 10–15 substantive pages, subject to the course template, with appendices for all 20 queries, rubrics, annotation protocol, and additional results. Organize the paper as abstract; introduction; related work; ranking methods; corpus and query design; annotation; experimental setup; results; failure analysis; efficiency; limitations; conclusion; references.

Generate figures and tables from saved results. Report quality by category, per-query differences, judged coverage, and latency. Discuss corpus incompleteness, pooled judgments, small sample size, dense truncation, model-specific generalization, and any actual annotation limitations. Never invent numerical results or write conclusions in advance.

The final package contains the runnable demo, commands/environment, configs and model revisions, custom queries, reviewed labels, TREC runs, per-query metrics, figure scripts, and paper source/PDF. Corpus redistribution remains subject to its actual terms; the supplied mirror labels its license unknown.

## 11. Current state and next implementation step

Completed as of 24 October: both full retrieval engines, verified shared coverage of **594,589 articles**, and the **57-query original benchmark** requested by the user. Both original runs contain 57,000 hits. Main direct-grade nDCG@5 is **0.397464 BM25 / 0.457588 E5**, and MAP@1000 is **0.232874 / 0.276498**. All 3,248 independent native-evaluator comparisons passed; the full automated suite has **107 passing tests**. See `reports/ORIGINAL_57_BENCHMARK.md`, `reports/ORIGINAL_57_CASE_STUDIES.md` and `reports/TASK_C_PROGRESS.md` for results, uncertainty, judgment coverage and provenance.

Update on 25 October: the user authorized full-article AI relevance assessment and asked to defer the PDF. All 20 query/rubric records are now frozen byte-for-byte under `annotations/ai_study_v1/`, with a protocol superseding historical human-review gate fields. The equal-depth top-20 pool contains **737 pairs**, including **188** in either engine's top five. A calibration pilot has **16 assessed pairs covering both engines' top five for N03 and H01**. These are AI diagnostic labels; human fields remain blank. Remaining custom judgments and complete custom MAP are pending.

The fixed k=60 RRF extension is also complete on the original 57 queries: nDCG@5 **0.490028**, MAP@1000 **0.333199**, with **1,624** further independent metric comparisons passing. The full test suite reached **115 passing tests**. See `reports/TASK_D_PROGRESS.md`, `reports/RRF_EXPERIMENT.md` and `reports/CUSTOM_AI_PILOT.md`.

Next: assess the remaining 18 queries' top-five unions, complete deeper pool assessment and custom evaluation, then build the comparison demo and complete the report. Group details, contribution matrix and GitHub URL remain placeholders; no PDF is requested at this stage. Respect the Mac's 8 GiB memory limit. Original source datasets and prior artifacts are preserved. The earlier dated timeline is historical and does not imply that its dates were met.

Later update on 25 October: **all 20 top-five unions are now assessed**, with 188 AI decisions and verified full-text evidence. The above Task D milestone is historical. Current custom nDCG@5 is **0.514902 BM25 / 0.528590 E5**, with P@5 **0.53** for both; negation means are **0.643358 / 0.664864** (E5 wins three cases, BM25 two). All 168 new native metric checks passed, and the suite reached 121 passing tests. The remaining depth-20 pool contains 549 unassessed pairs, so custom MAP is still withheld. See `reports/TASK_E_PROGRESS.md` and `reports/CUSTOM_20_TOP5.md`. Next: deeper assessment and pooled MAP, then the comparison demo.

## Sources

Current milestone on 25 October supersedes the pending states above: **all 737 custom pooled pairs are assessed**, preserving the earlier 188 labels. Custom nDCG@5 is **0.462126 BM25 / 0.489668 E5** and pooled MAP@1000 **0.400600 / 0.468318**; all 588 native checks pass. These are AI diagnostic judgments and shallow-pool MAP estimates. The local demo now supports all 77 saved queries, article/evidence inspection, exact E5 input visibility, and live BM25/E5/RRF searches. Real-browser and live full-corpus smoke checks passed; the complete suite has **138 passing tests**. See `reports/TASK_F_PROGRESS.md`, `reports/CUSTOM_20_DEPTH20.md` and `reports/DEMO_GUIDE.md`. Next: a bounded diagnostic ablation, paper consolidation, then the deferred submission PDF with actual group/repository metadata.

- User proposal: `IR Proposal - Robust Lexical Neural and Hybrid Retrieval.docx`.
- Supplied mirror: https://huggingface.co/datasets/liuqi6777/trec-news
- BEIR dataset catalog and toolkit: https://github.com/beir-cellar/beir
- BEIR paper: https://arxiv.org/abs/2104.08663
- NIST 2019 task, topics, judgments and evaluation script: https://trec.nist.gov/data/news2019.html
- NIST 2019 judgments: https://trec.nist.gov/data/news/2019/newsir19-qrels-background.txt
- E5 model card: https://huggingface.co/intfloat/e5-base-v2
- Pyserini requirements and usage: https://github.com/castorini/pyserini
- NevIR: https://arxiv.org/abs/2305.07614
- NVIDIA T4 specifications: https://www.nvidia.com/en-us/data-center/tesla-t4/
- NVIDIA L4 specifications: https://www.nvidia.com/en-us/data-center/l4/


## Final-deliverables update

The user has now requested final deliverables. The four-page brief and 15-page research report are generated under `deliverables/`, with editable sources, an architecture SVG and a reproducibility archive. The symmetric quality ablation is complete: empty-body removal within fixed judged top-20 candidates raises E5 nDCG@5 from 0.489668 to 0.549151 while BM25 is unchanged. This is post-hoc evidence, separate from frozen baseline rankings and labels. The final automated suite has 140 passing tests. See `DELIVERABLES.md` and `reports/TASK_G_FINAL_DELIVERABLES.md`. Actual group/member/contribution metadata and the GitHub URL remain placeholders; nothing is uploaded or published. Earlier statements that PDF creation or quality ablation are pending are historical milestones.


## Group 5 metadata and repository preparation

Group 5 is Parth Raghuvanshi (2023A7PS0574P), Sushruth Reddy Challa (2023A7PS0504P), Hamsini G (2023A7PS0006P) and Kritika Pandey (2023A7PS0022P), for Information Retrieval under faculty mentor Abhinav Kumar. The brief is now `deliverables/5_NewsIR_BM25_Dense.pdf`. Each member is assigned 25% ownership/review responsibility; completed-work attribution remains factual. Local Git is initialized; authenticated remote creation under `parthRag/news-ir-bm25-dense` remains pending. See `CONTRIBUTING.md` and `reports/GITHUB_HANDOFF.md`. No historical dates or member commit authors are fabricated.

Query-extension update, 25 October: the completed 20-query study is preserved, and a separate 40-query version adds five new information needs per category. The resulting ten-per-category suite has frozen query text, rubrics, explicit temporal bounds and a topic-family map. New relevance assessment and 40-query metrics are pending; existing numerical findings still describe the completed original 20. See `reports/CUSTOM_40_EXTENSION.md`. Parth's corrected student ID is **2023A7PS0574P** in the active metadata and regenerated reports.


Completed expansion,25 October 2026: all707 follow-up pairs assessed, bringing the designated pool to 1,444. BM25/E5 combined nDCG@5 is 0.513337/0.436211 and pooled MAP0.442759/0.407164. All 737 initial decisions are byte-preserved. The demo covers 97 distinct queries and 117 saved-view entries; the current suite passes 153 tests with 7,196 native metric comparisons. The four-page submission and 19-page supporting report now show the changed pattern and limitations. See `reports/CUSTOM_40_DEPTH20.md`. Earlier pending extension statements are historical.


GitHub publication completed: the account identity parthRag was authenticated, public repository https://github.com/parthRag/news-ir-bm25-dense was created, and the existing main branch was pushed. The report now uses this verified link. Individual contribution confirmations remain distinct from equal component ownership. Earlier authentication-pending notes are historical.
