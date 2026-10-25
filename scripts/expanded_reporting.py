"""Report the frozen original, follow-up, and combined custom samples separately."""
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'artifacts/evaluations/custom40-depth20-v2'


def read(path):
    return json.loads(path.read_text())


def readable_prose(markdown):
    """Space prose numbers without modifying literal file paths or identifiers."""
    pieces = re.split(r'(```[\s\S]*?```|`[^`]*`)', markdown)
    for i in range(0, len(pieces), 2):
        pieces[i] = re.sub(r'\b(initial|original|added|combined|all|top)(20|40|57|737)\b', r'\1 \2', pieces[i], flags=re.I)
        pieces[i] = re.sub(r'\b(Section|Sections|March|October)(\d+)\b', r'\1 \2', pieces[i])
        pieces[i] = re.sub(r'\b(and|to|of|has|with|covers|passes|exposes|the|is|at|grade|rank|vs|strict)(?=\d)', r'\1 ', pieces[i])
    return ''.join(pieces)


def load():
    return {"metrics": read(FOLDER / 'metrics.json')['linear'],
            "extension": read(FOLDER.parent / 'custom40-extension20-depth20-v2/metrics.json')['linear'],
            "categories": read(FOLDER / 'by_category.json'),
            "paired": read(FOLDER / 'paired_comparison.json')['metrics'],
            "clustered": read(FOLDER / 'clustered_comparison.json'),
            "labels": [json.loads(l) for l in (ROOT / 'annotations/custom40_v2/assessments.all40.jsonl').read_text().splitlines()],
            "queries": [json.loads(l) for l in (ROOT / 'annotations/custom40_v2/queries.all40.jsonl').read_text().splitlines()]}


def test_count():
    return sum(int(s.attrib['tests']) for s in ET.parse(ROOT / 'artifacts/test-results-final.xml').getroot().iter('testsuite'))


def tables(data, original, initial, table):
    scopes = [('Original 57 supplied qrels', original), ('Initial custom 20', initial),
              ('Added custom 20', data['extension']), ('Combined custom 40', data['metrics'])]
    overall = table(['Evaluation set', 'BM25 nDCG@5', 'E5 nDCG@5', 'BM25 MAP', 'E5 MAP'],
                    [[name] + [f'{es[e]["aggregate"][m]:.4f}' for m in ['ndcg_at_5','ap_at_1000'] for e in ['bm25','dense']] for name, es in scopes])
    categories = table(['Category (10 each)', 'BM25 nDCG@5', 'E5 nDCG@5', 'BM25 MAP', 'E5 MAP'],
                       [[name] + [f'{data["categories"][key][e][m]:.4f}' for m in ['ndcg_at_5','ap_at_1000'] for e in ['bm25','dense']]
                        for key, name in [('vocabulary_mismatch','Vocabulary mismatch'),('negation','Negation'),('homonym','Word sense'),('temporal','Temporal')]])
    return overall, categories


