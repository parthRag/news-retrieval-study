"""Build editable Markdown and print-ready HTML from frozen experiment artifacts."""
import html
import csv
import json
from pathlib import Path
from markdown_it import MarkdownIt
from news_ir.data import sha256_file
from submission_brief import build_brief
from expanded_reporting import load as load_expanded, update_brief, expanded_pages, write_progress, figures, test_count, readable_prose

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'

def read(path): return json.loads((ROOT/path).read_text())
def table(headers, rows):
    def cell(x): return str(x).replace('|',' / ').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(map(cell,headers))+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(cell,r))+' |' for r in rows])
def f(x): return f'{x:.4f}'
def box(x,y,w,h,text):
    lines=text.split('\n')
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="#eef3f6" stroke="#7491a5"/>'+''.join(f'<text x="{x+w/2}" y="{y+h/2+(i-(len(lines)-1)/2)*17}" text-anchor="middle" dominant-baseline="middle">{html.escape(t)}</text>' for i,t in enumerate(lines))
def architecture():
    s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 270" role="img" aria-label="Shared corpus to BM25 and E5, saved runs, evaluation, demo and reports"><defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#506c80"/></marker></defs><g font-family="Arial,sans-serif" font-size="14" fill="#16354b">'
    for a,b,c,d in [(178,135,232,135),(412,135,458,62),(412,135,458,200),(650,62,700,135),(650,200,700,135),(846,135,880,54),(846,135,880,135),(846,135,880,216)]:
        s+=f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="#506c80" stroke-width="2" marker-end="url(#a)"/>'
    for args in [(4,100,174,70,'News corpus\n594,977 records'),(232,100,180,70,'Shared title + body\n594,589 eligible'),(458,26,192,72,'BM25 inverted index\nFull article'),(458,164,192,72,'E5 → exact FAISS\nFirst 512 tokens'),(700,100,146,70,'Saved top 1,000\n+ fixed RRF'),(880,16,116,68,'57 original topics\n40 custom queries'),(880,101,116,68,'Local demo\n+ full articles'),(880,182,116,68,'Metrics, figures\n+ report')]: s+=box(*args)
    return s+'</g></svg>'

CSS='''@page{size:A4;margin:15mm 16mm 16mm}*{box-sizing:border-box}body{margin:0;color:#172b3e;font:10.3pt/1.38 Georgia,"Times New Roman",serif}h1,h2,h3,h4,th,.meta{font-family:Arial,sans-serif}h1{font-size:23pt;line-height:1.12;margin:0 0 12pt;letter-spacing:-.4pt}h2{font-size:15pt;line-height:1.2;margin:0 0 10pt;padding-bottom:6pt;border-bottom:1pt solid #b5c6d0;color:#164f70}h3{font-size:11.5pt;margin:12pt 0 5pt}p{margin:0 0 8pt}table{border-collapse:collapse;width:100%;font-size:9pt;margin:9pt 0 12pt;break-inside:auto}th,td{text-align:left;vertical-align:top;padding:5pt 6pt;border-bottom:.5pt solid #d4dfe5}th{background:#edf3f6;font-weight:700}tr{break-inside:avoid}thead{display:table-header-group}ul,ol{padding-left:17pt;margin:5pt 0 10pt}li{margin:0 0 5pt}a{color:#185d80;overflow-wrap:anywhere;text-decoration:none}code{font:8.1pt/1.4 Menlo,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;padding:8pt;background:#f1f4f6;overflow-wrap:anywhere}blockquote{margin:8pt 0;padding:4pt 10pt;border-left:2pt solid #acbfc9;color:#425768}img{display:block;max-width:100%;max-height:75mm;object-fit:contain;margin:10pt auto}section.page{break-after:page}section.page:last-child{break-after:auto}.meta{font-size:9pt;color:#4e6574;padding:7pt 0 12pt}.notice{background:#fff3db;border-left:3pt solid #c18b2f;padding:8pt 10pt;margin:9pt 0;font:9.2pt/1.4 Arial,sans-serif}.compact{font-size:10.2pt}.compact table{font-size:9pt}.architecture{width:100%;margin:12pt 0}strong{font-weight:bold}small{font-size:8pt}.caption{font-size:8.5pt;color:#506775} .query-page table{font-size:8.8pt}.query-page td:first-child{width:8%}.query-page td:nth-child(2){width:46%}.query-page td:nth-child(3){width:46%}'''

def publish(stem,pages,*,compact=False):
    md='\n\n<!-- PAGE -->\n\n'.join(pages)+'\n'
    (OUT/(stem+'.md')).write_text(md)
    parser=MarkdownIt('commonmark',{'html':True}).enable('table')
    sections=''.join('<section class="page">'+parser.render(p)+'</section>' for p in pages)
    document='<!doctype html><html lang="en"><head><meta charset="utf-8"><title>'+html.escape(stem)+'</title><style>'+CSS+'</style></head><body class="'+('compact' if compact else 'paper')+'">'+sections+'</body></html>'
    (OUT/(stem+'.html')).write_text(document)


