"""Inspect selected extremes without generating or changing relevance labels."""
import json
from pathlib import Path

from news_ir.data import DocumentStore
from report_integrated_study import table

ROOT=Path(__file__).resolve().parents[1]


def main():
 data=json.loads((ROOT/'artifacts/evaluations/integrated-core18-v1/metrics.json').read_text(encoding="utf-8"))['variants']
 queries={r['_id']:r for r in map(json.loads,(ROOT/'annotations/core18_v1/queries.jsonl').read_text(encoding="utf-8").splitlines())}
 labels={}
 for r in map(json.loads,(ROOT/'annotations/core18_v1/qrels.jsonl').read_text(encoding="utf-8").splitlines()):
  labels.setdefault(r['query-id'],{})[r['corpus-id']]=r['score']
 runs={e:{r['query_id']:r['hits'] for r in map(json.loads,(ROOT/f'artifacts/runs/{e}-core18-v1/results.jsonl').read_text(encoding="utf-8").splitlines())} for e in ['bm25','dense']}
 differences=[]
 for q in data['title']['bm25']['per_query']:
  tid=q.rsplit('-',1)[0];other=tid+'-rewrite'
  adv=(data['rewrite']['dense']['per_query'][other]['ndcg_at_5']-data['title']['dense']['per_query'][q]['ndcg_at_5'])-(data['rewrite']['bm25']['per_query'][other]['ndcg_at_5']-data['title']['bm25']['per_query'][q]['ndcg_at_5'])
  differences.append((adv,tid))
 cases=[min(differences),max(differences)];records=[]
 parts=['# Core 2018 paired ranking examples\n',
 'These are the two extremes of E5-minus-BM25 rewrite-change advantage, selected after scoring. They illustrate variability and are not a representative sample. Grades below are supplied NIST judgments, not new assessments; an unjudged hit remains explicitly unjudged. New rewrite intent still needs independent human review.\n']
 with DocumentStore(ROOT/'artifacts/indexes/bm25') as store:
  for advantage,tid in cases:
   title=queries[tid+'-title'];rewrite=queries[tid+'-rewrite']
   parts += [f'## Topic {tid}: {title["text"]}\n',f'Original: **{title["text"]}**. Rewrite: **{rewrite["text"]}**. Differential change: **{advantage:+.4f} nDCG@5**.\n',
    'Official narrative: '+title['narrative']+'\n']
   row_metrics=[];leaders=[]
   for variant in ['title','rewrite']:
    q=tid+'-'+variant
    for engine in ['bm25','dense']:
     score=data[variant][engine]['per_query'][q]['ndcg_at_5'];row_metrics.append([variant,engine,f'{score:.4f}'])
     for hit in runs[engine][q][:3]:
      doc=store.get(hit['doc_id']);grade=labels[q].get(hit['doc_id'],'Unjudged')
      leaders.append([variant,engine,hit['rank'],grade,doc.title,f"`{doc.doc_id}`"])
      records.append({'topic_id':tid,'variant':variant,'engine':engine,'rank':hit['rank'],'grade':grade,'doc_id':doc.doc_id,'title':doc.title})
   parts += [table(['Formulation','Engine','nDCG@5'],row_metrics),'\n'+table(['Formulation','Engine','Rank','NIST grade','Article title','ID'],leaders),
    '\nThe table establishes changes in observed ranking and reference grades. It does not establish a causal account of model reasoning; inspect the article text and retained E5 prefix in the demo.\n']
   if tid=='814':parts.append('E5 stays at 1.0000 in both formulations. Its negative differential advantage comes from BM25 improving, rather than from E5 failing. Absolute quality and robustness change are different quantities.\n')
   if tid=='825':parts.append('BM25 loses its known-positive top-five results after the rewrite, while E5 keeps the same grade-2 lead article. Some BM25 rewrite hits are unjudged, so a zero reference score does not establish that all retrieved articles are irrelevant.\n')
 (ROOT/'reports/CORE18_CASE_STUDIES.md').write_text('\n\n'.join(parts)+'\n', encoding="utf-8", newline="\n")
 (ROOT/'artifacts/integration-validation/selected_cases.json').write_text(json.dumps(records,indent=2)+'\n', encoding="utf-8", newline="\n")
 print('Wrote two selected paired cases and 24 top-three ranking observations.')

if __name__=='__main__':main()