def update_brief(pages, data, original, initial, table):
    """Keep the required four-page structure while replacing superseded findings."""
    pages = list(pages)
    pages[0] = pages[0].replace('We use two separate query sets.', 'We evaluate two distinct tasks.')
    start = pages[0].index('Our **20 custom queries**')
    end = pages[0].index('\n\n**Success measures:**', start)
    pages[0] = pages[0][:start] + ('Our **40 custom queries** have ten questions per category: vocabulary mismatch, negation, word sense and temporal constraints. The original 20 are preserved; 20 follow-up questions add ransomware, bail reform, Java/Mercury senses and dated disaster responses. Wording, inclusion rules and event windows were frozen before follow-up retrieval, after viewing the initial results. This is an exploratory extension, not an independent held-out replication.') + pages[0][end:]
    start = pages[0].index('**Assessment scope:**')
    pages[0] = pages[0][:start] + '''**Assessment scope and next validation:** the current comparison uses thorough, full-article **AI judgments** for all **1,444 query–article pairs** in the equal-depth top-20 union: 737 preserved initial decisions and 707 added decisions. Each judgment follows a frozen 0–2 rubric and has a rationale, source hash and quoted evidence. **Human review is planned next**, beginning with balanced cases across all 40 queries and adjudication of disagreements; it has not yet been completed. The custom results are therefore preliminary. Grade 0 fails a mandatory constraint, 1 gives limited qualifying detail, and 2 gives substantive support. Every top-20 hit is assessed, but only about 3% of each top-1,000 list is judged, so custom MAP is a **shallow-pool estimate**. Unjudged hits keep their ranks with zero contribution; all 40 queries remain in the averages, including V05 with no pooled positive.
'''
    overall, categories = tables(data, original, initial, table)
    ci = data['clustered']['design_families']['metrics']['ndcg_at_5']['cluster_bootstrap_95_percentile_ci']
    pages[2] = f'''## 5. Current findings and what they mean
Both engines, fixed RRF and the comparison demo are implemented. Supplied-qrels and custom tasks remain separate; custom MAP below uses pooled positives.

{overall}

{categories}

**The larger suite changes the comparison.** E5 leads the initial 20, while BM25 leads the added 20 and the combined 40. BM25 wins 21 queries at nDCG@5, E5 wins 15, and four tie. The combined vocabulary-mismatch result also reverses the initial pattern. More queries expose topic and wording sensitivity; they do not guarantee the expected neural advantage. RRF remains an original-benchmark extension: nDCG@5 **0.4900**, MAP **0.3332**.

**Failure modes:** exact entities and detailed constraints can help BM25. E5 sometimes retrieves the broad topic while missing a required cause, response or date. In the word-sense category, BM25 has slightly higher nDCG@5 but E5 higher pooled MAP; early ranking and recovery measure different behavior. Neither ranker enforces negation or time as a logical constraint. Temporal exclusions include missing date evidence, not only known out-of-window events.

**Uncertainty:** the combined E5−BM25 nDCG difference is **−0.0771**, with a descriptive 95% family-bootstrap interval **[{ci[0]:+.4f}, {ci[1]:+.4f}]** (37 topic families; 10,000 draws). Query and broader 35-family analyses also include zero for nDCG and MAP. These intervals do not measure label accuracy or establish a general winner.

**A practical improvement:** on the preserved initial 20, removing empty-body candidates raises E5 nDCG@5 **0.4897 → 0.5492**, P@5 **0.53 → 0.60**, with BM25 unchanged. This bounded, post-hoc top-20 ablation has not been rerun on the added queries.

**Resources and checks:** BM25 index **367.6 MiB**, dense index **1.72 GiB**, model about **418 MiB** on disk. BM25 built in **66.55 s** locally; T4 encoding took **5 h 43 min**. One cold CPU query took **1.4/48.6 s** (BM25/E5), including startup; hardware/stages differ. Peak RAM and controlled warm latency remain unmeasured. Verification: **{test_count()} passing tests**, **7,196 native metric comparisons**, and verified saved demo views; no new GPU encoding was required.
'''
    pages[3] = pages[3].replace('**Query expansion:** a separate 40-query suite now has ten questions per category. Its 20 new queries await relevance assessment; all results above remain for the completed original 20.', '**Expanded evaluation completed:** 40 queries, ten per category; all 1,444 designated pairs assessed. Initial, added and combined results are retained separately, with topic-family uncertainty and full-text evidence.')
    pages[3] = pages[3].replace('Hybrid, custom study, demo and report', 'Hybrid, 40-query study, demo and report')
    return pages