def main():
    OUT.mkdir(exist_ok=True)
    meta=read('configs/submission.json')
    orig=read('artifacts/evaluations/rrf-original-57/metrics.json')['primary']
    custom=read('artifacts/evaluations/custom20-depth20-v1/metrics.json')['linear']
    paired=read('artifacts/evaluations/custom20-depth20-v1/paired_comparison.json')['metrics']
    cats=read('artifacts/evaluations/custom20-depth20-v1/by_category.json')
    ablation=read('artifacts/evaluations/quality-top20-v1/metrics.json')
    sensitivity=read('artifacts/evaluations/custom20-depth20-v1/sensitivity.json')['scenarios']
    queries=list(map(json.loads,(ROOT/'annotations/ai_study_v1/queries.jsonl').read_text().splitlines()))
    labels=list(map(json.loads,(ROOT/'annotations/ai_study_v1/assessments.depth20.jsonl').read_text().splitlines()))
    baseline=read('artifacts/evaluations/custom20-depth20-v1/manifest.json')
    # Refuse writing reports based on altered quantitative output.
    for folder in ['custom20-depth20-v1','rrf-original-57','quality-top20-v1','custom40-extension20-depth20-v2','custom40-depth20-v2']:
        manifest=read(f'artifacts/evaluations/{folder}/manifest.json')
        for name,digest in manifest['files'].items():
            if sha256_file(ROOT/f'artifacts/evaluations/{folder}'/name)!=digest: raise ValueError('Evaluation changed: '+name)
    original_table=table(['Measure','BM25','E5 dense','RRF k=60'],[[label]+[f(orig[e]['aggregate'][m]) for e in ['bm25','dense','rrf']] for m,label in [('ndcg_at_5','nDCG@5'),('ap_at_1000','MAP@1000'),('precision_at_5','P@5'),('recall_at_1000','Recall@1000')]])
    custom_table=table(['Measure','BM25','E5 dense'],[[label]+[f(custom[e]['aggregate'][m]) for e in ['bm25','dense']] for m,label in [('ndcg_at_5','nDCG@5'),('ndcg_at_10','nDCG@10'),('ap_at_1000','Pooled MAP@1000'),('precision_at_5','P@5'),('judged_at_1000','Judged fraction @1000')]])
    category_table=table(['Category (5 each)','BM25 nDCG@5','E5 nDCG@5','BM25 pooled MAP','E5 pooled MAP'],[[name,f(cats[c]['bm25']['ndcg_at_5']),f(cats[c]['dense']['ndcg_at_5']),f(cats[c]['bm25']['ap_at_1000']),f(cats[c]['dense']['ap_at_1000'])] for c,name in [('vocabulary_mismatch','Vocabulary mismatch'),('negation','Negation'),('homonym','Word sense'),('temporal','Temporal')]])
    ablation_table=table(['Rule within original top 20','BM25 nDCG@5','E5 nDCG@5','BM25 P@5','E5 P@5'],[[name]+[f(ablation[v][e]['aggregate'][m]) for m in ['fixed_reference_ndcg_at_5','precision_at_5'] for e in ['bm25','dense']] for v,name in [('baseline','Frozen baseline'),('no_empty_body','Remove empty bodies'),('deduplicate','Exact content deduplication'),('no_empty_body_and_deduplicate','Both rules')]])
    repository_note = 'verified repository' if meta.get('repository_status') == 'created' else 'planned URL; creation awaiting GitHub authentication'
    identity=(f"**Group:** {meta['group_number']} · **Course:** {meta.get('course', '')}  \n"
              f"**Faculty mentor:** {meta.get('faculty_mentor', '')}  \n**Members:** {meta['members']}  \n"
              f"**GitHub repository:** {meta['repository_url']} ({repository_note})")
    references='''1. Manning, Raghavan and Schütze (2008). *Introduction to Information Retrieval*. Cambridge University Press. Chapters 6 and 11. https://nlp.stanford.edu/IR-book/
2. Wang et al. (2022; revised 2024). *Text Embeddings by Weakly-Supervised Contrastive Pre-training*. https://arxiv.org/abs/2212.03533
3. intfloat. *E5-base-v2 model card*. https://huggingface.co/intfloat/e5-base-v2
4. Thakur et al. (2021). *BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models*. https://arxiv.org/abs/2104.08663
5. Cormack, Clarke and Büttcher (2009). *Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods*. SIGIR. https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf
6. Weller, Lawrie and Van Durme (2024). *NevIR: Negation in Neural Information Retrieval*. EACL, pp. 2274–2287. https://aclanthology.org/2024.eacl-long.139/
7. Soboroff (2025). *Don't Use LLMs to Make Relevance Judgments*. Information Retrieval Research 1, 29–46. https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958495
8. NIST. *TREC 2019 News track data*. https://trec.nist.gov/data/news2019.html
9. NIST. *trec_eval source*. https://github.com/usnistgov/trec_eval
10. Dataset mirror used locally: https://huggingface.co/datasets/liuqi6777/trec-news
'''
    brief = build_brief(meta, orig, custom, cats, ablation, paired, table, architecture)
    expanded = load_expanded()
    brief = update_brief(brief, expanded, orig, custom, table)
    publish(meta['group_number']+'_'+meta['short_title'],brief,compact=True)
    paper=[f'''# {meta['project_title']}
{identity}

<div class="meta">Research implementation report · 25 October 2026 · Local reproducible artifacts</div>

## Abstract
We compare lexical BM25 and E5-base-v2 dense retrieval over 594,589 eligible news articles. Evaluation separates a 57-topic supplied-qrels benchmark from a 40-query stress suite covering vocabulary mismatch, negation, word sense and temporal constraints. The expanded custom evaluation uses 1,444 evidence-backed AI assessments of the equal-depth top-20 union for a preliminary comparison, with human review planned as the next validation stage. On the original benchmark, BM25, E5 and fixed reciprocal-rank fusion achieve nDCG@5 of 0.3975, 0.4576 and 0.4900. On the expanded custom suite, BM25 and E5 achieve nDCG@5 of 0.5133 and 0.4362, with pooled MAP@1000 of 0.4428 and 0.4072. Both query and topic-family difference intervals include zero. This reverses the initial20 means; combined category behavior favors BM25 at nDCG@5, while E5 has higher word-sense pooled MAP. The follow-up was designed after initial outcomes were known. A bounded post-hoc empty-body filter raises E5 nDCG@5 to 0.5492. We supply a working local demo, independent native metric checks, explicit evidence provenance and reproducibility scripts. Findings are specific to these engines, queries, input budgets and incomplete relevance sets.

**Keywords:** information retrieval; BM25; dense embeddings; E5; negation; pooled evaluation; news search.

## 1. Introduction and research questions
News queries often describe a concept using vocabulary absent from a headline, but may also impose exact entities, polarity or event dates. A dense representation can bridge wording differences while blurring such constraints. A lexical ranker can reward the right names yet miss paraphrases or promote articles expressing the opposite assertion. Neither behavior should be assumed from the technology label alone.

We ask: **RQ1**, how do BM25 and E5 compare against supplied news judgments? **RQ2**, where do their relative rankings differ across four linguistic categories? **RQ3**, how much do empty records, duplicates, input truncation and assessment policy affect interpretation? **RQ4**, can the implemented system support transparent inspection and live demonstration on limited hardware?

The contribution is an implemented, auditable comparative study and a diagnostic query suite. It is not a new trained retrieval model. The supplied 57 topics provide a separate supporting benchmark; they cannot label the newly written information needs. The stress suite supplies assignment-specific evidence, with the assessment and validation plan in Section 5. The earlier proposal's hybrid and robustness ideas are retained as explicit extensions.
''','''## 2. Related work and retrieval foundations
### 2.1 Lexical ranking
Manning, Raghavan and Schütze [1] introduce term weighting and probabilistic retrieval foundations. BM25 rewards query-term occurrence with saturation and document-length normalization. It is attractive as a strong interpretable baseline, but a bag of analyzed terms does not encode argument structure, temporal arithmetic or truth conditions. Preserving a negation word merely makes it available for lexical matching.

### 2.2 Dense representations
E5 [2] learns text representations with contrastive training. We use the released E5-base-v2 checkpoint rather than training on this project. The model card [3] supplies the query/passage formatting, pooling and normalization procedure implemented here. Dense ranking compares vectors and can associate paraphrases, but representation similarity does not itself enforce all mandatory constraints. E5 is a bi-encoder, not an interactive generative answer system. Claims about its rankings should not be generalized to every LLM.

BEIR [4] motivates evaluation across varied retrieval settings and the continued use of strong lexical baselines. Our two reference sets serve different purposes: supplied background-linking relevance versus deliberately constrained news information needs. Their macro scores are not interchangeable and are never combined into one average.

### 2.3 Negation and fusion
NevIR [6] studies document pairs differing in negation and finds architecture-dependent weaknesses. It motivates testing polarity rather than predicting that every dense model will outperform BM25. Our natural news queries are not a replication of NevIR's controlled minimal-pair benchmark: they have multiple constraints and heterogeneous articles. Consequently, winning one negation query is not direct evidence of compositional negation understanding.

RRF [5] combines ranks without requiring comparable raw score scales. Our extension fixes the usual k=60 and equal engine weights, using no labels to fit fusion. Its empirical advantage is evaluated separately on the original 57 topics.

### 2.4 Assessment validity
Soboroff [7] discusses risks in treating model-generated relevance labels as ground truth. Our preliminary reference enables an initial engine comparison; human review is the next validation stage. Source hashes and literal quotations support inspection and reproducibility. Section5 describes the assessment process and review plan; supplied benchmark judgments remain a separate evidence source.

All system conclusions are therefore conditional: the encoder, preprocessing, query design, available article text and reference labels jointly define the experiment. No causal account of an embedding's internal reasoning is inferred from a ranking alone.
''','''## 3. Corpus and query design
### 3.1 Corpus provenance and eligibility
The downloaded mirror is `liuqi6777/trec-news` [10]. The local corpus contains 594,977 JSONL records with string ID, title and text fields. Shared contents are `(title + newline + text).strip()`. Only 388 records empty in both fields are excluded from retrieval, leaving 594,589 eligible articles. All original IDs remain in the lookup store. The 15,984 title-only articles are retained in the baseline, because silently dropping them from one engine would change the comparison corpus.

The corpus SHA-256 is recorded in every index/run manifest. Source records are streamed into Lucene and a SQLite byte-offset table, avoiding another complete text copy. Both engines are validated against the same eligible IDs, not only an equal document count. Empty bodies and extraction artifacts remain visible, rather than being repaired with external web content. Source distribution rights must be checked before publishing corpus text; the code package excludes the corpus and article packets.

### 3.2 Supplied benchmark
The downloaded 57 queries are headline/background-linking topics. The 15,655 supplied qrel pairs were previously audited against the official NIST 2019 judgments [8]; the supplied 0–4 grades correspond to the official gain-valued form. Sixty topics exist in official metadata, but this local judged subset has 57. None of their canonical source-article IDs occurs in the local corpus, so there is no inferred source-document exclusion.

Sixty-five judgments refer to 57 unavailable article IDs, including three positive query–article pairs. Main evaluation retains them in reference denominators; a separate available-corpus sensitivity reuses unchanged rankings and removes those qrels. This avoids improving main scores merely by hiding unavailable positives.

### 3.3 Twenty linguistic information needs
Five queries each cover vocabulary mismatch (V01–V05), negation (N01–N05), word sense/homonyms (H01–H05) and temporal constraints (T01–T05). Each has inclusion, exclusion and graded-relevance rules. Queries use news-compatible needs, rather than transplanting movie or ancient-history examples into an unsuitable corpus. The exact queries and rubrics are frozen under `annotations/ai_study_v1/`; the original draft status field is preserved for hash compatibility, while the later protocol records the assessment method.

The suite includes workforce reductions, retirement reserves, cricket insects versus international sport, jaguar conservation, Apple’s device-unlocking dispute, and bounded event windows. A missing assertion never proves its negation. Event windows concern dates evidenced in article text, not guessed publication dates. The suite is small and intentionally difficult; it is not a random sample of user traffic. Appendix A supplies all twenty texts and inclusion rules; full exclusion rules remain in the versioned JSONL.
''',f'''## 4. System architecture and implemented retrieval
<div class="architecture">{architecture()}</div>

### 4.1 BM25 implementation
Pyserini 1.5.0/Lucene indexes the full shared article contents with English tokenization and lowercasing, no stemming, no stopword removal and no title boost. Fixed parameters are **k1=0.9, b=0.4**. Conceptually, the score is proportional to a sum of IDF-weighted saturated term frequencies:

`sum_t IDF(t) * tf(t,d) / (tf(t,d) + k1 * (1-b+b*len(d)/avg_len))`.

The implementation and independent score tests use Lucene's actual scoring conventions. Anserini's exported scores are rounded/adjusted for deterministic ordering; evaluation preserves the published rank order. A natural-language `NOT` is an analyzed term, not a hard Boolean operation; no hidden date filter is applied.

### 4.2 Dense implementation
The checkpoint is `intfloat/e5-base-v2`, revision `f52bf8ec8c7124536f0efb74aca902b2995e5bcd`. Inputs use `query: ` and `passage: ` prefixes, a total 512-token budget including prefix/special tokens, masked mean pooling and L2 normalization. Document vectors are 768-dimensional float32. Exact FAISS inner-product search over normalized vectors implements cosine ranking, without approximate-neighbor recall error.

Only the prefix of a long article is represented. BM25 sees full bodies, so shared corpus coverage does not mean equal text coverage. A pinned-tokenizer audit records retained character endpoints and visibility of every saved evidence span. It finds truncation in 568 of the initial 737 assessed pairs (expanded audit: 1,117 of 1,444); these are pair counts, not independent article counts or causal model explanations.

### 4.3 Fusion, manifests and lookup
Each engine exports up to 1,000 hits per query as JSONL and TREC files, alongside query snapshots, parameters and content hashes. RRF scores each unique ID by `sum(1/(60+rank))`, keeps 1,000 results and resolves score ties by ID. Original indexes/runs are never silently overwritten. The demo uses the same search CLI and a read-only article store; saved evaluation replay is labeled separately from new retrieval. On this Mac, JVM, model encoding and FAISS execution are isolated to avoid memory/OpenMP conflicts.
''','''## 5. Assessment protocol and evaluation definitions
### 5.1 Candidate pooling and reading
The current custom comparison uses full-article AI judgments as a preliminary reference. Human review is planned next and has not yet been completed. The review will begin with balanced cases across all40 queries, independent overlap and adjudication, with achieved coverage reported before separate human-reviewed scores are produced. The detailed plan is in `reports/ASSESSMENT_METHOD.md`.

The union of each engine's top 20 contains 737 query–article pairs, including 188 in either top five. All 737 are assessed. Article packets use deterministic randomized order without engine, rank or score; however, earlier results had been seen, so perfect blindness and preregistration are not claimed. Every full available title/body was read, including long texts in explicit consecutive chunks. Only an exact repeated extraction glossary was removed from the reading display; evidence offsets always refer to original source contents.

Grades are **0** for failure of the information need or a mandatory constraint, **1** for limited detail while satisfying the need, and **2** for substantive directly relevant evidence. Each record includes rationale, literal quotations, Unicode start/end offsets, source hash, reading acknowledgment, assessor provenance and confidence. The distribution is 398 grade 0, 110 grade 1 and 229 grade 2; 625 decisions are self-rated high confidence, 112 medium. Confidence is not calibrated accuracy. Thirteen same-query exact-content reuses identify a source decision; no identical same-query contents have conflicting grades. Earlier pilot and top-five judgments are preserved.

### 5.2 Metrics
For cutoff K, `DCG@K = sum(gain_i/log2(i+1))`; `nDCG@K = DCG@K/IDCG@K`. Main gains equal grades: 0–4 for the original benchmark and 0–2 for custom queries. Exponential gains are a sensitivity analysis. IDCG uses all known reference positives, including positives absent from the retrieved ranks.

AP@1000 sums precision at each positively judged hit among the first 1,000 ranks, then divides by **all known relevant documents for the query**. MAP is the equal-weight macro mean. Binary relevance is grade > 0. P@5 divides by five, including when fewer results exist. Unjudged documents keep their ranks with zero contribution; this numerical convention is not a factual irrelevance judgment. Queries without known positives receive zero and stay in averages.

Custom MAP is explicitly **pooled MAP@1000**. Its reference set is the completed designated shallow pool, not exhaustive corpus labels. About 3% of the saved top-1,000 lists are judged. No claim of complete recall follows from complete assessment of top 20. V05's zero-positive pool does not prove there is no relevant corpus article.

### 5.3 Uncertainty and verification
Ten thousand paired query-bootstrap resamples produce descriptive percentile intervals, with recorded seeds. Related queries/shared articles and uncertainty in the preliminary reference limit interpretation. These are not label-accuracy intervals. Native `trec_eval` [9] independently cross-checks seven measures per query and macro mean. Ordinal scores preserve published rank order, including tied original scores, during those checks.
''',f'''## 6. Results on the original 57 topics
{original_table}

E5 has higher means than BM25, but BM25 wins 21 of 57 nDCG@5 comparisons; E5 wins 31 and five tie. The paired E5-minus-BM25 nDCG@5 difference is **+0.0601**, with descriptive 95% interval **[−0.0046, +0.1294]**. Its AP difference is **+0.0436**, interval **[+0.0032, +0.0852]**. These conditional estimates support complementarity rather than universal superiority.

![Original three-engine results](../reports/figures/current-study/original_57_three_engines.png)

RRF has the highest means. Its nDCG@5 difference against BM25 is +0.0926, interval [+0.0434, +0.1419]; against E5 it is +0.0324, interval [−0.0154, +0.0790]. AP differences are +0.1003 versus BM25 and +0.0567 versus E5, with positive descriptive intervals. Fixed fusion was not fitted on these qrels, but examining a third system remains exploratory rather than a new held-out confirmation.

### Judgment coverage and gain sensitivity
At rank five, judged fractions are **96.49% BM25**, **79.30% E5**, and **92.63% RRF**. Lower reference coverage can penalize genuinely useful unjudged results, especially for dense retrieval. It is incorrect to label every zero metric contribution a confirmed failure. Exponential-gain nDCG@5 is 0.3369/0.3959/0.4140; the NIST gain-valued sensitivity is 0.3546/0.4118/0.4369. Available-corpus sensitivity changes E5 to 0.4582, while BM25/RRF nDCG remain 0.3975/0.4900.

### Measured cases
For topic 870, E5's 0.9294 versus BM25's 0.0000 matches a contrast between reports of transgender killings and lexical distraction by political entities. Topic 830 similarly connects miniature frogs with a fingernail-sized description. Conversely, topic 852 favors BM25 (0.5353 versus 0.0457), but three dense top-five hits are unjudged; the observed difference mixes topical focus and coverage. These cases identify plausible explanations, not internal neural reasoning. Full IDs, supplied grades and inspected evidence remain in `reports/ORIGINAL_57_CASE_STUDIES.md`.
''',f'''## 7. Results on the custom linguistic suite
{custom_table}

All 20 queries and all top-20 retrieved slots are judged. The only zero-positive pooled query is V05; V01 and T01 have relevant deeper results. Both systems have P@5=0.53, even though the ordering and grades of useful results differ.

{category_table}

![Category metrics](../reports/figures/custom20-depth20/category_metrics.png)

**Uncertainty.** E5−BM25 nDCG@5 is +0.0275, interval [−0.1264,+0.1650], with 12 E5 wins, five BM25 wins and three ties. Pooled MAP difference is +0.0677, interval [−0.0877,+0.2220], with 12/7/1 wins/losses/ties. Both intervals include zero. Five hand-authored queries per category are insufficient for broad category-level significance claims.

The earlier top-five-only nDCG was 0.5149/0.5286. Deeper relevant judgments increase ideal-ranking denominators, changing nDCG despite identical original top-five grades and rankings. The frozen historical snapshot remains valid for its original scope. It must not be substituted for the current complete-designated-pool results merely because it is larger.

**Sensitivity.** Exponential 0/1/3 gains yield nDCG@5=0.4350/0.4708. Removing medium-confidence positive credit gives 0.4181/0.4645; keeping only grade-2 positives gives 0.3797/0.4332. These specified scenarios preserve the average direction but do not bound label error, establish significance or validate high-confidence judgments.
''','''## 8. Failure analysis: linguistic boundaries and competing explanations
### 8.1 Vocabulary mismatch
The category means favor E5, with nDCG@5=0.3488 versus 0.1830. V04 is a strong individual dense case, while V01 shows that finding workforce-cutting language is insufficient if the required technology sector or explanatory detail is missing. Both V01 top-five lists fail, yet the deeper pool has relevant articles. Better semantic association is helpful but does not enforce every constraint.

### 8.2 Negation
E5 wins three of five negation queries at nDCG@5, BM25 two. Means are close: 0.6192 versus 0.6046. The pooled MAP ordering reverses, with BM25 0.6922 versus E5 0.5409. Thus the answer depends on whether we ask about a few early graded hits or recovery of all known pooled positives. N03 is a strong BM25 case (0.6608 versus 0.1461). Retrieved reports can contain the right topic yet fail the required assertion. Mixed articles can still qualify when they explicitly describe the requested condition. Absence of an airborne-transmission assertion alone is not an explicit rejection of airborne transmission. These are judgments of what the requested reporting states, not current clinical guidance.

This does not prove BM25 understands negation: its bag-of-terms formulation has no truth-condition mechanism. Nor does an E5 win prove polarity understanding. Entity matches, correlated wording, input coverage, article quality and the query's other constraints remain competing explanations. A controlled polarity-flip study needs changed-query judgments and is future work.

### 8.3 Word sense and extraction quality
H02 asks about India international cricket results and player performance. Dense top-five results are empty-body records titled `Results`, all grade 0. BM25 also makes errors: its lead previews India–Pakistan rather than reporting a match result. Deeper candidates include wrong teams, domestic cricket and previews. H04 retrieves conservation articles about other species; H03 instead concerns Apple’s iPhone-unlocking dispute with the FBI. Correct broad context is insufficient for the precise entity/sense need.

### 8.4 Temporal constraints
BM25 leads temporal category means (0.4267 versus 0.2836 nDCG@5). T03 and T04 are prominent dense failures. Judgments distinguish actual state rulings from stayed decisions and the excluded national event. T01's deeper retrospectives can satisfy an earlier window even if the article itself is later. Undated relevant-looking text does not establish the requested bounded event date. One T01 retrospective contains a questionable relative date and has medium confidence; this is a source-quality limitation.

### 8.5 Evidence visibility
The audit records whether quoted support lies within E5's retained prefix. It can identify unavailable evidence, but visibility does not establish use by the model. BM25's full-body coverage and E5's prefix coverage confound architecture with input budget. Neither causal attribution to truncation nor a general model-family claim is warranted without a controlled equal-input or passage-indexing experiment.
''',f'''## 9. Post-hoc content-quality ablation
### 9.1 Protocol
After observing empty records and duplicate articles, we applied the same four deterministic policies to each engine's original top 20: retain all; remove whitespace-empty bodies; suppress exact title-plus-body duplicates after the first occurrence; apply both. Rankings preserve remaining original order, use no score/label threshold and never refill beyond rank 20. All candidates are already judged, so no unjudged replacement is silently treated as an observed negative. The baseline files and relevance labels remain unchanged.

Main nDCG uses the original document-level reference IDCG; P@5 always divides by five. MAP is not reported for these bounded candidate lists. Because repeated positively judged document IDs can receive repeated ordinary nDCG credit, we additionally report a separate **unique-content nDCG@5**: only the first occurrence of a content hash earns gain, duplicate positions remain, and IDCG uses all unique pooled contents. Same-query content grades are consistent. This additional measure is not standard document-level nDCG and cannot be compared numerically as if it used the same reference.

{ablation_table}

### 9.2 Interpretation
Empty-body removal improves E5 nDCG@5 by **+0.0595** and P@5 by **+0.07**, with BM25 unchanged. H02 rises from 0 to 0.4788 within the retained horizon. N03 improves from 0.1461 to 0.3601 but remains below BM25's baseline. This demonstrates sensitivity to available-record quality; it does not establish that empty records fully explain polarity failures.

Unique-content nDCG rises with exact deduplication: BM25 **0.4581 → 0.4736**, E5 **0.4821 → 0.5153**. Both rules yield **0.4736 / 0.5534**. Ordinary E5 nDCG with both rules (0.5434) is slightly lower than empty-body removal alone (0.5492), while the unique-content measure improves. The difference reflects what each reference rewards and illustrates why diversity cannot be inferred from document-ID metrics alone.

These rules were motivated by observed failures, not preregistered or validated on a fresh test set. No optimal threshold was searched, but post-hoc selection still limits generalization. The experiment measures filtering within a depth-20 horizon, not reindexing/searching a cleaned full corpus. Future work should test the frozen rule on new queries, include longer refilling pools with proper labels, and compare passage representations while controlling input coverage.

Outputs include every candidate/retained ID, per-query CSV, aggregate metrics and source-bound hashes in `artifacts/evaluations/quality-top20-v1/`.
''','''## 10. Engineering, efficiency and reproducibility
### 10.1 Resource measurements
| Component | Measured requirement or time | Interpretation |
| --- | --- | --- |
| BM25 index folder | 385,483,844 bytes (367.6 MiB) | Includes local lookup metadata; disk, not RAM |
| Dense index folder | 1,848,335,569 bytes (1.72 GiB) | Excludes separate model weights |
| E5 weights | About 418 MiB | Additional disk requirement |
| BM25 index build | 66.55 seconds, local Mac | Different stage/hardware from encoding |
| Full dense job | 20,574.8 seconds, Kaggle T4 | About 5 h 43 min, including job work |
| RRF computation | About 0.69 ms/query | Saved rank fusion only, excluding searches/startup |
| Live CPU smoke query | BM25 1.39 s; E5 48.59 s | Includes separate process/model startup; single-run observation |

The local machine has 8 GiB RAM. GPU document encoding used one T4 and checkpointed float32 shards, which were validated for complete unique IDs, finite normalized vectors and source/model identity. It is completed work; the demo needs no GPU. Peak resident RAM and representative warmed query-latency distributions have not been measured under a controlled protocol. Disk sizes are not substitutes for RAM measurements, and disparate build stages are not a speedup comparison.

### 10.2 Working demo
A standard-library local HTTP server serves packaged HTML/CSS/JavaScript. Startup verifies query/run/evaluation hashes and corpus identity. Saved custom views show two engines, relevance rules, per-query metrics, full articles, rationale and highlighted evidence. The input toggle displays the exact E5-retained passage text. Original views additionally show RRF and supplied grades.

Live searches run BM25 then E5 in separate processes, combine complete top-1,000 lists by RRF, and return explicitly unjudged results without fabricated metrics. FAISS remains isolated. One job at a time, bounded in-memory history, literal query arguments and subprocess timeouts support operation on the limited machine. Saved comparisons remain available during live retrieval and are never overwritten.

### 10.3 Checks and artifact integrity
The initial release had 140 passing tests (the expanded suite is reported in Section13), covering real Lucene behavior, independent scoring, Unicode offsets, malformed inputs, atomic publication, source identity, retrieval exports, metric definitions, assessment preservation, exact-content handling, HTTP routes, live-job recovery and quality-metric behavior. Initial-release native checks total **5,460**: 3,248 original baseline comparisons, 1,624 RRF comparisons and 588 custom comparisons. Native four-decimal output uses tolerance 0.000051. The custom artifact validator recomputes saved scores and checks all 737 source/evidence records. Real-browser verification covers all 77 saved queries, article views, 390-pixel layout and actual BM25/E5/RRF retrieval, with no observed JavaScript exceptions.
''','''## 11. Limitations, conclusions and remaining review
### 11.1 Validity limits
**Assessment.** The current reference supports preliminary comparison. Full-text evidence and self-rated confidence help inspection, but do not establish decision accuracy; earlier outcomes were also visible during study development. The planned human-review stage will check relevant cases, hard negatives, temporal bounds and borderline grades. Review coverage and agreement will be reported only after that work is completed.

**Pooling.** Completing the designated pool does not label the whole corpus. Only about 3% of each top-1,000 list is judged. Custom AP/recall depend on pooled known positives; V05's zero cannot establish answer absence. RRF is evaluated on original supplied qrels only. A custom RRF run could promote articles outside the judged top-20 union, so a comparable custom evaluation would require attention to additional coverage.

**Comparability.** Both engines share article IDs, but BM25 sees full bodies and E5 only a prefix. The exact search removes approximate-index error but not encoder truncation. Extraction glitches, title-only records and exact duplicates interact with representation. The bounded post-hoc quality experiment demonstrates sensitivity without fully separating these causes.

**Generalization.** The initial twenty authored queries, five per category, were too few for broad claims about linguistic competence. Query dependence and model-specific behavior limit bootstrap interpretation. No held-out tuning set, new dataset or controlled polarity-pair benchmark was added. Original supplied judgments also have unequal coverage and a small number of unavailable positives.

A separate extension now defines **40 queries, ten per category**, preserving the original 20 exactly and adding 20 new information needs. Assessment and evaluation are now complete; Sections12–13 report the added and combined samples. Sections7–9 preserve the initial20 results and ablations. The extension was designed after viewing those results and is not an independent held-out study. Shared-topic families are recorded for grouped uncertainty analysis. Its frozen rubrics and protocol are in `annotations/custom40_v2/`; see `reports/CUSTOM_40_EXTENSION.md`.

**Efficiency.** One GPU encoding job and a few cold local searches do not supply a controlled systems benchmark. End-to-end latency includes startup and memory pressure; peak RAM is unmeasured. The demo is a local research prototype, not a deployed concurrent service.

### 11.2 Initial-study interpretation
The initial 20-query comparison shows complementary strengths under transparent evaluation. E5 improves original-benchmark averages and performs well on vocabulary mismatch and word sense; BM25 retains substantial per-query wins and stronger temporal category means. Negation has no simple technology-level winner: near-top graded retrieval and pooled recovery can favor different engines. Fixed RRF improves original averages, while uncertainty and judgment coverage qualify the claim. Article-quality filtering materially changes dense outcomes, supporting explicit data-quality diagnosis alongside model analysis.

The deliverable combines a functioning dual-engine system, a 40-query challenge suite, complete designated-pool judgments, nDCG/MAP evaluation, evidence-linked failures, uncertainty, a measured stretch experiment and a local demo. The preliminary comparison is complete, with the human-review stage planned as described above.

### 11.3 Submission and authorship
Group 5 member and mentor details appear on the first page. The brief records responsibility for completed team components; actual personal work is confirmed separately. The verified public repository, linked on page 1, publishes source, notebooks, preprocessing scripts and reports. Assessment provenance and the next validation stage are described in Section 5. Submit the four-page brief; this longer report is supporting research material.
''',f'''## References and reproduction index
{references}

### Reproduction commands
Use Python 3.12 and Java 21. In the existing environment, from the repository root:

```sh
.venv/bin/python -m news_ir.demo
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_custom_depth20.py
.venv/bin/python scripts/evaluate_quality_ablation.py --output artifacts/evaluations/quality-recheck
.venv/bin/python scripts/build_final_documents.py
```

The locked environment and `README.md` document setup, source/index construction, Kaggle encoding, independent evaluation and saved-run reproduction. `reports/DEMO_GUIDE.md` provides the presentation sequence. `DELIVERABLES.md` maps submission artifacts and local data dependencies.

**Provenance anchors.** Corpus SHA-256: `{baseline['corpus_sha256']}`. Custom queries: `{baseline['query_source_sha256']}`. Custom assessments: `{baseline['assessments_sha256']}`. Full revision/configuration hashes remain in manifests; frozen inputs are not modified to regenerate the report.

**Evidence location.** The 737-decision appendix is `reports/CUSTOM_20_DEPTH20_EVIDENCE.md`; full article packets remain local under `artifacts/assessments/`. The longer appendix is not reproduced in the four-page brief. Selected article excerpts remain evidence for the judgments, rather than a substitute for full-document review.
''']
    paper.extend(expanded_pages(expanded, orig, custom, table))
    for half in [queries[:10],queries[10:]]:
        p='## Appendix A. Frozen custom queries'+(' (V01–N05)' if half[0]['_id']=='V01' else ' (H01–T05)')+'\n\n'
        p+='Each information need has the shared 0/1/2 rubric: fails a mandatory constraint; limited qualifying detail; substantive qualifying evidence. Exact exclusion rules and status/protocol fields are in the frozen JSONL. Temporal grading requires article-evidenced event bounds.\n\n'
        p+=table(['ID','Query text','Inclusion rule'],[[q['_id'],q['text'],q['relevant_if']] for q in half])
        p+='\n\n**Scope:** All pairs in the BM25/E5 top-20 union are assessed, with full-available-text evidence. Query labels are not transferred from the original 57 topics. Hard constraints remain part of the relevance decision; topically related contradictory or undated articles do not automatically qualify.'
        paper.append(p)
    evidence_cases=[('V04','2f33cb3e-46a6-11e1-865e-8d7745453554','E5 rank 1'),
                    ('N03','6e21bdec-561b-11e4-809b-8cc0a295c773','BM25 rank 2'),
                    ('N03','48ba826e85ce81d1399fc6636b1e8c23','E5 rank 1'),
                    ('H02','0731a894-b080-11e4-bf39-5560f3918d4b','BM25 rank 1'),
                    ('H02','614571525868fac3ac742d8699e9c7b6','E5 rank 1'),
                    ('T03','ee0edaf8-9513-11e4-aabd-d0b93ff613d5','BM25 rank 1'),
                    ('T03','cd2d15a93cdce9a5bdec350e450afcfe','E5 rank 1')]
    evidence_rows=[]
    lookup={(r['query_id'],r['doc_id']):r for r in labels}
    for qid,doc_id,rank in evidence_cases:
        r=lookup[qid,doc_id]
        explanation=r['rationale'].split('. ')[0].rstrip('.')+'.'
        evidence_rows.append([f"{qid} · {rank} · grade {r['grade']}",
                              f"`{doc_id}` — “{r['evidence'][0]['quote']}” — {explanation}"])
    paper.append('## Appendix B. Traceable failure-analysis evidence\n\n'
                 'These selected saved assessments connect the discussion to exact article IDs and literal source text. '
                 'The grades evaluate the frozen query need, not the scientific or legal truth of every article assertion. '
                 'Full rationales, all evidence offsets and source hashes remain in the 737-decision appendix.\n\n'
                 +table(['Query / saved rank / grade','Document ID, quotation and assessment rationale'],evidence_rows)
                 +'\n\nV04 demonstrates a qualifying dense hit, not a failed lexical lead: BM25 rank 1 is also grade 2, while its lower early ranks explain the query-level difference. '
                 'For N03, the BM25 positive above has support far beyond the E5 prefix; lexical specificity and coverage remain competing explanations. '
                 'For T03, a qualifying date must be established from the full narrative; the brief quotation alone is not sufficient temporal proof.')
    for half in [expanded['queries'][20:30], expanded['queries'][30:]]:
        paper.append('## Appendix C. Frozen follow-up queries (' + half[0]['_id'] + '–' + half[-1]['_id'] + ')\n\n' + 'Each new query uses the same strict0/1/2 rubric. Wording and bounds were frozen before retrieval; frozen pending-status fields are historical, with completion recorded separately.\n\n' + table(['ID','Query text','Inclusion rule'], [[q['_id'],q['text'],q['relevant_if']] for q in half]))
    replacements = {'initial20': 'initial 20', 'original20': 'original 20', 'all40 frozen': 'all 40 frozen', 'Section13': 'Section 13', 'Sections12': 'Sections 12', 'Sections7': 'Sections 7', 'March11': 'March 11', 'top20': 'top 20', 'at1000': 'at 1000', 'grade2': 'grade 2', 'grade0': 'grade 0', 'rank1': 'rank 1', 'vs0.3156': 'vs 0.3156', 'strict0/1/2': 'strict 0/1/2'}
    for i, page in enumerate(paper):
        for a, b in replacements.items():
            page = page.replace(a, b) if a not in {'initial20', 'original20', 'top20'} else page
        paper[i] = readable_prose(page)
    publish('RESEARCH_REPORT',paper)
    write_progress(expanded, orig, custom, table)
    figures(expanded)
    (OUT/'architecture.svg').write_text(architecture())
    (OUT/'references.md').write_text(references)
    with (OUT/'contribution_matrix.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(['member', 'assigned_ownership', 'completed_team_outputs', 'confirmed_individual_work', 'individual_completion_confirmed'])
        writer.writerows([r['member'], r['ownership'], r.get('completed_team_outputs', ''), r['completed'],
                          r.get('completion_confirmed', False)] for r in meta['contributions'])
    snapshot={"source": "Frozen JSON evaluations, including completed expanded40 assessment", "metadata":meta,
              "original57":{e:v['aggregate'] for e,v in orig.items()},
              "custom20":{e:v['aggregate'] for e,v in custom.items()},
              "custom40":{e:v['aggregate'] for e,v in expanded["metrics"].items()},
              "extension20":{e:v['aggregate'] for e,v in expanded["extension"].items()},
              "custom40_clustered":expanded["clustered"],
              "quality_ablation":{v:{e:r['aggregate'] for e,r in es.items()} for v,es in ablation.items()},
              "custom_paired_uncertainty":paired,"categories":cats,
              "source_manifests":{d:sha256_file(ROOT/f'artifacts/evaluations/{d}/manifest.json') for d in ['rrf-original-57','custom20-depth20-v1','quality-top20-v1','custom40-extension20-depth20-v2','custom40-depth20-v2']}}
    (OUT/'results_snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    print(json.dumps({'brief_source_pages':len(brief),'research_source_pages':len(paper),'output':str(OUT)},indent=2))

if __name__=='__main__': main()
