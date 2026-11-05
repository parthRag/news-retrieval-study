"""Verify integrated saved results without the corpus, model, Java or live demo."""
import json
from pathlib import Path

from news_ir.data import read_queries,sha256_file
from news_ir.evaluation import load_qrels,load_run
from news_ir.robustness import evaluate_extended,paired_formulation_tests,topic_cluster_feature_tests
import csv
from evaluate_integrated_study import assert_snapshot,read_trec

ROOT=Path(__file__).resolve().parents[1]


def main():
 source=assert_snapshot();base=ROOT/'artifacts/evaluations'
 summary={'status':'passed','imported_revision':source['commit'],'imported_files':len(source['files'])}
 for dataset in ['core18','covid']:
  folder=base/f'integrated-{dataset}-v1';manifest=json.loads((folder/'manifest.json').read_text(encoding="utf-8"))
  for name,digest in manifest['files'].items():
   if sha256_file(folder/name)!=digest:raise ValueError('Evaluation file changed: '+name)
  all_expected=json.loads((folder/'metrics.json').read_text(encoding="utf-8"))
  expected=all_expected['variants']
  if dataset=='core18':
   inputs=ROOT/'annotations/core18_v1'
   protocol=json.loads((inputs/'protocol.json').read_text(encoding="utf-8"))
   for name,digest in protocol['files'].items():
    if sha256_file(inputs/name)!=digest:raise ValueError('Frozen Core 2018 file changed')
   queries=read_queries(inputs/'queries.jsonl');labels=load_qrels(inputs/'qrels.jsonl',[q['_id'] for q in queries])
   rankings={}
   for engine,entry in manifest['runs'].items():
    root=ROOT/entry['path']
    if sha256_file(root/'manifest.json')!=entry['manifest_sha256']:raise ValueError('Run manifest changed')
    # Checks the exported rankings/identity, not corpus-wide coverage from absent text.
    ids={h['doc_id'] for row in map(json.loads,(root/'results.jsonl').read_text(encoding="utf-8").splitlines()) for h in row['hits']}
    rankings[engine],_=load_run(root,inputs/'queries.jsonl',ids,expected_source_sha256=manifest['corpus_sha256'])
  else:
   labels={}
   for line in (ROOT/'studies/hamsini_robustness/queries/trec_covid.qrels').read_text(encoding="utf-8").splitlines():
    q,_,d,g=line.split();labels.setdefault(q,{})[d]=int(g)
  comparisons=0
  for variant,systems in expected.items():
   for engine,result in systems.items():
    qids=list(result['per_query']);judgments={q:labels[q] for q in qids}
    if dataset=='core18':run={q:rankings[engine][q] for q in qids}
    else:
     suffix={'original':'query','description':'text'}.get(variant,variant)
     run=read_trec(ROOT/f'studies/hamsini_robustness/runs/trec_covid/{engine}_{suffix}.run')
    actual=evaluate_extended(run,judgments)
    if actual!=result:raise ValueError(f'Integrated metric mismatch: {dataset}/{variant}/{engine}')
    comparisons+=actual['independent_standard_metric_comparisons']
    if dataset=='core18':
     audit=json.loads((inputs/'corpus_audit.json').read_text(encoding="utf-8"))
     excluded={(r['topic_id'],r['doc_id']) for r in audit['missing_judgments']}
     available={q:{d:g for d,g in judgments[q].items() if (q.rsplit('-',1)[0],d) not in excluded} for q in qids}
     if evaluate_extended(run,available)!=all_expected['available_corpus_sensitivity'][variant][engine]:
      raise ValueError('Available-corpus sensitivity differs')
    elif variant in all_expected['flagged_topic_omission_sensitivity']:
     filtered={q:ids for q,ids in run.items() if q not in {'5','12'}}
     reduced={q:j for q,j in judgments.items() if q not in {'5','12'}}
     if evaluate_extended(filtered,reduced)['aggregate']!=all_expected['flagged_topic_omission_sensitivity'][variant][engine]:
      raise ValueError('Flagged-topic sensitivity differs')
  changes=paired_formulation_tests(expected) if dataset=='core18' else paired_formulation_tests(expected,control='original',alternatives=('rewrite_a','rewrite_b'))
  if changes!=json.loads((folder/'paired_changes.json').read_text(encoding="utf-8")):raise ValueError('Paired changes differ')
  if dataset=='covid':
   observations=[]
   for row in csv.DictReader((ROOT/'studies/hamsini_robustness/queries/variants/trec_covid_rewrite_features.csv').open(encoding="utf-8")):
    q=row['qid'];v='rewrite_'+row['variant']
    advantage=(expected[v]['dense']['per_query'][q]['ndcg_at_10']-expected['original']['dense']['per_query'][q]['ndcg_at_10'])-(expected[v]['bm25']['per_query'][q]['ndcg_at_10']-expected['original']['bm25']['per_query'][q]['ndcg_at_10'])
    observations.append({'topic_id':q,'advantage':advantage,**{k:float(row[k]) for k in ['content_overlap','length_change','mean_idf','n_words']}})
   if topic_cluster_feature_tests(observations,['content_overlap','length_change','mean_idf','n_words'])!=json.loads((folder/'topic_mean_features.json').read_text(encoding="utf-8")):
    raise ValueError('Topic-mean feature analysis differs')
  summary[dataset]={'topics':50,'formulations':len(expected),'engines':3,'independent_standard_metric_comparisons':comparisons,'metrics_and_paired_tests':'exact reproduction'}
 out=ROOT/'artifacts/integration-validation';out.mkdir(exist_ok=True,parents=True)
 (out/'numerical.json').write_text(json.dumps(summary,indent=2)+'\n', encoding="utf-8", newline="\n")
 print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
