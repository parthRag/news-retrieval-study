"""Create an explicit local code/evidence archive without corpus, model or indexes."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from news_ir.data import sha256_file

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'


def package_paths():
    files=set()
    for name in ['src','scripts','tests','configs','notebooks','reports','annotations']:
        for path in (ROOT/name).rglob('*'):
            if path.is_file() and not path.is_symlink() and not any(p in {'__pycache__','.DS_Store'} for p in path.parts):
                files.add(path)
    for name in ['README.md','DELIVERABLES.md','CONTRIBUTING.md','PROJECT_BLUEPRINT.md','pyproject.toml','requirements-lock.txt','.gitignore','queries.jsonl','qrel.jsonl','job_summary.json']:
        files.add(ROOT/name)
    for name in ['original-57','rrf-original-57','custom20-depth20-v1','custom20-top5-v1','quality-top20-v1',
                 'custom40-extension20-depth20-v2','custom40-depth20-v2']:
        files.update(p for p in (ROOT/'artifacts/evaluations'/name).rglob('*') if p.is_file())
    for name in ['bm25-original-benchmark','dense-original','rrf-original-k60','bm25-custom-draft-depth1000','dense-custom-draft',
                 'bm25-custom40-extension20-v2','dense-custom40-extension20-v2','bm25-custom40-v2','dense-custom40-v2']:
        files.update((ROOT/'artifacts/runs'/name/f) for f in ['manifest.json','run.trec','results.jsonl','queries.jsonl'])
    for name in ['test-results-final.xml','custom20_depth20_validation.json','original_benchmark_provenance.json',
                 'custom40_extension_validation.json','custom40_depth20_validation.json','github_publication.json']:
        files.add(ROOT/'artifacts'/name)
    for name in ['protocol.json','pool.provenance.jsonl','queries.jsonl']:
        files.add(ROOT/'artifacts/assessments/custom40-extension20-v2'/name)
        files.add(ROOT/'artifacts/assessments/custom40-v2'/name)
    for name in ['demo-validation','demo-validation-recheck','demo-validation-expanded40','demo-validation-assessment-plan']:
        files.update(p for p in (ROOT/'artifacts'/name).iterdir() if p.is_file())
    for name in ['brief','research']:
        files.update(ROOT/f'artifacts/pdf-review/{name}'/f for f in ['inspection.json','extracted.txt'])
    files.update(p for p in OUT.iterdir() if p.is_file() and p.suffix in {'.pdf','.md','.html','.svg','.csv','.json'}
                 and p.name not in {'release_manifest.json','final_validation.json'})
    for p in files:
        if not p.is_file() or p.is_symlink(): raise ValueError(f'Missing or unsafe package input: {p}')
    return sorted(files)


def main():
    files=package_paths()
    hashes={str(p.relative_to(ROOT)):sha256_file(p) for p in files}
    inner={'files':hashes,'excluded':'corpus, full article packets, model, indexes, encodings, environment, caches',
           'scope':'Local review/reproducibility archive; live demo requires restored local data dependencies. Group metadata is filled; public repository publication and individual contribution confirmation are tracked in configs/submission.json.'}
    target=OUT/'NewsIR_Reproducibility_Package.zip'
    with tempfile.NamedTemporaryFile(dir=OUT,suffix='.building',delete=False) as temp:
        temporary=Path(temp.name)
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for path in files:
                name=str(path.relative_to(ROOT))
                data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=hashes[name]: raise ValueError('Input changed while packaging: '+name)
                archive.writestr(name,data)
            archive.writestr('PACKAGE_MANIFEST.json',json.dumps(inner,indent=2)+'\n')
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True);raise
    manifest={**inner,'archive':target.name,'archive_bytes':target.stat().st_size,'archive_sha256':sha256_file(target),
              'file_count':len(files),'metadata':json.loads((ROOT/'configs/submission.json').read_text())}
    (OUT/'release_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['archive','archive_bytes','archive_sha256','file_count']},indent=2))

if __name__=='__main__': main()
