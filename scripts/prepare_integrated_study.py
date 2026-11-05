"""Freeze Core 2018 formulations and audit the existing available news corpus."""
import json
from datetime import datetime, timezone
from pathlib import Path

from news_ir.data import DocumentStore, sha256_file

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'studies/hamsini_robustness'
OUT = ROOT / 'annotations/core18_v1'

# Written before any Core 2018 retrieval was executed. These are provisional
# machine-authored formulations, not claimed as independent human verification.
REWRITES = {
 '321':'female legislative representation', '336':'black bear assaults',
 '341':'air travel passenger screening', '347':'preventing animal species extinction',
 '350':'occupational health risks of computer screens', '362':'clandestine people transport',
 '363':'transit tunnel catastrophes', '367':'maritime vessel hijacking',
 '375':'power from hydrogen', '378':'euro currency resistance', '393':'euthanasia',
 '397':'passenger car safety recalls', '400':'Amazonian rainforest preservation',
 '408':'destructive tropical cyclones', '414':'Cuban sugar shipments abroad',
 '422':'artwork theft and counterfeiting', '426':'police canine use',
 '427':'ultraviolet harm to vision', '433':'ancient Greek Stoic thought',
 '439':'scientific breakthroughs and novel inventions', '442':'selfless deeds of bravery',
 '445':'female church pastors', '626':'crowd crushes', '646':'rising SNAP participation',
 '690':'university degree employment benefits', '801':'African poliomyelitis immunization',
 '802':"Saudi women's right to drive", '803':'shrinking American middle-income class',
 '804':'female portrait on twenty-dollar bill', '805':'consuming invasive organisms',
 '806':'computing aids for people with paralysis', '807':"Hugo Chavez's Cuban health care",
 '808':'Boston race bombing trial outcome', '809':'planetary defense against asteroid collisions',
 '810':'chemical exposure and diabetes risk', '811':'vehicle cybersecurity',
 '812':'social network harassment and teenage suicide', '813':'cannabis strength',
 '814':"consequences of China's single-child rule",
 '815':'Iranian release of journalist Jason Rezaian',
 '816':'raising the national minimum pay floor', '817':'Cuba frees USAID contractor Alan Gross',
 '818':'nutritional benefits of eating eggs', '819':'American population age distribution',
 '820':'fatality rates from bacterial diseases', '821':'fraudulent electronic mail schemes',
 '822':'Sony Pictures computer intrusion', '823':'containing methicillin-resistant Staphylococcus aureus',
 '824':'Jeff Bezos buys the Post', '825':'maize alcohol fuel and food costs',
}


def write(path, value):
 path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding="utf-8", newline="\n")


