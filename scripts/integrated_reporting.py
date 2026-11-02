"""Report separately scoped news and imported scientific robustness experiments."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def load():
 base=ROOT/'artifacts/evaluations'
 if not (base/'integrated-core18-v1/manifest.json').exists():return None
 return {name:json.loads((base/f'integrated-{name}-v1/metrics.json').read_text()) for name in ['core18','covid']}


def comparison_table(data,table,metric='ndcg_at_5'):
 rows=[]
 for dataset,variant,label in [('core18','title','News · original titles'),('core18','rewrite','News · provisional rewrites'),
  ('core18','description','News · official descriptions'),('covid','original','COVID · original keywords'),
  ('covid','rewrite_a','COVID · rewrite A'),('covid','rewrite_b','COVID · rewrite B')]:
  rows.append([label]+[f'{data[dataset]["variants"][variant][e]["aggregate"][metric]:.4f}' for e in ['bm25','dense','rrf']])
 return table(['Separate experiment','BM25','E5','RRF'],rows)


def update_brief(pages,data,table):
 pages=list(pages)
 pages[0]=pages[0].replace('We evaluate two distinct tasks.','We retain the background-linking and custom diagnostics, and add a paired ad-hoc news experiment.')
 marker='**Success measures:**'
 insert='''**Integrated robustness study:** 50 [NIST Core 2018](https://trec.nist.gov/data/core2018.html) topics are now evaluated on the available news corpus, using original titles, official descriptions and one provisional rewrite per topic (150 formulations). The 26,233 source qrel pairs match NIST. Seven judged articles are absent and eleven are empty; one unavailable pair is positive. All original qrels remain in primary denominators. This is an available-corpus adaptation, not an official WaPo v2 reproduction. [Hamsini’s 50-topic TREC-COVID study](https://github.com/HamsiniGururaj/robust-news-retrieval) is preserved as a separate cross-domain experiment.

'''
 # Save room by shortening historical suite detail; current counts stay explicit.
 start=pages[0].index('Our **40 custom queries**');end=pages[0].index('\n\n**Success measures:**',start)
 pages[0]=pages[0][:start]+'Our **40 custom queries** have ten questions per category: vocabulary mismatch, negation, homonyms and temporal constraints. All 1,444 top-20 pooled pairs are assessed; the initial 737 decisions remain unchanged.\n\n'+insert+pages[0][end:]
 pages[0]=pages[0].replace('0–4 for supplied judgments and 0–2 for the custom study.', '0–4 for the 57-topic reference and 0–2 for Core 2018, COVID and custom queries.')
 start=pages[0].index('**Assessment scope and next validation:**')
 pages[0]=pages[0][:start]+'''**Reference status:** custom results use evidence-backed full-article **AI judgments** under a 0–2 rubric. **Human review is planned next and has not yet been completed.** New news rewrites are AI-authored, frozen before retrieval, and await independent human intent review; their scores reuse human NIST labels conditionally on preserving the narrative. Official descriptions change length/detail, so they are a query-form diagnostic. COVID rewrites retain their source study’s single-annotator verification. Custom MAP is shallow-pool; none of these labels establish that unjudged articles are irrelevant.
'''
 core=data['core18']['variants'];covid=data['covid']['variants']
 pages[2]='''## 5. Current findings and what they mean
All systems are implemented. Each row below is a separate 50-topic experiment; scores are not averaged across domains or formulations. The table reports **nDCG@5**, with graded gains equal to the reference labels.

'''+comparison_table(data,table)+'''

**Paired news finding:** E5’s rewrite-minus-title change exceeds BM25’s by **+0.1820 nDCG@5**, with a 95% paired interval **[+0.0784, +0.2905]** and Holm-adjusted p=**0.0168**. The direction also holds for MAP and bpref, but the condensed-nDCG@10 interval includes zero. RRF stays near its original news score, while it drops substantially in the COVID rewrites. These are separate, conditional patterns—not proof that domain alone causes the difference.

**Reference sensitivity:** judgment coverage changes when wording changes. Condensed nDCG removes unjudged hits; bpref supplies another incomplete-reference view. Neither supplies missing judgments. The news rewrite conclusions remain provisional until independent intent review; title-versus-description differences also include query length and specificity.

**Preserved diagnostics:** on the original 57 background-linking topics, BM25/E5/RRF nDCG@5 remains **0.3975/0.4576/0.4900**. On custom40, BM25/E5 is **0.5133/0.4362** and pooled MAP is **0.4428/0.4072**; family intervals include zero. Initial20 nDCG@5 was **0.4621/0.4897**. A separate post-hoc empty-body filter raises E5 to **0.5492** within the initial judged pool; it is not a cleaned-corpus replication.

**Resources:** the news BM25/dense indexes occupy 367.6 MiB/1.72 GiB; E5 weights add about 418 MiB. Existing T4 corpus encoding took about 5 h 43 min and is reused. New query batching records amortized throughput, not single-query latency. Full-body BM25 versus E5’s first 512 tokens remains an input-coverage confound. Historical evaluation files and source-study results are preserved; current checks and exact values are in the reproducibility package.
'''
 pages[3]=pages[3].replace('Qrel audit, metrics, candidate pooling and evidence checks.','COVID rewrite experiments, query tooling and paired statistics.')
 pages[3]=pages[3].replace('Rows assign responsibility for completed team components; individual work is confirmed separately.','Rows distinguish assigned responsibility from verified personal work; Hamsini’s source study is credited.')
 first=pages[3].index('The project adds')
 end=pages[3].index('\n\n**Completed stretch objectives:**',first)
 pages[3]=pages[3][:first]+'The project combines controlled query rewording with constraint diagnostics, source-linked relevance evidence and an audit of E5’s retained input. Separate news and COVID experiments test whether the same robustness pattern holds in different settings.'+pages[3][end:]
 start=pages[3].index('**Further work:**');end=pages[3].index('\n\n**Expanded evaluation completed:**',start)
 pages[3]=pages[3][:start]+'**Further work:** independently review news rewrite intent and custom labels, then test controlled polarity pairs, equal-input retrieval and a cross-encoder. These extensions have no claimed results.'+pages[3][end:]
 pages[3]=pages[3].replace('25 Oct 2026 · completed.','25 Oct 2026 · completed; integrated news/COVID experiments added 2 Nov.')
 return pages


def paper_pages(data,table):
 return ['''## 14. Integrated controlled robustness experiments
The combined project retains the existing news engines and incorporates Hamsini G’s independently implemented controlled-rewrite study. A byte-preserved snapshot of her code, query sheet, tests, saved runs and results is stored under `studies/hamsini_robustness/`, with source commit and per-file hashes. Her pipeline/experiment work is credited directly; integration is a subsequent change.

### 14.1 News-domain task and corpus audit
Core 2018 supplies 50 ad-hoc news topics, each with a title, description and narrative. All 26,233 exported query–document grades match the official NIST file. The available corpus contains documents for 26,226 of those pairs. Eleven additional pairs refer to empty excluded records; just one of the total 18 unavailable pairs is positive. Primary scores retain every original judgment; an available-corpus sensitivity removes unavailable pairs without changing rankings.

The mirror has 594,977 source records and is not established as text-equivalent to the full official WaPo v2 collection. These results are explicitly a Core 2018 evaluation on the available news corpus, not an official full-corpus reproduction. Existing news vectors are reused; no model is retrained or tuned on the topics.

### 14.2 Frozen query formulations and validity
All 50 topics receive three formulations: official title, official description and one new provisional AI-authored rewrite. The exact 150 texts, narratives, length/overlap features and protocol were frozen before Core 2018 retrieval. Independent human rewrite-intent review has not been completed. Reusing NIST labels for a rewrite is conditional on retaining its narrative’s relevance criteria. Official description comparisons change length/detail and are reported as a query-form diagnostic, not pure paraphrase robustness.

### 14.3 Separate nDCG@5 results
'''+comparison_table(data,table)+'''

The news difference in changes, E5 minus BM25, is +0.1820 nDCG@5 (paired 95% interval [+0.0784, +0.2905], Holm p=0.0168). MAP and bpref point the same way; condensed-nDCG@10 uncertainty includes zero. News RRF is nearly stable (0.4453 → 0.4447), unlike its larger COVID declines. Dataset, rewrite and coverage differences prevent attributing this contrast to domain alone.

COVID rows are an integrated rank-preserving re-evaluation of Hamsini’s saved runs, not newly generated retrieval runs. Original score-based CSVs reproduce and remain unchanged. Near-tie score serialization can produce small differences when an evaluator sorts scores; the integrated evaluation uses derived ordinal scores to retain published rank order. Exact @10, MAP, coverage, bpref and sensitivities are saved alongside @5.
''','''## 15. Paired interpretation, integration and next validation
### 15.1 Estimand and uncertainty
For each engine and topic, change is score(rewrite) minus score(original). Dense robustness advantage is change(E5) minus change(BM25). A positive value means E5 lost less or gained more; it does not necessarily mean E5 has the higher absolute score. Paired tests use one observation per topic, 10,000 bootstrap/sign-flip draws and Holm adjustment within each declared metric family. Domains and formulation variants are never pooled into an overall performance average.

Hamsini’s original feature analysis treated both rewrites as 100 observations from 50 topics. The integration adds a clearly different topic-mean association analysis: both feature and advantage are averaged within topic before permutation. This changes the estimand and is not presented as a retroactive rewrite of her original results. Each original phenomenon group already contains distinct topics, so this dependence concern is not used to dismiss every group-specific comparison.

### 15.2 Incomplete judgments and rewrite validity
Standard nDCG/MAP retain unjudged positions with zero contribution. Condensed nDCG and bpref provide sensitivity views but cannot recover unknown labels. The COVID query study has substantially lower judged coverage on rewrites. An omission sensitivity excludes topics 5 and 12, flagged during the pre-integration review for possible intent narrowing; original texts and primary results remain unchanged. This sensitivity does not certify the remaining rewrites.

The news study now has a direct short-query ad-hoc benchmark in addition to the earlier headline/background-linking adaptation. The 40 custom needs remain a separate constraint diagnostic with preliminary full-article relevance labels. Neither the source study’s self-verification nor machine evidence checks are represented as independent human assessment.

### 15.3 Engineering and demo integration
The active engine preserves strict corpus/model identity and resume checks. Small batches encode new query vectors and submit them to exact FAISS search; runtime manifests record batch size and amortized throughput. This leaves the frozen document vectors and earlier experiments intact. Fake-encoder tests compare batched and sequential rankings, including empty queries and cutoff ties.

The local demo exposes all three Core 2018 formulations. A rewritten/description query shows its original title and each engine’s nDCG@5 change, alongside article text and supplied grades. Scientific runs remain a separate saved study because their document text is not part of the local news corpus. No COVID ID is resolved through the news article store.

### 15.4 Remaining work and reproducibility
Prioritize an independent human check of news rewrite intent and the planned custom relevance review, then publish separately versioned reviewed results. Equal-input/passage retrieval and contrastive polarity tests remain extensions. Confirm remaining personal contributions with the members concerned.

Run `scripts/evaluate_integrated_study.py --study covid --output <new-directory>` to reproduce the imported study, and use `--study core18 --native` for the new news runs. Existing outputs are refused. `reports/INTEGRATED_STUDY.md` records the current computed results and effect sizes; `studies/README.md` identifies the original contribution and source.
''']
