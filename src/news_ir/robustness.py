"""Controlled topic-paired comparisons integrating Hamsini G's study design.

No scores are pooled across datasets or across different formulation variants.
Published rank order is preserved with ordinal scores for the external backend.
"""
import math
from dataclasses import asdict

import numpy as np

from .evaluation import evaluate_rankings
from .paired_stats import compare

BACKEND_MEASURES = {
 'ndcg_at_5':'nDCG@5','ndcg_at_10':'nDCG@10','ap_at_1000':'AP@1000',
 'recall_at_1000':'R@1000','precision_at_5':'P@5','precision_at_10':'P@10',
 'judged_at_5':'Judged@5','judged_at_10':'Judged@10',
 'recall_at_100':'R@100','condensed_ndcg_at_5':'nDCG(judged_only=True)@5',
 'condensed_ndcg_at_10':'nDCG(judged_only=True)@10','bpref':'Bpref',
}


def evaluate_extended(rankings, qrels):
 """Keep our evaluator and independently check standard metrics via ir_measures."""
 import ir_measures
 base=evaluate_rankings(rankings,qrels)
 measures={str(ir_measures.parse_measure(v)):k for k,v in BACKEND_MEASURES.items()}
 ordinal={q:{d:1001-i for i,d in enumerate(ids,1)} for q,ids in rankings.items()}
 values={q:{m:0.0 for m in BACKEND_MEASURES} for q in qrels}
 for metric in ir_measures.evaluator([ir_measures.parse_measure(v) for v in BACKEND_MEASURES.values()],qrels).iter_calc(ordinal):
  values[metric.query_id][measures[str(metric.measure)]]=float(metric.value)
 checks=0
 for q,computed in values.items():
  for name,val in computed.items():
   if name in base['per_query'][q]:
    if not math.isclose(base['per_query'][q][name],val,abs_tol=1e-10):
     raise ValueError(f'Independent metric disagreement {q}/{name}')
    checks+=1
   base['per_query'][q][name]=val
 for name in BACKEND_MEASURES:
  base['aggregate'][name]=float(np.mean([r[name] for r in values.values()]))
 base['independent_standard_metric_comparisons']=checks
 base['extra_metrics_backend']='ir_measures 0.4.3 / pytrec_eval; ordinal scores preserve saved order'
 return base


def paired_formulation_tests(variants, *, control='title', alternatives=('rewrite','description'), seed=20261102):
 """One observation per topic, Holm within each metric's declared comparison family."""
 metrics=['ndcg_at_5','ndcg_at_10','ap_at_1000','condensed_ndcg_at_10','bpref']
 engines=list(variants[control])
 scores={}
 for variant,systems in variants.items():
  for engine,result in systems.items():
   # Query IDs end in a variant suffix, but shared topic ID is the pairing key.
   rows={q.rsplit('-',1)[0]:v for q,v in result['per_query'].items()}
   if len(rows)!=len(result['per_query']):raise ValueError('Duplicate topic within variant')
   scores[f'{engine}_{variant}']=rows
 pairs=[]
 for alt in alternatives:
  for engine in engines:pairs.append((f'{engine}_{alt}',f'{engine}_{control}'))
  pairs.append((f'dense_{alt}-dense_{control}',f'bm25_{alt}-bm25_{control}'))
 # Change-vs-change is the difference in loss, not just a comparison of rewrite levels.
 for alt in alternatives:
  for engine in engines:
   a=scores[f'{engine}_{alt}'];b=scores[f'{engine}_{control}']
   if set(a)!=set(b):raise ValueError('Formulations must cover identical topics')
   scores[f'{engine}_{alt}-{engine}_{control}']={q:{m:a[q][m]-b[q][m] for m in metrics} for q in a}
 return {m:[asdict(r) for r in compare(scores,pairs,m,seed=seed)] for m in metrics}


def topic_cluster_feature_tests(observations, features, *, samples=2000, seed=20261102):
 """Aggregate both rewrites per topic before feature/performance association.

The estimand is explicitly topic-mean feature vs topic-mean advantage, rather
than the original pooled rewrite-level correlation. No independent-rewrite claim.
"""
 from .paired_stats import holm
 from scipy.stats import rankdata
 groups={}
 for row in observations:groups.setdefault(row['topic_id'],[]).append(row)
 if len(groups)<2:raise ValueError('Need multiple independent topics')
 def rho(x,y):
  a,b=rankdata(x),rankdata(y)
  return float(np.corrcoef(a,b)[0,1]) if a.std() and b.std() else 0.0
 y=np.array([np.mean([r['advantage'] for r in rows]) for rows in groups.values()])
 result=[]
 for feature in features:
  x=np.array([np.mean([r[feature] for r in rows]) for rows in groups.values()])
  observed=rho(x,y);rng=np.random.default_rng(seed)
  p=(1+sum(abs(rho(x,rng.permutation(y)))>=abs(observed)-1e-12 for _ in range(samples)))/(samples+1)
  result.append({'feature':feature,'topics':len(groups),'spearman_rho':observed,'p_value':p})
 for row,p in zip(result,holm([r['p_value'] for r in result])):row['p_holm']=p
 return {'unit':'topic means of both rewrites; changed estimand from pooled rewrite correlation',
         'samples':samples,'seed':seed,'results':result}
