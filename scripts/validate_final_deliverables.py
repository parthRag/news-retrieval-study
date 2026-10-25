"""Audit the release and recompute published metrics from packaged saved artifacts.

Does not require corpus text, model weights or a running demo. PDF structure/text
is checked against separately generated macOS PDFKit inspection artifacts.
"""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from news_ir.data import sha256_file
from news_ir.evaluation import evaluate_rankings,load_qrels,load_run
from news_ir.quality import filter_candidates,quality_scores
from news_ir.expanded_study import clustered_comparison

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'

def read(path): return json.loads((ROOT/path).read_text())
def require(ok,message):
    if not ok: raise ValueError(message)


def main():
    if (OUT/'release_manifest.json').exists():
        manifest=read('deliverables/release_manifest.json')
        archive=OUT/manifest['archive']
        require(sha256_file(archive)==manifest['archive_sha256'],'Archive hash')
        with zipfile.ZipFile(archive) as bundle:
            require(bundle.testzip() is None,'Corrupt ZIP entry')
            inner=json.loads(bundle.read('PACKAGE_MANIFEST.json'))
            require(inner['files']==manifest['files'],'Archive/outer manifest mismatch')
            require(set(bundle.namelist())==set(manifest['files'])|{'PACKAGE_MANIFEST.json'},'Unexpected archive entries')
            for name,digest in manifest['files'].items():
                require(hashlib.sha256(bundle.read(name)).hexdigest()==digest,'Archive member hash: '+name)
        verification_mode='local archive and source tree'
    else:
        manifest=read('PACKAGE_MANIFEST.json')
        manifest.update(file_count=len(manifest['files']),archive_bytes=None,archive_sha256=None)
        verification_mode='extracted package members; archive itself is external'
    for name,digest in manifest['files'].items():
        p=Path(name)
        require(not p.is_absolute() and '..' not in p.parts,'Unsafe archive path')
        require(p.name not in {'corpus.jsonl','articles.blinded.jsonl'} and
                not any(x in p.parts for x in ['.venv','__pycache__','models','indexes','encodings']), 'Excluded data in archive')
        require(sha256_file(ROOT/name)==digest,'Local release file changed: '+name)
    metadata=read('configs/submission.json')
    brief=metadata['group_number']+'_'+metadata['short_title']
    inspections={name:read(f'artifacts/pdf-review/{name}/inspection.json') for name in ['brief','research']}
    require(inspections['brief']['page_count']==4,'Brief must have four pages')
    require(inspections['research']['page_count']==19,'Research report page count changed')
    for name in inspections:
        text=(ROOT/f'artifacts/pdf-review/{name}/extracted.txt').read_text()
        pdf=OUT/((brief if name=='brief' else 'RESEARCH_REPORT')+'.pdf')
        require(sha256_file(pdf)==inspections[name]['pdf_sha256'],'PDF inspection is stale')
        require(all(p['characters']>500 for p in inspections[name]['pages']),'Unexpected blank PDF page')
        require('0.4621' in text and '0.4897' in text and '0.5492' in text,'Missing quantitative PDF content')
        expanded=read('artifacts/evaluations/custom40-depth20-v2/metrics.json')['linear']
        require(all(f"{expanded[e]['aggregate'][m]:.4f}" in text for e in ['bm25','dense']
                    for m in ['ndcg_at_5','ap_at_1000']),'Missing expanded PDF metrics')
        require('Contribution' in text or name=='research','Missing brief contribution matrix')
        review_text=''.join(text.casefold().split())
        require('humanreviewisplanned' in review_text and 'hasnotyetbeencompleted' in review_text,
                'Missing preliminary-reference status or planned human-review stage')
        require(''.join(metadata['group_number'].split()) in ''.join(text.split()),'Missing metadata')
        normalized=''.join(text.split())
        for member in metadata.get('member_details',[]):
            require(member['student_id'] in normalized,'Missing student ID in PDF')
            require(''.join(member['name'].split()) in normalized,'Missing member name in PDF')
        require(''.join(metadata.get('course','').split()) in normalized,'Missing course in PDF')
        require(''.join(metadata.get('faculty_mentor','').split()) in normalized,'Missing mentor in PDF')
    html=(OUT/(brief+'.html')).read_text()
    require('<td>---</td>' not in html,'Broken Markdown table in PDF source')
    brief_text=(ROOT/'artifacts/pdf-review/brief/extracted.txt').read_text()
    condensed=''.join(brief_text.casefold().split())
    required_sections=['Primary objective','Dataset and evaluation criteria',
                       'Related research: approach, findings and relevance',
                       'Approach and architectural reasoning','Current findings and what they mean',
                       'Key innovations and stretch objectives','Key milestones and tentative timeline',
                       'Contribution matrix and delivery']
    for heading in required_sections:
        require(''.join(heading.casefold().split()) in condensed,'Missing required report section: '+heading)
    linked_urls={link.rstrip('/') for page in inspections['brief']['pages'] for link in page.get('links',[])}
    required_urls=['https://huggingface.co/datasets/liuqi6777/trec-news',
                   'https://arxiv.org/abs/2104.08663','https://arxiv.org/abs/2212.03533',
                   'https://aclanthology.org/2024.eacl-long.139',
                   'https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf']
    if metadata.get('repository_status') == 'created':
        required_urls.append(metadata['repository_url'])
        publication=read('artifacts/github_publication.json')
        require(publication['status']=='published' and publication['visibility']=='public' and
                publication['url']==metadata['repository_url'] and publication['owner']==metadata['github_username'] and
                publication['default_branch']=='main','Repository publication evidence mismatch')
    require(set(required_urls) <= linked_urls,'Missing clickable dataset or paper links')
    text=(ROOT/'artifacts/pdf-review/research/extracted.txt').read_text()
    queries=[json.loads(l) for l in (ROOT/'annotations/ai_study_v1/queries.jsonl').read_text().splitlines()]
    expanded_queries=[json.loads(l) for l in (ROOT/'annotations/custom40_v2/queries.all40.jsonl').read_text().splitlines()]
    require(len(expanded_queries)==40 and all(q['_id'] in text for q in expanded_queries),'Missing query appendix')
    source='82086c5dc9397700ca6682d19f1a1cace8ace5defa31f7990ca3c28314ec61a9'
    original=read('artifacts/evaluations/rrf-original-57/metrics.json')['primary']
    custom=read('artifacts/evaluations/custom20-depth20-v1/metrics.json')
    rankings={}
    for suite,qfile,names in [('original','queries.jsonl',{'bm25':'bm25-original-benchmark','dense':'dense-original','rrf':'rrf-original-k60'}),
                              ('custom','annotations/ai_study_v1/queries.jsonl',{'bm25':'bm25-custom-draft-depth1000','dense':'dense-custom-draft'})]:
        rankings[suite]={}
        for engine,name in names.items():
            path=ROOT/'artifacts/runs'/name
            # Restored-archive check of published ranks/hashes; original corpus ID coverage
            # was validated separately, not re-established from these retrieved IDs.
            rows=[json.loads(l) for l in (path/'results.jsonl').read_text().splitlines()]
            ids={h['doc_id'] for r in rows for h in r['hits']}
            rankings[suite][engine],_=load_run(path,ROOT/qfile,ids,expected_source_sha256=source)
    qids=list(original['bm25']['per_query'])
    labels=load_qrels(ROOT/'qrel.jsonl',qids)
    for engine,run in rankings['original'].items():
        require(evaluate_rankings(run,labels)==original[engine],'Original metric mismatch: '+engine)
    qlabels={q['_id']:{} for q in queries}
    assessment_rows=[json.loads(l) for l in (ROOT/'annotations/ai_study_v1/assessments.depth20.jsonl').read_text().splitlines()]
    require(len(assessment_rows)==737,'Assessment count')
    for r in assessment_rows: qlabels[r['query_id']][r['doc_id']]=r['grade']
    for mode in ['linear','exp2']:
        for engine,run in rankings['custom'].items():
            require(evaluate_rankings(run,qlabels,gain_mode=mode)==custom[mode][engine],'Custom metric mismatch')
    combined_labels=ROOT/'annotations/custom40_v2/assessments.all40.jsonl'
    protocol=read('annotations/custom40_v2/protocol.json')
    require(sha256_file(ROOT/'annotations/ai_study_v1/assessments.depth20.jsonl')==protocol['original_assessments_sha256'],
            'Frozen original judgment hash changed')
    require((ROOT/'annotations/custom40_v2/queries.all40.jsonl').read_bytes()==
            (ROOT/'annotations/ai_study_v1/queries.jsonl').read_bytes()+
            (ROOT/'annotations/custom40_v2/queries.extension20.jsonl').read_bytes(),'Frozen original query bytes changed')
    require(combined_labels.read_bytes()==(ROOT/'annotations/ai_study_v1/assessments.depth20.jsonl').read_bytes()+
            (ROOT/'annotations/custom40_v2/assessments.extension20.jsonl').read_bytes(),'Original decisions changed')
    for suffix, queryfile, label_file, evaluation, count in [
        ('custom40-extension20-v2','queries.extension20.jsonl','assessments.extension20.jsonl','custom40-extension20-depth20-v2',707),
        ('custom40-v2','queries.all40.jsonl','assessments.all40.jsonl','custom40-depth20-v2',1444)]:
        labels=[json.loads(l) for l in (ROOT/'annotations/custom40_v2'/label_file).read_text().splitlines()]
        require(len(labels)==count and len({(r['query_id'],r['doc_id']) for r in labels})==count,'Expanded assessment count')
        qs=[json.loads(l) for l in (ROOT/'annotations/custom40_v2'/queryfile).read_text().splitlines()]
        qlabels={q['_id']:{} for q in qs}
        for r in labels:
            require(r['assessor_type']=='AI' and r['full_article_read'],'Assessment disclosure changed')
            qlabels[r['query_id']][r['doc_id']]=r['grade']
        expected=read(f'artifacts/evaluations/{evaluation}/metrics.json')
        runs={}
        for engine in ['bm25','dense']:
            path=ROOT/f'artifacts/runs/{engine}-{suffix}'
            rows=[json.loads(l) for l in (path/'results.jsonl').read_text().splitlines()]
            ids={h['doc_id'] for r in rows for h in r['hits']}
            runs[engine],_=load_run(path,ROOT/'annotations/custom40_v2'/queryfile,ids,expected_source_sha256=source)
            for mode in ['linear','exp2']:
                require(evaluate_rankings(runs[engine],qlabels,gain_mode=mode)==expected[mode][engine],'Expanded metric mismatch')
        pool={(q,d) for q in qlabels for run in runs.values() for d in run[q][:20]}
        require(pool=={(r['query_id'],r['doc_id']) for r in labels},'Expanded symmetric top20 coverage')
        if count==1444:
            clusters=read('artifacts/evaluations/custom40-depth20-v2/clustered_comparison.json')
            for value in clusters.values():
                require(clustered_comparison(expected['linear']['bm25'],expected['linear']['dense'],value['families'])==value,'Family interval reproduction')
    visibility=read('annotations/ai_study_v1/evidence_visibility.depth20.json')['documents']
    articles={q['_id']:{} for q in queries}
    for row in visibility:
        articles[row['query_id']][row['doc_id']]={'contents_sha256':row['contents_sha256'],'text':'' if row['empty_body'] else '[nonempty body]'}
    quality=read('artifacts/evaluations/quality-top20-v1/metrics.json')
    choices={'baseline':(False,False),'no_empty_body':(True,False),'deduplicate':(False,True),'no_empty_body_and_deduplicate':(True,True)}
    for variant,(empty,dedup) in choices.items():
        for engine,run in rankings['custom'].items():
            rows={}
            for qid,ids in run.items():
                selected=filter_candidates(ids[:20],articles[qid],empty=empty,deduplicate=dedup)
                rows[qid]=quality_scores(selected,articles[qid],qlabels[qid])
            expected={'per_query':rows,'aggregate':{k:sum(v[k] for v in rows.values())/len(rows) for k in next(iter(rows.values()))}}
            require(expected==quality[variant][engine],'Quality metric mismatch')
    def native_counts(value):
        if not isinstance(value,dict): return 0
        if 'comparisons' in value and 'status' in value:
            require(value['status']=='passed','A native metric check failed')
            return value['comparisons']
        return sum(native_counts(v) for v in value.values())
    native_total=sum(native_counts(read(f'artifacts/evaluations/{folder}/crosscheck.json'))
                     for folder in ['original-57','rrf-original-57','custom20-depth20-v1','custom40-extension20-depth20-v2','custom40-depth20-v2'])
    require(native_total==7196,'Native comparison count mismatch')
    test=ET.parse(ROOT/'artifacts/test-results-final.xml').getroot()
    suites=list(test.iter('testsuite'))
    tests=sum(int(s.attrib.get('tests',0)) for s in suites)
    require(tests>=153 and all(int(s.attrib.get('failures',0))==int(s.attrib.get('errors',0))==0 for s in suites),'Final test run failed')
    pending=[]
    if metadata.get('repository_status') != 'created': pending.append('Create and verify the GitHub repository')
    pending += ['Confirm completed contribution: '+r['member'] for r in metadata['contributions'] if not r.get('completion_confirmed')]
    for key in ['group_number','members','course','faculty_mentor','repository_url']:
        value=metadata.get(key,'')
        if not value or 'PENDING' in value or '[' in value: pending.append('Fill '+key)
    result={'status':'passed','submission_ready':bool(metadata['contributions']) and not pending,
            'verification_mode':verification_mode,
            'remaining_metadata':pending,
            'repository_url':metadata['repository_url'],
            'repository_status':metadata['repository_status'],
            'brief_pages':4,'research_report_pages':19,'automated_tests':tests,'native_metric_comparisons':native_total,
            'expanded_queries':40,'custom_assessed_pairs':1444,'original_decisions_byte_preserved':737,
            'archive_files':manifest['file_count'],'archive_bytes':manifest['archive_bytes'],
            'numeric_reproduction':'Original primary metrics; initial20/added20/combined40 linear+exp2; both family bootstraps; four original20 quality policies. Per-query and macro values reproduce exactly.',
            'pdf_checks':'PDFKit page counts/text tied to PDF SHA256; current HTML contains no malformed table separator rows',
            'four_page_requirement_sections':required_sections,
            'verified_clickable_dataset_and_paper_links':required_urls,
            'archive_sha256':manifest['archive_sha256']}
    (OUT/'final_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
