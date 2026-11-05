"""Build an offline review pack with full articles and blank response fields."""
import csv
import html
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import zipfile

from news_ir.data import DocumentStore, sha256_file
from news_ir.evaluation import load_run
from news_ir.human_review import digest, select_article_pairs, review_views

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'artifacts/assessments/human-review-round1'


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_csv(path, columns, rows):
    # Metadata is quoted and formula-like source strings are neutralized for Excel.
    def safe(value):
        value = str(value)
        return "'" + value if value.startswith(('=', '+', '-', '@')) else value
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(columns)
        for row in rows:
            writer.writerow([safe(row.get(k, '')) for k in columns])


def main():
    if TARGET.exists():
        raise FileExistsError('Review pack exists; preserve it and use a new round/version')
    tasks, source_hashes = [], {}
    core_path = ROOT / 'annotations/core18_v1/queries.jsonl'
    core = [r for r in read_jsonl(core_path) if r['variant'] == 'rewrite']
    for i, row in enumerate(core):
        tasks.append({'task_id': f'R{i+1:03}', 'kind': 'rewrite', 'dataset': 'Core 2018 news',
                      'priority': 'required', 'batch': 'ABCD'[i % 4], 'topic_id': row['topic_id'],
                      'original': row['original_title'], 'rewrite': row['text'],
                      'description': row['description'], 'narrative': row['narrative']})
    source_hashes[str(core_path.relative_to(ROOT))] = sha256_file(core_path)
    covid_path = ROOT / 'studies/hamsini_robustness/queries/variants/trec_covid_rewrites.csv'
    raw = covid_path.read_text(encoding='cp1252')
    import io
    rows = {r['qid']: r for r in csv.DictReader(io.StringIO(raw))}
    for i, (qid, variant) in enumerate([('5', 'a'), ('5', 'b'), ('12', 'a'), ('12', 'b')]):
        row = rows[qid]
        tasks.append({'task_id': f'H{i+1:03}', 'kind': 'rewrite', 'dataset': 'TREC-COVID targeted check',
                      'priority': 'required', 'batch': 'ABCD'[i], 'topic_id': qid,
                      'original': row['original'], 'rewrite': row['rewrite_' + variant],
                      'description': row['question'], 'narrative': row['narrative'], 'variant': variant})
    source_hashes[str(covid_path.relative_to(ROOT))] = sha256_file(covid_path)
    queries_path = ROOT / 'annotations/custom40_v2/queries.all40.jsonl'
    queries = read_jsonl(queries_path)
    qlookup = {q['_id']: q for q in queries}
    source_hashes[str(queries_path.relative_to(ROOT))] = sha256_file(queries_path)
    provenance = []
    with DocumentStore(ROOT / 'artifacts/indexes/bm25') as store:
        eligible = {r[0] for r in store._db.execute('SELECT doc_id FROM documents WHERE eligible=1')}
        source_sha = store.manifest['source']['sha256']
        rankings = {}
        for engine in ['bm25', 'dense']:
            folder = ROOT / f'artifacts/runs/{engine}-custom40-v2'
            rankings[engine], _ = load_run(folder, queries_path, eligible, expected_source_sha256=source_sha)
            for name in ['manifest.json', 'run.trec', 'results.jsonl', 'queries.jsonl']:
                source_hashes[str((folder/name).relative_to(ROOT))] = sha256_file(folder/name)
        choices = select_article_pairs(queries, rankings)
        # Keep waves distinct; no existing AI grade or rationale enters selection or payload.
        for wave in [1, 2]:
            for i, query in enumerate(queries):
                choice = next(r for r in choices if r['query_id'] == query['_id'] and r['wave'] == wave)
                doc = store.get(choice['doc_id'])
                if doc is None:
                    raise ValueError('Missing selected article')
                task_id = f'J{(wave-1)*40+i+1:03}'
                task = {'task_id': task_id, 'kind': 'relevance', 'dataset': 'Custom40 news audit',
                        'priority': 'required' if wave == 1 else 'optional', 'wave': wave,
                        'batch': 'ABCD'[i % 4], 'query_id': query['_id'], 'query': query['text'],
                        'category': query['category'], 'relevant_if': query['relevant_if'],
                        'exclude_if': query['exclude_if'],
                        **{k: query[k] for k in ['grade_0', 'grade_1', 'grade_2']},
                        'doc_id': doc.doc_id, 'title': doc.title, 'article_contents': doc.contents,
                        'contents_sha256': __import__('hashlib').sha256(doc.contents.encode()).hexdigest(),
                        'word_count': len(doc.contents.split())}
                tasks.append(task)
                provenance.append(dict(choice, task_id=task_id,
                                       source_rank=rankings[choice['target_engine']][query['_id']].index(doc.doc_id)+1))
    assert len(core) == 50 and len(queries) == 40 and len(tasks) == 134
    required = [t for t in tasks if t['priority'] == 'required']
    extra = [t for t in tasks if t['priority'] == 'optional']
    article_required = [t for t in required if t['kind'] == 'relevance']
    word_count = sum(t['word_count'] for t in article_required)
    payload = {'schema': 'news_ir_human_review_v1', 'pack_id': 'news-ir-human-round1-20261102',
               'tasks_sha256': digest(tasks), 'deadline_note': 'Requested review by 3 November 2026',
               'required_task_count': len(required), 'optional_task_count': len(extra), 'tasks': tasks}
    TARGET.parent.mkdir(exist_ok=True, parents=True)
    working = Path(tempfile.mkdtemp(prefix='.human-review-building-', dir=TARGET.parent))
    try:
        (working/'tasks.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding="utf-8", newline="\n")
        template = (ROOT/'src/news_ir/web/review_pack.html').read_text(encoding="utf-8")
        views = review_views(tasks)
        for filename, title, selected in views:
            data = {**payload, 'view_title': title, 'tasks': selected}
            embedded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            (working/filename).write_text(template.replace('__REVIEW_DATA__', embedded), encoding="utf-8", newline="\n")
        (working/'articles').mkdir()
        for task in tasks:
            if task['kind'] != 'relevance':
                continue
            article = '<!doctype html><meta charset="utf-8"><title>'+task['task_id']+'</title><style>body{max-width:850px;margin:35px auto;padding:0 20px;font:18px/1.6 Georgia}pre{white-space:pre-wrap;font:inherit}</style>'
            article += '<h1>'+html.escape(task['task_id']+' · '+task['title'])+'</h1>'
            for heading, text in [('Query', task['query']), ('Relevant if', task['relevant_if']), ('Exclude', task['exclude_if'])]:
                article += '<h2>'+heading+'</h2><p>'+html.escape(text)+'</p>'
            article += '<h2>Full available article</h2><pre>'+html.escape(task['article_contents'])+'</pre>'
            (working/'articles'/f"{task['task_id']}.html").write_text(article, encoding="utf-8", newline="\n")
        blank = {'reviewer':'','verdict':'','reason':'','suggested_rewrite':'','notes':'','grade':'','evidence_quote':'','full_article_read':''}
        rewrite_columns = ['task_id','batch','topic_id','original','rewrite','description','narrative','reviewer','verdict','reason','suggested_rewrite','notes']
        for name, selected in [('A_news_rewrites.csv',required[:50]),('B_covid_targeted.csv',required[50:54])]:
            write_csv(working/name,rewrite_columns,[{**t,**blank} for t in selected])
        article_columns = ['task_id','batch','query_id','category','query','relevant_if','exclude_if','grade_0','grade_1','grade_2','title','doc_id','article_file','reviewer','grade','reason','evidence_quote','full_article_read','notes']
        for name, selected in [('C_articles_required.csv',article_required),('OPTIONAL_articles_extra.csv',extra)]:
            write_csv(working/name,article_columns,[{**t,**blank,'article_file':f"articles/{t['task_id']}.html"} for t in selected])
        instructions = (ROOT/'reports/HUMAN_REVIEW_INSTRUCTIONS.md').read_text(encoding="utf-8")
        (working/'README.md').write_text(instructions, encoding="utf-8", newline="\n")
        from markdown_it import MarkdownIt
        guide = MarkdownIt('commonmark').enable('table').render(instructions)
        (working/'INSTRUCTIONS.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Human review instructions</title><style>body{max-width:1050px;margin:30px auto;padding:15px;font:17px/1.6 system-ui}table{border-collapse:collapse}td,th{border:1px solid #bccbd4;padding:9px;text-align:left}code{overflow-wrap:anywhere}</style>'+guide, encoding="utf-8", newline="\n")
        manifest = {'schema':payload['schema'],'pack_id':payload['pack_id'],'tasks_sha256':payload['tasks_sha256'],
                    'created_at_utc':datetime.now(timezone.utc).isoformat(),
                    'required_tasks':len(required),'required_rewrite_checks':54,'required_articles':40,
                    'optional_articles':40,'required_article_words':word_count,
                    'required_article_categories':dict(Counter(t['category'] for t in article_required)),
                    'required_batches':dict(Counter(t['batch'] for t in required)),
                    'selection':'Seeded per-query top-five draw, counterbalanced five queries per engine per category; optional wave uses the other engine and another document. No AI labels used in selection.',
                    'seed':'news-ir-human-round1-20261102','assessment_blinding':'Reviewer files omit engine, rank, retrieval score, AI grade and AI rationale. Prior exposure to study results may limit blinding.',
                    'interpretation':'40-pair top-five audit if required tasks complete; 80 if optional pass also complete. Neither completes human judgments for all 1,444 pooled pairs or licenses full human-reviewed custom40 MAP/nDCG.',
                    'corpus_sha256':source_sha,'source_files':source_hashes,
                    'workload_note':'Reading-time estimates must add decision/note time; pace varies by article and assessor.',
                    'response_requirements':{'reviewer_name':'required','rewrite_verdict':'required for resolved meaning checks',
                        'article_grade':'required for resolved relevance judgments','full_article_read':'required for grades 0/1/2',
                        'reason':'optional','evidence_quote':'optional; literal if supplied','suggested_rewrite':'optional'},
                    'files':{str(p.relative_to(working)):sha256_file(p) for p in working.rglob('*') if p.is_file()}}
        (working/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n', encoding="utf-8", newline="\n")
        working.rename(TARGET)
        # Keep engine-origin mapping outside the portable reviewer package.
        (TARGET.parent/'human-review-round1.admin.json').write_text(json.dumps({'pack_id':payload['pack_id'],'selection':provenance},indent=2)+'\n', encoding="utf-8", newline="\n")
        archive = TARGET.with_suffix('.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for path in TARGET.rglob('*'):
                if path.is_file():z.write(path,arcname=str(path.relative_to(TARGET)))
        print(json.dumps({'folder':str(TARGET),'archive':str(archive),'required_tasks':len(required),'required_articles':40,'required_article_words':word_count,'optional_articles':40,'batches':manifest['required_batches']},indent=2))
    except BaseException:
        shutil.rmtree(working,ignore_errors=True)
        raise


if __name__ == '__main__':main()
