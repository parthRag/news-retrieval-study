"""Refresh presentation/time-budget views while preserving frozen review tasks.

Never edits response CSVs or tasks.json. Exports from earlier UI versions stay
compatible because pack ID, task IDs and complete task-data hash do not change.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile

from markdown_it import MarkdownIt

from news_ir.data import sha256_file
from news_ir.human_review import digest, review_views

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT/'artifacts/assessments/human-review-round1'
    payload = json.loads((folder/'tasks.json').read_text(encoding="utf-8"))
    manifest = json.loads((folder/'manifest.json').read_text(encoding="utf-8"))
    if digest(payload['tasks']) != payload['tasks_sha256']:
        raise ValueError('Frozen task data changed')
    for name, expected in manifest['files'].items():
        if name.endswith('.csv') and sha256_file(folder/name) != expected:
            raise ValueError('A worksheet has responses; preserve it before changing packet presentation')
    original_task_bytes = (folder/'tasks.json').read_bytes()
    template = (ROOT/'src/news_ir/web/review_pack.html').read_text(encoding="utf-8")
    for filename, title, tasks in review_views(payload['tasks']):
        data = {**payload, 'view_title':title, 'tasks':tasks}
        embedded = json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        (folder/filename).write_text(template.replace('__REVIEW_DATA__',embedded), encoding="utf-8", newline="\n")
    guide = (ROOT/'reports/HUMAN_REVIEW_INSTRUCTIONS.md').read_text(encoding="utf-8")
    (folder/'README.md').write_text(guide, encoding="utf-8", newline="\n")
    rendered = MarkdownIt('commonmark').enable('table').render(guide)
    (folder/'INSTRUCTIONS.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Human review instructions</title><style>body{max-width:1050px;margin:30px auto;padding:15px;font:17px/1.6 system-ui}table{border-collapse:collapse}td,th{border:1px solid #bccbd4;padding:9px;text-align:left}code{overflow-wrap:anywhere}</style>'+rendered, encoding="utf-8", newline="\n")
    assert (folder/'tasks.json').read_bytes() == original_task_bytes
    manifest['ui_updated_at_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['response_requirements'] = {'reviewer_name':'required', 'rewrite_verdict':'required for resolved meaning checks',
        'article_grade':'required for resolved relevance judgments', 'full_article_read':'required for grades 0/1/2',
        'reason':'optional', 'evidence_quote':'optional; must be literal source text if supplied',
        'suggested_rewrite':'optional', 'uncertainty':'saved separately, not counted as resolved'}
    manifest['presentation_views'] = {name:len(tasks) for name,_,tasks in review_views(payload['tasks'])}
    manifest['assessment_blinding'] = 'Per-article task views omit engine identity, rank, score, AI grade and rationale. Manifest describes the selection protocol; prior exposure to study results may limit blinding.'
    manifest['files'] = {str(p.relative_to(folder)):sha256_file(p) for p in folder.rglob('*') if p.is_file() and p.name!='manifest.json'}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n', encoding="utf-8", newline="\n")
    archive = folder.with_suffix('.zip')
    pending = archive.with_suffix('.zip.building')
    with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED) as z:
        for path in folder.rglob('*'):
            if path.is_file():z.write(path,arcname=str(path.relative_to(folder)))
    pending.replace(archive)
    print(json.dumps({'frozen_tasks_unchanged':True,'archive_bytes':archive.stat().st_size,'views':manifest['presentation_views']},indent=2))


if __name__ == '__main__':main()
