"""Recompute the preserved COVID study and the new available-corpus Core 2018 study.

All outputs are versioned; old judgments, queries and evaluation files are untouched.
"""
import argparse
import csv
import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from news_ir.benchmark import crosscheck
from news_ir.data import DocumentStore, sha256_file
from news_ir.evaluation import load_qrels, load_run
from news_ir.paired_stats import compare
from news_ir.robustness import evaluate_extended, paired_formulation_tests, topic_cluster_feature_tests

ROOT=Path(__file__).resolve().parents[1]


def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def assert_snapshot():
 manifest=json.loads((ROOT/'studies/hamsini_robustness.provenance.json').read_text())
 for name,digest in manifest['files'].items():
  if sha256_file(ROOT/'studies/hamsini_robustness'/name)!=digest:raise ValueError('Imported study changed: '+name)
 return manifest


def read_trec(path):
 rows={}
 for line in path.read_text().splitlines():
  q,_,d,rank,score,tag=line.split()
  if d in rows.setdefault(q,{}):raise ValueError('Duplicate TREC hit')
  rows[q][d]=float(score)
 # Preserve the original evaluator's score/docid-descending tie convention.
 return {q:sorted(docs,key=lambda d:(docs[d],d),reverse=True) for q,docs in rows.items()}


def covid(out):
 source=ROOT/'studies/hamsini_robustness'
 labels={}
 for line in (source/'queries/trec_covid.qrels').read_text().splitlines():
  q,_,d,g=line.split();labels.setdefault(q,{})[d]=int(g)
 variants={};files={};comparisons=0
 for variant,suffix in [('original','query'),('description','text'),('rewrite_a','rewrite_a'),('rewrite_b','rewrite_b')]:
  variants[variant]={}
  for engine in ['bm25','dense','rrf']:
   path=source/f'runs/trec_covid/{engine}_{suffix}.run'
   result=evaluate_extended(read_trec(path),labels)
   variants[variant][engine]=result
   files[str(path.relative_to(ROOT))]=sha256_file(path)
   saved=list(csv.DictReader((source/f'results/trec_covid/{engine}_{suffix}.csv').open()))
   mapping={'nDCG@10':'ndcg_at_10','AP(rel=1)':'ap_at_1000','R(rel=1)@100':'recall_at_100',
    'Judged@10':'judged_at_10','nDCG(judged_only=True)@10':'condensed_ndcg_at_10','Bpref':'bpref'}
   # Original evaluation consumed serialized model/fusion scores. Verify that
   # historical protocol separately; our new evaluation preserves published ranks
   # with ordinal scores, which can differ at floating-point score ties.
   import ir_measures
   raw={}
   for line in path.read_text().splitlines():
    q,_,d,rank,score,tag=line.split();raw.setdefault(q,{})[d]=float(score)
   history={}
   for item in ir_measures.evaluator([ir_measures.parse_measure(m) for m in mapping],labels).iter_calc(raw):
    history[(item.query_id,str(item.measure))]=item.value
   for row in saved:
    canonical=str(ir_measures.parse_measure(row['measure']))
    if abs(history[(row['qid'],canonical)]-float(row['value']))>5.01e-7:
     raise ValueError(f"Historical imported score reproduction failed: {engine}/{suffix}/{row['qid']}/{row['measure']}")
    comparisons+=1
 changes=paired_formulation_tests(variants,control='original',alternatives=('rewrite_a','rewrite_b'))
 features=list(csv.DictReader((source/'queries/variants/trec_covid_rewrite_features.csv').open()))
 observations=[]
 for row in features:
  q=row['qid'];v='rewrite_'+row['variant']
  adv=(variants[v]['dense']['per_query'][q]['ndcg_at_10']-variants['original']['dense']['per_query'][q]['ndcg_at_10'])-(variants[v]['bm25']['per_query'][q]['ndcg_at_10']-variants['original']['bm25']['per_query'][q]['ndcg_at_10'])
  observations.append({'topic_id':q,'advantage':adv,**{k:float(row[k]) for k in ['content_overlap','length_change','mean_idf','n_words']}})
 clustered=topic_cluster_feature_tests(observations,['content_overlap','length_change','mean_idf','n_words'])
 # Flagged in the pre-integration review; retain originals and report omission only as sensitivity.
 sensitivity={v:{e:evaluate_extended({q:r for q,r in read_trec(source/f'runs/trec_covid/{e}_{suffix}.run').items() if q not in {'5','12'}},
  {q:j for q,j in labels.items() if q not in {'5','12'}})['aggregate'] for e in ['bm25','dense','rrf']}
  for v,suffix in [('original','query'),('rewrite_a','rewrite_a'),('rewrite_b','rewrite_b')]}
 write(out/'metrics.json',{'variants':variants,'flagged_topic_omission_sensitivity':sensitivity})
 write(out/'paired_changes.json',changes);write(out/'topic_mean_features.json',clustered)
 return {'dataset':'TREC-COVID','topic_count':50,'documents':171331,'recomputed_saved_csv_values':comparisons,
  'source_files':files,'interpretation':'Imported human qrels; rewrite equivalence was single-annotator verified in source study. Topics 5/12 flagged for independent review; exclusion is a sensitivity, not repaired ground truth.',
  'attribution':'Controlled COVID rewrite study by Hamsini G; integrated re-evaluation/extra @5 metrics/topic-mean feature analysis added separately.',
  'ranking_note':'Historical score-based CSVs reproduce. Integrated metrics use derived ordinal scores to preserve published rank order; near-tie handling can produce small differences. Both original files and original CSVs are preserved.'}