def expanded_pages(data, original, initial, table):
    overall, categories = tables(data, original, initial, table)
    return [f'''## 12. Expanded scope: 40-query follow-up and combined results
This section supersedes the initial-20 interpretation in Sections 7–8. Those tables and the quality ablation remain unchanged historical results. We added five information needs per category without altering the original queries, rankings or 737 decisions. The follow-up was designed after observing initial results; it is not a preregistered or independent held-out test. All new rubrics were frozen before follow-up retrieval. No model retraining or test-driven parameter tuning was performed.

{overall}

{categories}

The added 20 favor BM25 strongly enough to reverse both combined mean measures. The initial advantage of E5 on vocabulary mismatch and word sense is therefore not stable across this authored sample. BM25 leads all four combined category nDCG means, while E5 retains higher word-sense pooled MAP. Combined P@5 is **0.555 BM25 / 0.460 E5**. Per-query nDCG wins are **21 BM25 / 15 E5 / 4 ties**. The result does not show that lexical retrieval generally solves semantic mismatch: long queries contain useful matching terms, constraints differ, and the E5 representation has a shorter input budget.

Assessment now covers **1,444 pairs**, including **707 added decisions**. Four disjoint assessment batches used the protocol in Section 5; no agreement score is inferred from this division. Every unique available article in each assignment was read; exact same-query/full-content duplicates could reuse a documented decision. A targeted primary-assistant audit reviewed five borderline cases before metrics and downgraded one Japanese evacuation-advice judgment because issuance after March11 was not established. Original category files and the audit trail are retained. All 737 initial decisions are byte-preserved.

Temporal judgments require article-supported event dates. A report of a Brazilian deployment on “Saturday” without a calendar anchor can be topically appropriate but fail this evidence requirement. Such zeros should not all be interpreted as wrong-event retrieval. Relevance concerns the article's assertions and the frozen need; it does not certify every factual assertion in the source.
''', f'''## 13. Robustness of the expanded comparison
The all-40 E5−BM25 mean differences are **−0.0771 nDCG@5** and **−0.0356 pooled MAP**. We retain the initial query-bootstrap analysis and add paired topic-family resampling to avoid treating the cricket, Java and Mercury sense pairs as fully independent topics. Each resampled family carries all its queries; the ratio of summed differences to the resampled query count preserves the query-weighted estimand.

{table(['Resampling unit','nDCG@5 95% interval','Pooled MAP 95% interval'], [[name] + ['['+', '.join(f'{x:+.4f}' for x in (values[m]['paired_bootstrap_95_percentile_ci'] if name=='40 queries' else values[m]['cluster_bootstrap_95_percentile_ci']))+']' for m in ['ndcg_at_5','ap_at_1000']] for name, values in [('40 queries',data['paired']),('37 design families',data['clustered']['design_families']['metrics']),('35 broader topic groups',data['clustered']['broader_topic_sensitivity']['metrics'])]])}

All intervals include zero. The broader grouping additionally joins marriage-law and Ebola topics across categories. Neither grouping guarantees independent topic families; the intervals describe resampling variability, not judgment accuracy or generalization to an external query population. Category groups contain ten queries each and remain exploratory. Gain and confidence sensitivities are saved alongside each evaluation.

**Coverage and reproducibility.** Both engines' complete top20 are judged. Mean judged fraction at1000 is **2.9175% BM25 / 3.1500% E5**. Custom MAP remains incomplete-pool MAP; higher recall of pooled positives does not demonstrate corpus-wide completeness. V05 remains the sole zero-positive pool. Combined saved runs concatenate unchanged component ranks and scores, with component manifest hashes. Earlier E5 query encoding ran on a GPU, while follow-up query encoding used the CPU; combined timing is not a controlled benchmark. The document vectors, model revision and corpus remain the same.

**Concrete follow-up cases.** For V08, BM25 nDCG@5 is **0.9270**, E5 **0.3008**. BM25's first article (`5b0dbbda-5c3e-11e7-9fc6-c7ef4bc58d13`, grade2) connects wealthy arrivals, rising rents and forced moves in Bloomingdale; E5's first (`d056a7e2-f5df-11e5-8b23-538270a1ca31`, grade0) contains only a link to earlier columns. That is an article-content failure as well as a ranking observation. For N08, BM25's lead (`d29a85bb3643b94fb5ad7fb7bc77a1a4`, grade2) explains completed Keystone rejection, while E5's lead (`8d3f8976-41f0-11e1-8f2d-87a67739d0d2`, grade0) predicts an announcement later that day: the decisive constraint is completed versus pending action. V07 is a counterexample: E5 leads **0.3392 vs0.3156**, with a detailed D.C. risk-assessment article at rank1; BM25's first discusses cash bail without establishing the required alternative. These evidence-backed distinctions describe observed rankings, without proving a causal model mechanism.

**Validation.** Added and combined metrics contribute **588 + 1,148** independent native comparisons, giving **7,196** across the project. The current test suite has **{test_count()} passing tests**. The expanded report, saved demo, all40 frozen query texts, 1,444 decisions, targeted adjudication, source-run lineage and uncertainty artifacts are included in the local package. Full article packets, corpus, model and indexes are excluded from the portable archive and remain local dependencies.

**Next validation stage.** Human review is planned, starting with a balanced sample of positives, hard negatives and date-unsupported cases. After review, we will test passage-based or equal-input retrieval with fresh judgments. Controlled polarity pairs would isolate negation better than these natural multi-constraint queries. The larger suite supplies more diagnostic cases, while the reversal warns against assuming a model-level winner from the first five examples per category.
''']


