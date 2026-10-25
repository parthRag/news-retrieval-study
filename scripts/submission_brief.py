"""Four-page course report: proposal requirements plus verified implementation results."""


def build_brief(meta, original, custom, categories, quality, paired, table, architecture):
    def f(value):
        return f"{value:.4f}"

    members = "<br>".join(f"{m['name']} — {m['student_id']}" for m in meta['member_details'])
    identity = (f"**Group {meta['group_number']} · {meta['course']}**  \n"
                f"**Faculty mentor:** {meta['faculty_mentor']}  \n{members}")
    results = table(
        ['Evaluation set / measure', 'BM25', 'E5 dense', 'RRF hybrid'],
        [[f"Original 57: {label}"] + [f(original[e]['aggregate'][metric]) for e in ['bm25', 'dense', 'rrf']]
         for metric, label in [('ndcg_at_5', 'nDCG@5'), ('ap_at_1000', 'MAP@1000')]]
        + [[f"Custom 20: {label}"] + [f(custom[e]['aggregate'][metric]) for e in ['bm25', 'dense']] + ['Not evaluated']
           for metric, label in [('ndcg_at_5', 'nDCG@5'), ('ap_at_1000', 'pooled MAP@1000')]])
    category_results = table(
        ['Custom category (5 queries)', 'BM25 nDCG@5', 'E5 nDCG@5'],
        [[name, f(categories[key]['bm25']['ndcg_at_5']), f(categories[key]['dense']['ndcg_at_5'])]
         for key, name in [('vocabulary_mismatch', 'Vocabulary mismatch'), ('negation', 'Negation'),
                           ('homonym', 'Word sense / homonyms'), ('temporal', 'Temporal constraints')]])
    pipeline = table(['Component', 'Method and reason for the choice'], [
        ['BM25', 'Lucene inverted index; k1=0.9, b=0.4. A strong term-based baseline makes exact-name and wording effects visible.'],
        ['Dense retrieval', 'E5-base-v2: query:/passage: prefixes, mean pooling, normalized 768-D vectors; exact FAISS cosine ranking. Tests semantic matching without approximate-index error.'],
        ['Hybrid and inspection', 'Fixed equal-weight RRF, sum(1/(60+rank)); no tuning. Article lookup and the demo connect ranked IDs to full text and relevance evidence.']])
    contributions = table(['Member', 'Assigned ownership', 'Completed team component'], [
        ['Parth Raghuvanshi', 'data/BM25', 'Corpus audit, preprocessing, BM25 index and GPU handoff.'],
        ['Sushruth Reddy Challa', 'E5/FAISS', 'E5 encoder, GPU workflow, vector index and dense search.'],
        ['Hamsini G', 'evaluation', 'Qrel audit, metrics, candidate pooling and evidence checks.'],
        ['Kritika Pandey', 'demo/report', 'Comparison demo, figures, failure analysis and report package.']])
    delta = paired['ndcg_at_5']
    low, high = delta['paired_bootstrap_95_percentile_ci']
    clean_e5 = quality['no_empty_body']['dense']['aggregate']['fixed_reference_ndcg_at_5']
    milestones = table(['Milestone', 'Timing and status'], [
        ['Shared corpus and BM25 index', '19 Oct 2026 · completed.'],
        ['Full E5 index and original 57-topic evaluation', '24 Oct 2026 · completed.'],
        ['Hybrid, custom study, demo and report', '25 Oct 2026 · completed.'],
        ['Begin human review and member checks', 'Next session: 2–3 hours for an initial sample; tentative.'],
        ['Public repository and demo rehearsal', 'Repository published; allow about 1 hour for rehearsal.'],
        ['Final link, page-count and submission checks', 'Allow 30 minutes before the course deadline; one member submits.']])
    repo = (f"[GitHub repository]({meta['repository_url']})" if meta.get('repository_status') == 'created'
            else f"[Planned GitHub repository]({meta['repository_url']}); authenticated creation is pending.")

    return [f'''# News Retrieval under Vocabulary Mismatch
### BM25, neural search and hybrid retrieval
{identity}

## 1. Primary objective
Find out when a news search engine benefits from semantic matching and when exact wording still matters. We compare BM25 with E5 dense retrieval over the same articles, focusing on vocabulary mismatch, negation, ambiguous words and event dates. The aim is a working comparison demo and an evidence-based account of their strengths and failures. E5 is a neural bi-encoder; the findings concern this model and setup, rather than all LLMs.

## 2. Dataset and evaluation criteria
**Selected dataset:** [TREC-News mirror — liuqi6777/trec-news](https://huggingface.co/datasets/liuqi6777/trec-news). The downloaded corpus has **594,977 records**. Excluding 388 records with no title or body leaves **594,589 articles** for both engines. Title-only articles remain in the baseline so the two systems search the same IDs.

We use two separate query sets. The **57 original background-linking topics** have **15,655 supplied relevance judgments**. Our **20 custom queries** have five questions in each linguistic category. Examples ask for reporting that Ebola is **not** airborne, distinguish cricket farming from India cricket match reports, and seek UK events in the first 30 days after the Brexit vote. Each custom query has explicit inclusion and exclusion rules; all texts and rubrics are saved in `annotations/ai_study_v1/queries.jsonl`.

**Success measures:** nDCG@5 measures how well the first five results are ordered by relevance; MAP@1000 measures recovery and ordering of known relevant articles across the saved top 1,000. We also report Precision@5, category means, judged coverage and paired query-bootstrap intervals. AP divides by all known positives for the query. Main nDCG gains equal relevance grades: 0–4 for supplied judgments and 0–2 for the custom study.

**Assessment scope:** all **737 query–article pairs** in the union of both engines’ top 20 have AI relevance assessments, with full-text reading, source hashes and quoted evidence. Grade 0 fails the need, 1 provides limited qualifying detail, and 2 gives a substantive match. These support a preliminary comparison; human review is planned as the next validation stage and has not yet been completed. Unjudged hits keep their ranks and have zero metric contribution; that does not establish irrelevance. Only about 3% of each top-1,000 list is judged, so custom MAP is a **shallow-pool estimate**. All 20 queries remain in the averages, including one with no known positive in its pool.
''', f'''## 3. Related research: approach, findings and relevance
**Thakur et al. (2021), [BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663).** The paper evaluates ten retrieval systems across 18 datasets. BM25 is a robust baseline; reranking and late-interaction methods have strong average quality at greater computational cost. This supports keeping BM25 as a serious comparator and examining different query types.

**Wang et al. (2022; revised 2024), [Text Embeddings by Weakly-Supervised Contrastive Pre-training](https://arxiv.org/abs/2212.03533).** E5 learns text embeddings through contrastive training on text pairs and reports strong transfer on BEIR/MTEB tasks. We use a released E5 checkpoint to test whether this semantic representation helps with news queries whose wording differs from relevant articles.

**Weller, Lawrie and Van Durme (2024), [NevIR: Negation in Neural Information Retrieval](https://aclanthology.org/2024.eacl-long.139/).** The authors compare documents differing in negation. Many retrievers struggle with polarity; cross-encoders perform better than bi-encoders. This motivates explicit negation tests instead of assuming that semantic similarity enforces a negative constraint.

**Cormack, Clarke and Büttcher (2009), [Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).** The paper combines ranked lists through reciprocal-rank contributions and reports gains over individual systems in its experiments. We test fixed RRF with k=60 as an extension, without fitting weights to our judgments.

## 4. Approach and architectural reasoning
<div class="architecture">{architecture()}</div>

{pipeline}

Both engines use title plus body. English lexical analysis lowercases and tokenizes, preserves stopwords and does not stem. BM25 reads full bodies; E5 retains the first **512 tokens**, including its prefix and special tokens. This difference is audited and remains a limitation of the comparison. BM25 treats “NOT” as a term, with no Boolean negation or date filter. The lexical foundations follow Manning et al., *Introduction to Information Retrieval*, Chapters 6 and 11.
''', f'''## 5. Current findings and what they mean
Both engines, the fixed hybrid and the local comparison demo are implemented. The two evaluation sets remain separate because their queries and relevance scales differ.

{results}

{category_results}

**Vocabulary mismatch and word sense:** E5 has higher category means. This suggests that semantic representations help bridge wording differences, but the full query still matters: matching a broad topic can miss a required company, species or event.

**Negation and time:** E5 wins three of the five negation queries at nDCG@5, while BM25 wins two. The category’s pooled MAP favors BM25 (**0.6922 vs 0.5409**), despite E5’s small nDCG lead. A few good early results therefore do not imply reliable recovery of all known qualifying articles. BM25 leads the temporal category; the article must provide evidence of the requested event window.

**A practical failure and improvement:** for India cricket, E5’s leading hits are empty-body records titled “Results.” Removing empty bodies from each engine’s already judged top 20 raises E5 nDCG@5 from **0.4897 to {f(clean_e5)}** and P@5 from **0.53 to 0.60**; BM25 is unchanged. This points to article-quality checks as a useful improvement. It is a post-hoc result within a fixed candidate pool, not evidence of a cleaned full-corpus or held-out gain.

**Uncertainty:** the custom E5–BM25 nDCG@5 difference is **{delta['mean_dense_minus_bm25']:+.4f}**, with a descriptive 95% interval **[{low:+.4f}, {high:+.4f}]** from 10,000 paired query resamples. The pooled MAP interval also includes zero. These small preliminary samples do not establish a general winner; full-body versus prefix coverage is another competing explanation.

**Resources and checks:** BM25 occupies 367.6 MiB and the dense index 1.72 GiB on disk, plus about 418 MiB of model weights. BM25 built in 66.55 s locally; encoding took about 5 h 43 min on a T4. One cold CPU demo query took 1.4 s for BM25 and 48.6 s for E5, including startup; this is not a controlled speed comparison. Disk size is not peak RAM; controlled RAM/warmed-latency measurements remain pending. Verification includes **140 passing tests**, **5,460 native metric cross-checks**, and browser checks of all 77 saved queries plus live retrieval.
''', f'''## 6. Key innovations and stretch objectives
The project adds a constraint-focused evaluation and transparent inspection tools to established rankers. Three additions make it useful: a query suite with explicit linguistic constraints; evidence-linked judgments that explain why an article qualifies; and an input-visibility audit showing what text E5 retained. A symmetric quality experiment measures how article quality affects the rankings.

**Completed stretch objectives:** fixed RRF on the original 57 topics; exact-content deduplication and empty-body filtering within judged candidates; gain/confidence sensitivity; and a full-article demo with an E5 input toggle. **Further work:** complete the planned human-review stage, then test controlled polarity pairs, equal-input or passage-based retrieval, and a cross-encoder reranker. These extensions need fresh validation; no results for them are claimed.

**Query expansion:** a separate 40-query suite now has ten questions per category. Its 20 new queries await relevance assessment; all results above remain for the completed original 20.

## 7. Key milestones and tentative timeline
Completed dates below follow saved artifact timestamps in India time. Remaining durations are planning estimates, not a new submission deadline.

{milestones}

## 8. Contribution matrix and delivery
{contributions}

Rows assign responsibility for completed team components; individual work is confirmed separately.

**Working demo:** run `.venv/bin/python -m news_ir.demo` and open `http://127.0.0.1:8765`. Saved views show scores and evidence; new live queries are explicitly unjudged. No additional GPU job is needed. {repo}

**Submission file:** `5_NewsIR_BM25_Dense.pdf`. Only one group member submits this single four-page PDF.
''']