def core18(out,native):
 folder=ROOT/'annotations/core18_v1';protocol=json.loads((folder/'protocol.json').read_text())
 for name,digest in protocol['files'].items():
  if sha256_file(folder/name)!=digest:raise ValueError('Frozen Core 2018 input changed')
 queries=[json.loads(l) for l in (folder/'queries.jsonl').read_text().splitlines()]
 labels=load_qrels(folder/'qrels.jsonl',[q['_id'] for q in queries])
 with DocumentStore(ROOT/'artifacts/indexes/bm25') as store:
  eligible={r[0] for r in store._db.execute('SELECT doc_id FROM documents WHERE eligible=1')}
  corpus_sha=store.manifest['source']['sha256']
 runs={};manifests={}
 for engine in ['bm25','dense','rrf']:
  path=ROOT/f'artifacts/runs/{engine}-core18-v1'
  runs[engine],manifest=load_run(path,folder/'queries.jsonl',eligible,expected_source_sha256=corpus_sha)
  manifests[engine]={'path':str(path.relative_to(ROOT)),'manifest_sha256':sha256_file(path/'manifest.json')}
 variants={};available={};checks={}
 for variant in protocol['variants']:
  ids=[q['_id'] for q in queries if q['variant']==variant]
  judgments={q:labels[q] for q in ids}
  available_labels={q:{d:g for d,g in j.items() if d in eligible} for q,j in judgments.items()}
  variants[variant]={};available[variant]={};checks[variant]={}
  for engine,run in runs.items():
   ranking={q:run[q] for q in ids}
   result=evaluate_extended(ranking,judgments);variants[variant][engine]=result
   available[variant][engine]=evaluate_extended(ranking,available_labels)
   if native:checks[variant][engine]=crosscheck(judgments,ranking,result,out/'native',name=f'{variant}-{engine}')
 write(out/'metrics.json',{'variants':variants,'available_corpus_sensitivity':available})
 write(out/'paired_changes.json',paired_formulation_tests(variants))
 write(out/'native_crosscheck.json',checks)
 return {'dataset':'Core 2018 on available news mirror','topic_count':50,'query_count':150,
  'corpus_sha256':corpus_sha,'eligible_documents':len(eligible),'official_corpus_equivalence':False,
  'query_source_sha256':sha256_file(folder/'queries.jsonl'),'qrels_sha256':sha256_file(folder/'qrels.jsonl'),
  'protocol_sha256':sha256_file(folder/'protocol.json'),'runs':manifests,
  'native_comparisons':sum(r['comparisons'] for systems in checks.values() for r in systems.values()),
  'interpretation':'Separate title baseline, official description query-form diagnostic and provisional AI rewrite experiment; human rewrite intent review pending. All qrels retained in primary denominator.'}


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--study',choices=['covid','core18'],required=True)
 parser.add_argument('--output',type=Path);parser.add_argument('--native',action='store_true');args=parser.parse_args()
 source=assert_snapshot()
 target=args.output or ROOT/f'artifacts/evaluations/integrated-{args.study}-v1'
 if target.exists():raise FileExistsError('Evaluation exists; choose a new version')
 target.parent.mkdir(parents=True,exist_ok=True)
 working=Path(tempfile.mkdtemp(prefix='.integrated-evaluation-',dir=target.parent))
 try:
  meta=covid(working) if args.study=='covid' else core18(working,args.native)
  meta.update(imported_source_commit=source['commit'],files={str(p.relative_to(working)):sha256_file(p) for p in working.rglob('*') if p.is_file()})
  write(working/'manifest.json',meta);working.rename(target)
  print(json.dumps({'output':str(target),**{k:v for k,v in meta.items() if k not in ['files','source_files','runs']}},indent=2))
 except BaseException:shutil.rmtree(working);raise

if __name__=='__main__':main()
