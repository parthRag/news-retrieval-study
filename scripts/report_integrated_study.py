"""Generate the combined-study report from immutable evaluation outputs."""
import json
from pathlib import Path

from integrated_reporting import load, comparison_table

ROOT=Path(__file__).resolve().parents[1]


def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
  ['| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in rows])


def main():
 data=load()
 if data is None:raise ValueError('Complete Core 2018 evaluation before reporting combined results')
 parts=['# Integrated news and controlled-rewrite study\n',
  'The main project keeps the existing news corpus, BM25/E5 indexes and article-inspection demo. Hamsini G’s controlled TREC-COVID experiment is imported byte-for-byte with attribution, and the design is applied to 50 Core 2018 topics on the available news corpus. Scores are always separate by dataset and formulation.\n',
  '## Separate effectiveness results\n',
  '**nDCG@5**\n'+comparison_table(data,table),
  '\n**nDCG@10**\n'+comparison_table(data,table,'ndcg_at_10'),
  '\n**MAP@1000**\n'+comparison_table(data,table,'ap_at_1000')]
 for dataset in ['core18','covid']:
  folder=ROOT/f'artifacts/evaluations/integrated-{dataset}-v1'
  changes=json.loads((folder/'paired_changes.json').read_text())
  parts.append(f'\n## {dataset}: paired changes and uncertainty\n')
  for metric in ['ndcg_at_5','ndcg_at_10','ap_at_1000','condensed_ndcg_at_10','bpref']:
   parts.append(f'\n**{metric}**\n'+table(['Comparison (A − B)','Mean change','95% interval','p Holm','Wins/ties/losses'],
    [[r['run_a']+' − '+r['run_b'],f"{r['mean_diff']:+.6f}",f"[{r['ci_low']:+.6f}, {r['ci_high']:+.6f}]",f"{r['p_holm']:.6f}",f"{r['wins']}/{r['ties']}/{r['losses']}"] for r in changes[metric]]))
  parts.append('\n**Judgment coverage:**\n'+table(['Formulation','BM25 Judged@10','E5 Judged@10','RRF Judged@10'],
   [[v]+[f'{systems[e]["aggregate"]["judged_at_10"]:.4f}' for e in ['bm25','dense','rrf']] for v,systems in data[dataset]['variants'].items()]))
 parts.append('''
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
''')
 (ROOT/'reports/INTEGRATED_STUDY.md').write_text('\n\n'.join(parts)+'\n')
 summary={dataset:{v:{e:r['aggregate'] for e,r in systems.items()} for v,systems in d['variants'].items()} for dataset,d in data.items()}
 (ROOT/'deliverables/integrated_results.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
