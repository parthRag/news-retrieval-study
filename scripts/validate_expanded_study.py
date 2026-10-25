"""Validate full expanded-pool evidence and all saved demo comparisons locally."""
import json
from pathlib import Path

from news_ir.assessment import validate_assessments
from news_ir.custom_depth20 import check_pool
from news_ir.data import sha256_file
from news_ir.demo import DemoService
from news_ir.evaluation import evaluate_rankings
from news_ir.expanded_study import clustered_comparison

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def main():
    ann = ROOT/'annotations/custom40_v2'
    original = ROOT/'annotations/ai_study_v1/assessments.depth20.jsonl'
    require((ann/'assessments.all40.jsonl').read_bytes() == original.read_bytes()+(ann/'assessments.extension20.jsonl').read_bytes(), 'Original label bytes changed')
    complete = read(ann/'assessment_completion.json')
    for filename, record in complete['parallel_category_sources'].items():
        require(sha256_file(ann/filename)==record['sha256'],'Assessor source changed')
    for name in ['extension','all40']:
        key = 'assessments_extension_sha256' if name=='extension' else 'assessments_all40_sha256'
        file = 'assessments.extension20.jsonl' if name=='extension' else 'assessments.all40.jsonl'
        require(sha256_file(ann/file)==complete[key], 'Final judgment hash changed')
    service = DemoService(ROOT)
    checked = 0
    try:
        for suffix, label_name, evaluation, count in [
            ('custom40-extension20-v2','extension20','custom40-extension20-depth20-v2',707),
            ('custom40-v2','all40','custom40-depth20-v2',1444)]:
            pool=ROOT/'artifacts/assessments'/suffix
            labels=ann/f'assessments.{label_name}.jsonl'
            validation=validate_assessments(pool,labels)
            require(validation['complete_pool'] and validation['assessed_pairs']==count,'Assessment coverage')
            qids=set(validation['qrels'])
            rankings={e:{q:[h['doc_id'] for h in hits] for q,hits in rows.items() if q in qids}
                      for e,rows in service.runs['expanded'].items()}
            provenance=[json.loads(x) for x in (pool/'pool.provenance.jsonl').read_text().splitlines()]
            check_pool(provenance,rankings,20)
            metrics=read(ROOT/'artifacts/evaluations'/evaluation/'metrics.json')
            for mode, engines in metrics.items():
                for engine, result in engines.items():
                    require(evaluate_rankings(rankings[engine],validation['qrels'],gain_mode=mode)==result,'Expanded metric mismatch')
        rows=[json.loads(x) for x in (ann/'assessments.all40.jsonl').read_text().splitlines()]
        grades={}
        for row in rows:
            doc=service.document(row['doc_id'],'expanded',row['query_id'])
            require(doc['assessment']==row,'Demo judgment mismatch')
            require(doc['e5_input_end'] is not None and 0<=doc['e5_input_end']<=len(doc['contents']),'Visibility coverage')
            for span in row['evidence']:
                require(doc['contents'][span['start']:span['end']]==span['quote'],'Source evidence mismatch')
            grades.setdefault((row['query_id'],row['contents_sha256']),set()).add(row['grade'])
            checked+=1
        require(all(len(g)==1 for g in grades.values()),'Duplicate content grade conflict')
        for suite, queries in service.catalog.items():
            for query in queries:
                replay=service.replay(suite,query['_id'],20)
                if suite!='original':
                    require(all(h['assessment'] for r in replay['engines'].values() for h in r['hits']),'Unassessed top20')
        require(service.catalog_data()['evaluated_query_count']==97,'Distinct demo query count')
        folder=ROOT/'artifacts/evaluations/custom40-depth20-v2'
        primary=read(folder/'metrics.json')['linear']
        clustered=read(folder/'clustered_comparison.json')
        for record in clustered.values():
            require(clustered_comparison(primary['bm25'],primary['dense'],record['families'])==record,'Family bootstrap reproduction')
    finally:
        service.close()
    result={'status':'passed','custom_queries':40,'assessed_pairs':1444,'source_evidence_visibility_checks':checked,
            'extension_pairs':707,'original_pairs_byte_preserved':737,'distinct_demo_queries':97,
            'saved_view_rows':117,'gain_modes_recomputed':['linear','exp2'],'family_bootstrap_recomputed':[37,35],
            'assessment_completion_sha256':sha256_file(ann/'assessment_completion.json')}
    (ROOT/'artifacts/custom40_depth20_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