def main():
 if OUT.exists(): raise FileExistsError('Frozen protocol exists; choose a new version')
 topics=[json.loads(l) for l in (SOURCE/'queries/core18_topics.jsonl').read_text(encoding="utf-8").splitlines()]
 assert len(topics)==50 and {t['query_id'] for t in topics}==set(REWRITES)
 proof=json.loads((ROOT/'artifacts/reviews/2026-11-02-project-comparison/core18_coverage.json').read_text(encoding="utf-8"))
 assert proof['official_nist_pair_grade_match']
 assert sha256_file(SOURCE/'queries/core18.qrels')==proof['peer_qrels_sha256']
 rows=[]
 for topic in topics:
  tid=topic['query_id']
  for variant,text in [('title',topic['title']),('description',topic['description']),('rewrite',REWRITES[tid])]:
   a=set(topic['title'].casefold().split());b=set(text.casefold().split())
   rows.append({'_id':f'{tid}-{variant}','text':text,'topic_id':tid,'variant':variant,
     'original_title':topic['title'],'description':topic['description'],'narrative':topic['narrative'],
     'formulation_source':'NIST official topic field' if variant!='rewrite' else 'AI-authored before retrieval; human intent review pending',
     'official_formulation':variant!='rewrite', 'independent_human_rewrite_review_completed':False,
     'length_change_words':len(text.split())-len(topic['title'].split()),
     'surface_token_jaccard':len(a&b)/len(a|b) if a|b else 1.0})
 OUT.mkdir(parents=True)
 (OUT/'queries.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows), encoding="utf-8", newline="\n")
 raw=[]
 for line in (SOURCE/'queries/core18.qrels').read_text(encoding="utf-8").splitlines():
  q,_,d,g=line.split();raw.append((q,d,int(g)))
 labels=[{'query-id':f'{q}-{v}','corpus-id':d,'score':g} for q,d,g in raw for v in ['title','description','rewrite']]
 (OUT/'qrels.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in labels), encoding="utf-8", newline="\n")
 with DocumentStore(ROOT/'artifacts/indexes/bm25') as store:
  actual=sha256_file(store.corpus)
  assert actual==store.manifest['source']['sha256']==proof['local_corpus_source_sha256']
  missing=[]
  for q,d,g in raw:
   hit=store._db.execute('SELECT eligible FROM documents WHERE doc_id=?',(d,)).fetchone()
   if not hit or not hit[0]:missing.append({'topic_id':q,'doc_id':d,'grade':g,'reason':'absent' if not hit else 'empty'})
  dense=json.loads((ROOT/'artifacts/indexes/dense/manifest.json').read_text(encoding="utf-8"))
  assert dense.get('corpus_sha256',dense.get('source_sha256'))==actual
  assert dense['coverage']=='full' and dense['indexed_documents']==store.manifest['documents']['indexed']
  audit={'status':'passed_for_available_corpus_study','official_corpus_equivalence':False,
   'corpus_sha256':actual,'documents':store.manifest['documents'],
   'official_qrels_pair_grade_match':True,'official_qrels_sha256':proof['official_qrels_sha256'],
   'topics':50,'original_judgments':len(raw),'missing_judgments':missing,
   'missing_positive_judgments':sum(r['grade']>0 for r in missing),
   'scope':'Core 2018 topics on the available TREC-News mirror; not official WaPo v2 reproduction. ID coverage and sampled source identity cannot establish official text equivalence.'}
  write(OUT/'corpus_audit.json',audit)
 protocol={'created_at_utc':datetime.now(timezone.utc).isoformat(),'query_count':150,'topic_count':50,
  'variants':['title','description','rewrite'],'formulation_origin':{
   'title':'Official NIST title; benchmark baseline',
   'description':'Official NIST description; query-form diagnostic, confounded by length/detail, not controlled paraphrase',
   'rewrite':'One provisional AI-authored paraphrase per topic; intended to retain narrative relevance, independent human review pending'},
  'primary_comparison':'Within-topic title vs rewrite; conditional on intent preservation. Description separate.',
  'qrel_reuse':'Human NIST relevance labels reused only under the stated information need; no new human relevance or rewrite-verification claims.',
  'selection':'All 50 topics, no selection by outcomes. Texts frozen before first Core 2018 retrieval. Existing news/COVID results were already known.',
  'settings':'Existing full-corpus BM25 and pinned E5 indexes; RRF k=60; top 1000; no model training or parameter tuning',
  'statistics':'Paired original/rewrite changes over 50 topics; 10000 bootstrap/sign-flip draws; Holm within each declared family. Never pool COVID/news/custom scores.',
  'metrics':['nDCG@5','nDCG@10','MAP@1000','Recall@100','Judged@5/10','condensed nDCG@5/10','bpref'],
  'missing_documents':'Retain all qrels in primary denominators/IDCG; separate available-corpus sensitivity',
  'files':{p.name:sha256_file(p) for p in OUT.iterdir() if p.is_file()}}
 write(OUT/'protocol.json',protocol)
 print(json.dumps({'queries':len(rows),'missing_judgments':len(missing),'missing_positive':audit['missing_positive_judgments']},indent=2))

if __name__=='__main__':main()
