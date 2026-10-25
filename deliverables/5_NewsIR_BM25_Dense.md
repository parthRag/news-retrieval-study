# News Retrieval under Vocabulary Mismatch
### BM25, neural search and hybrid retrieval
**Group 5 · Information Retrieval**  
**Faculty mentor:** Abhinav Kumar  
Parth Raghuvanshi — 2023A7PS0574P<br>Sushruth Reddy Challa — 2023A7PS0504P<br>Hamsini G — 2023A7PS0006P<br>Kritika Pandey — 2023A7PS0022P

## 1. Primary objective
Find out when a news search engine benefits from semantic matching and when exact wording still matters. We compare BM25 with E5 dense retrieval over the same articles, focusing on vocabulary mismatch, negation, ambiguous words and event dates. The aim is a working comparison demo and an evidence-based account of their strengths and failures. E5 is a neural bi-encoder; the findings concern this model and setup, rather than all LLMs.

## 2. Dataset and evaluation criteria
**Selected dataset:** [TREC-News mirror — liuqi6777/trec-news](https://huggingface.co/datasets/liuqi6777/trec-news). The downloaded corpus has **594,977 records**. Excluding 388 records with no title or body leaves **594,589 articles** for both engines. Title-only articles remain in the baseline so the two systems search the same IDs.

We evaluate two distinct tasks. The **57 original background-linking topics** have **15,655 supplied relevance judgments**. Our **40 custom queries** have ten questions per category: vocabulary mismatch, negation, word sense and temporal constraints. The original 20 are preserved; 20 follow-up questions add ransomware, bail reform, Java/Mercury senses and dated disaster responses. Wording, inclusion rules and event windows were frozen before follow-up retrieval, after viewing the initial results. This is an exploratory extension, not an independent held-out replication.

**Success measures:** nDCG@5 measures how well the first five results are ordered by relevance; MAP@1000 measures recovery and ordering of known relevant articles across the saved top 1,000. We also report Precision@5, category means, judged coverage and paired query-bootstrap intervals. AP divides by all known positives for the query. Main nDCG gains equal relevance grades: 0–4 for supplied judgments and 0–2 for the custom study.

**Assessment scope and next validation:** the current comparison uses thorough, full-article **AI judgments** for all **1,444 query–article pairs** in the equal-depth top-20 union: 737 preserved initial decisions and 707 added decisions. Each judgment follows a frozen 0–2 rubric and has a rationale, source hash and quoted evidence. **Human review is planned next**, beginning with balanced cases across all 40 queries and adjudication of disagreements; it has not yet been completed. The custom results are therefore preliminary. Grade 0 fails a mandatory constraint, 1 gives limited qualifying detail, and 2 gives substantive support. Every top-20 hit is assessed, but only about 3% of each top-1,000 list is judged, so custom MAP is a **shallow-pool estimate**. Unjudged hits keep their ranks with zero contribution; all 40 queries remain in the averages, including V05 with no pooled positive.


<!-- PAGE -->

## 3. Related research: approach, findings and relevance
**Thakur et al. (2021), [BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663).** The paper evaluates ten retrieval systems across 18 datasets. BM25 is a robust baseline; reranking and late-interaction methods have strong average quality at greater computational cost. This supports keeping BM25 as a serious comparator and examining different query types.

**Wang et al. (2022; revised 2024), [Text Embeddings by Weakly-Supervised Contrastive Pre-training](https://arxiv.org/abs/2212.03533).** E5 learns text embeddings through contrastive training on text pairs and reports strong transfer on BEIR/MTEB tasks. We use a released E5 checkpoint to test whether this semantic representation helps with news queries whose wording differs from relevant articles.

**Weller, Lawrie and Van Durme (2024), [NevIR: Negation in Neural Information Retrieval](https://aclanthology.org/2024.eacl-long.139/).** The authors compare documents differing in negation. Many retrievers struggle with polarity; cross-encoders perform better than bi-encoders. This motivates explicit negation tests instead of assuming that semantic similarity enforces a negative constraint.

**Cormack, Clarke and Büttcher (2009), [Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).** The paper combines ranked lists through reciprocal-rank contributions and reports gains over individual systems in its experiments. We test fixed RRF with k=60 as an extension, without fitting weights to our judgments.

## 4. Approach and architectural reasoning
<div class="architecture"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 270" role="img" aria-label="Shared corpus to BM25 and E5, saved runs, evaluation, demo and reports"><defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#506c80"/></marker></defs><g font-family="Arial,sans-serif" font-size="14" fill="#16354b"><line x1="178" y1="135" x2="232" y2="135" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><line x1="412" y1="135" x2="458" y2="62" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><line x1="412" y1="135" x2="458" y2="200" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><line x1="650" y1="62" x2="700" y2="135" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><line x1="650" y1="200" x2="700" y2="135" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><line x1="846" y1="135" x2="880" y2="54" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><line x1="846" y1="135" x2="880" y2="135" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><line x1="846" y1="135" x2="880" y2="216" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/><rect x="4" y="100" width="174" height="70" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="91.0" y="126.5" text-anchor="middle" dominant-baseline="middle">News corpus</text><text x="91.0" y="143.5" text-anchor="middle" dominant-baseline="middle">594,977 records</text><rect x="232" y="100" width="180" height="70" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="322.0" y="126.5" text-anchor="middle" dominant-baseline="middle">Shared title + body</text><text x="322.0" y="143.5" text-anchor="middle" dominant-baseline="middle">594,589 eligible</text><rect x="458" y="26" width="192" height="72" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="554.0" y="53.5" text-anchor="middle" dominant-baseline="middle">BM25 inverted index</text><text x="554.0" y="70.5" text-anchor="middle" dominant-baseline="middle">Full article</text><rect x="458" y="164" width="192" height="72" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="554.0" y="191.5" text-anchor="middle" dominant-baseline="middle">E5 → exact FAISS</text><text x="554.0" y="208.5" text-anchor="middle" dominant-baseline="middle">First 512 tokens</text><rect x="700" y="100" width="146" height="70" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="773.0" y="126.5" text-anchor="middle" dominant-baseline="middle">Saved top 1,000</text><text x="773.0" y="143.5" text-anchor="middle" dominant-baseline="middle">+ fixed RRF</text><rect x="880" y="16" width="116" height="68" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="938.0" y="41.5" text-anchor="middle" dominant-baseline="middle">57 original topics</text><text x="938.0" y="58.5" text-anchor="middle" dominant-baseline="middle">40 custom queries</text><rect x="880" y="101" width="116" height="68" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="938.0" y="126.5" text-anchor="middle" dominant-baseline="middle">Local demo</text><text x="938.0" y="143.5" text-anchor="middle" dominant-baseline="middle">+ full articles</text><rect x="880" y="182" width="116" height="68" rx="7" fill="#eef3f6" stroke="#7491a5"/><text x="938.0" y="207.5" text-anchor="middle" dominant-baseline="middle">Metrics, figures</text><text x="938.0" y="224.5" text-anchor="middle" dominant-baseline="middle">+ report</text></g></svg></div>

| Component | Method and reason for the choice |
| --- | --- |
| BM25 | Lucene inverted index; k1=0.9, b=0.4. A strong term-based baseline makes exact-name and wording effects visible. |
| Dense retrieval | E5-base-v2: query:/passage: prefixes, mean pooling, normalized 768-D vectors; exact FAISS cosine ranking. Tests semantic matching without approximate-index error. |
| Hybrid and inspection | Fixed equal-weight RRF, sum(1/(60+rank)); no tuning. Article lookup and the demo connect ranked IDs to full text and relevance evidence. |

Both engines use title plus body. English lexical analysis lowercases and tokenizes, preserves stopwords and does not stem. BM25 reads full bodies; E5 retains the first **512 tokens**, including its prefix and special tokens. This difference is audited and remains a limitation of the comparison. BM25 treats “NOT” as a term, with no Boolean negation or date filter. The lexical foundations follow Manning et al., *Introduction to Information Retrieval*, Chapters 6 and 11.


<!-- PAGE -->

## 5. Current findings and what they mean
Both engines, fixed RRF and the comparison demo are implemented. Supplied-qrels and custom tasks remain separate; custom MAP below uses pooled positives.

| Evaluation set | BM25 nDCG@5 | E5 nDCG@5 | BM25 MAP | E5 MAP |
| --- | --- | --- | --- | --- |
| Original 57 supplied qrels | 0.3975 | 0.4576 | 0.2329 | 0.2765 |
| Initial custom 20 | 0.4621 | 0.4897 | 0.4006 | 0.4683 |
| Added custom 20 | 0.5645 | 0.3828 | 0.4849 | 0.3460 |
| Combined custom 40 | 0.5133 | 0.4362 | 0.4428 | 0.4072 |

| Category (10 each) | BM25 nDCG@5 | E5 nDCG@5 | BM25 MAP | E5 MAP |
| --- | --- | --- | --- | --- |
| Vocabulary mismatch | 0.4757 | 0.4000 | 0.4007 | 0.3343 |
| Negation | 0.7270 | 0.6322 | 0.6767 | 0.5469 |
| Word sense | 0.5526 | 0.5198 | 0.4113 | 0.5389 |
| Temporal | 0.2980 | 0.1930 | 0.2823 | 0.2085 |

**The larger suite changes the comparison.** E5 leads the initial 20, while BM25 leads the added 20 and the combined 40. BM25 wins 21 queries at nDCG@5, E5 wins 15, and four tie. The combined vocabulary-mismatch result also reverses the initial pattern. More queries expose topic and wording sensitivity; they do not guarantee the expected neural advantage. RRF remains an original-benchmark extension: nDCG@5 **0.4900**, MAP **0.3332**.

**Failure modes:** exact entities and detailed constraints can help BM25. E5 sometimes retrieves the broad topic while missing a required cause, response or date. In the word-sense category, BM25 has slightly higher nDCG@5 but E5 higher pooled MAP; early ranking and recovery measure different behavior. Neither ranker enforces negation or time as a logical constraint. Temporal exclusions include missing date evidence, not only known out-of-window events.

**Uncertainty:** the combined E5−BM25 nDCG difference is **−0.0771**, with a descriptive 95% family-bootstrap interval **[-0.1729, +0.0150]** (37 topic families; 10,000 draws). Query and broader 35-family analyses also include zero for nDCG and MAP. These intervals do not measure label accuracy or establish a general winner.

**A practical improvement:** on the preserved initial 20, removing empty-body candidates raises E5 nDCG@5 **0.4897 → 0.5492**, P@5 **0.53 → 0.60**, with BM25 unchanged. This bounded, post-hoc top-20 ablation has not been rerun on the added queries.

**Resources and checks:** BM25 index **367.6 MiB**, dense index **1.72 GiB**, model about **418 MiB** on disk. BM25 built in **66.55 s** locally; T4 encoding took **5 h 43 min**. One cold CPU query took **1.4/48.6 s** (BM25/E5), including startup; hardware/stages differ. Peak RAM and controlled warm latency remain unmeasured. Verification: **153 passing tests**, **7,196 native metric comparisons**, and verified saved demo views; no new GPU encoding was required.


<!-- PAGE -->

## 6. Key innovations and stretch objectives
The project adds a constraint-focused evaluation and transparent inspection tools to established rankers. Three additions make it useful: a query suite with explicit linguistic constraints; evidence-linked judgments that explain why an article qualifies; and an input-visibility audit showing what text E5 retained. A symmetric quality experiment measures how article quality affects the rankings.

**Completed stretch objectives:** fixed RRF on the original 57 topics; exact-content deduplication and empty-body filtering within judged candidates; gain/confidence sensitivity; and a full-article demo with an E5 input toggle. **Further work:** complete the planned human-review stage, then test controlled polarity pairs, equal-input or passage-based retrieval, and a cross-encoder reranker. These extensions need fresh validation; no results for them are claimed.

**Expanded evaluation completed:** 40 queries, ten per category; all 1,444 designated pairs assessed. Initial, added and combined results are retained separately, with topic-family uncertainty and full-text evidence.

## 7. Key milestones and tentative timeline
Completed dates below follow saved artifact timestamps in India time. Remaining durations are planning estimates, not a new submission deadline.

| Milestone | Timing and status |
| --- | --- |
| Shared corpus and BM25 index | 19 Oct 2026 · completed. |
| Full E5 index and original 57-topic evaluation | 24 Oct 2026 · completed. |
| Hybrid, 40-query study, demo and report | 25 Oct 2026 · completed. |
| Begin human review and member checks | Next session: 2–3 hours for an initial sample; tentative. |
| Public repository and demo rehearsal | Repository published; allow about 1 hour for rehearsal. |
| Final link, page-count and submission checks | Allow 30 minutes before the course deadline; one member submits. |

## 8. Contribution matrix and delivery
| Member | Assigned ownership | Completed team component |
| --- | --- | --- |
| Parth Raghuvanshi | data/BM25 | Corpus audit, preprocessing, BM25 index and GPU handoff. |
| Sushruth Reddy Challa | E5/FAISS | E5 encoder, GPU workflow, vector index and dense search. |
| Hamsini G | evaluation | Qrel audit, metrics, candidate pooling and evidence checks. |
| Kritika Pandey | demo/report | Comparison demo, figures, failure analysis and report package. |

Rows assign responsibility for completed team components; individual work is confirmed separately.

**Working demo:** run `.venv/bin/python -m news_ir.demo` and open `http://127.0.0.1:8765`. Saved views show scores and evidence; new live queries are explicitly unjudged. No additional GPU job is needed. [GitHub repository](https://github.com/parthRag/news-retrieval-study)

**Submission file:** `5_NewsIR_BM25_Dense.pdf`. Only one group member submits this single four-page PDF.