def write_progress(data, original, initial, table):
    overall, cats = tables(data, original, initial, table)
    text = '# Expanded custom study: completed 40-query evaluation\n\n'
    text += '40 information needs, ten per category; 1,444 evidence-backed preliminary judgments. [Assessment method and planned human review](ASSESSMENT_METHOD.md): full-article AI judgments support the current comparison; human review is the next validation stage and has not yet been completed. The 20 follow-up needs were frozen before their retrieval, after initial results were known.\n\n'+overall+'\n\n'+cats+'\n\n'
    text += 'BM25 leads the expanded means; this reverses the initial sample. All query/family bootstrap intervals include zero. Scores were computed from saved rankings and graded evidence; original queries and 737 decisions remain unchanged. Custom MAP uses shallow pooled positives.\n\n'
    text += table(['ID','BM25 nDCG@5','E5 nDCG@5','BM25 pooled AP','E5 pooled AP'],[[q['_id']] + [f'{data["metrics"][e]["per_query"][q["_id"]][m]:.6f}' for m in ['ndcg_at_5','ap_at_1000'] for e in ['bm25','dense']] for q in data['queries']])
    text += '\n\nSee `annotations/custom40_v2/assessment_completion.json`, `adjudication.json`, `assessments.all40.jsonl`, and `artifacts/evaluations/custom40-depth20-v2/`. Original-20 quality ablations are preserved separately; no expanded ablation is claimed.\n'
    text += '\n\n![Expanded category comparison](figures/custom40-depth20/category_metrics.png)\n'
    (ROOT/'reports/CUSTOM_40_DEPTH20.md').write_text(readable_prose(text))


def figures(data):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder = ROOT/'reports/figures/custom40-depth20'
    folder.mkdir(parents=True, exist_ok=True)
    keys = ['vocabulary_mismatch','negation','homonym','temporal']
    fig, axes = plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for ax, metric, title in zip(axes,['ndcg_at_5','ap_at_1000'],['nDCG@5','Pooled MAP@1000']):
        for e, shift, color in [('bm25',-.18,'#236283'),('dense',.18,'#c77339')]:
            ax.bar([i+shift for i in range(4)],[data['categories'][k][e][metric] for k in keys],width=.36,label='BM25' if e=='bm25' else 'E5 dense',color=color)
        ax.set_xticks(range(4),['Vocabulary','Negation','Word sense','Temporal']); ax.set_ylim(0,1); ax.set_title(title); ax.legend();ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Preliminary custom comparison · 10 queries/category · top20 pool')
    for suffix in ['png','svg']: fig.savefig(folder/f'category_metrics.{suffix}',dpi=180)
    plt.close(fig)
