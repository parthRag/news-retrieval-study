"""Optional real-browser integration check; requires a running demo and Chromium.

Uses an isolated temporary profile and runs one real CPU query. Existing output
folders are refused. requests/websockets are available in requirements-lock.txt.
"""
import argparse
import base64, json, os, pathlib, signal, subprocess, tempfile, time
import requests
from websockets.sync.client import connect
ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--browser', default='/Applications/Brave Browser.app/Contents/MacOS/Brave Browser')
parser.add_argument('--skip-live', action='store_true', help='Keep the prior live smoke result; check saved views and UI only')
parser.add_argument('--port', type=int, default=8765)
parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'artifacts/demo-validation-recheck')
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=False)
BASE = f'http://127.0.0.1:{args.port}'
report = {'base_url': BASE, 'saved_queries_checked': 0, 'article_endpoints_checked': 0}
catalog = requests.get(BASE+'/api/catalog').json()
assert catalog['custom_assessed_pairs']==(1444 if 'expanded' in catalog['suites'] else 737)
report['distinct_queries_checked']=catalog['evaluated_query_count']
for suite, queries in catalog['suites'].items():
    for query in queries:
        r=requests.get(BASE+'/api/replay', params={'suite':suite, 'qid':query['_id'], 'k':20})
        r.raise_for_status(); data=r.json()
        assert len(data['engines']) == (3 if suite=='original' else 2)
        for engine, result in data['engines'].items():
            assert len(result['hits'])==20 and result['metrics'] is not None
            if suite in {'custom','expanded'}: assert all(h['assessment'] is not None for h in result['hits'])
        hit=data['engines']['dense']['hits'][0]
        doc=requests.get(BASE+'/api/document',params={'suite':suite,'qid':query['_id'],'id':hit['doc_id']}).json()
        assert doc['doc_id']==hit['doc_id']
        assert isinstance(doc['contents'],str)
        report['article_endpoints_checked']+=1
        report['saved_queries_checked']+=1
print(f"Verified all {report['saved_queries_checked']} saved queries and article endpoints",flush=True)
profile=tempfile.TemporaryDirectory(prefix='news-ir-browser-')
process=subprocess.Popen([args.browser, '--headless','--disable-gpu','--no-first-run','--no-default-browser-check', '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0', '--user-data-dir='+profile.name, BASE], stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
try:
    active=pathlib.Path(profile.name)/'DevToolsActivePort'
    for _ in range(100):
        if active.exists(): break
        time.sleep(.2)
    port=active.read_text().splitlines()[0]
    targets=requests.get('http://127.0.0.1:'+port+'/json/list').json()
    target=next(t for t in targets if t['type']=='page')
    ws=connect(target['webSocketDebuggerUrl'],max_size=20_000_000,legacy=True)
    seq=0; errors=[]
    def call(method,params=None):
        global seq
        seq+=1; current=seq; ws.send(json.dumps({'id':current,'method':method,'params':params or {}}))
        while True:
            msg=json.loads(ws.recv(timeout=120))
            if msg.get('method')=='Runtime.exceptionThrown': errors.append(msg['params'])
            if msg.get('id')==current:
                if 'error' in msg: raise RuntimeError(msg['error'])
                return msg.get('result',{})
    def js(expression):
        result=call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
        if 'exceptionDetails' in result: raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')
    def wait(expression):
        for _ in range(200):
            if js(expression): return
            time.sleep(.1)
        raise RuntimeError('UI wait timed out: '+expression)
    call('Runtime.enable'); call('Page.enable')
    call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1050,'deviceScaleFactor':1,'mobile':False})
    wait("document.querySelectorAll('.engine').length===2 && document.querySelectorAll('#query option').length==="+str(40 if 'expanded' in catalog['suites'] else 20))
    assert js("!document.getElementById('assessment-status').hidden && document.getElementById('assessment-status').textContent.includes('AI judgments') && document.getElementById('assessment-status').textContent.includes('Human review is planned')")
    js("document.getElementById('query').value='H02'; document.getElementById('saved-form').requestSubmit()")
    wait("document.getElementById('result-source').textContent.startsWith('H02')")
    assert js("document.querySelectorAll('.card').length")==10
    shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
    (OUT/'demo-desktop.png').write_bytes(base64.b64decode(shot['data']))
    js("document.getElementById('results').scrollIntoView()")
    shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
    (OUT/'demo-comparison.png').write_bytes(base64.b64decode(shot['data']))
    js("document.querySelector('.card button').click()")
    wait("document.getElementById('article').open")
    assert js("article.assessment.assessor_type==='AI' && document.getElementById('assessment').textContent.includes('AI')")
    assert js("document.querySelectorAll('#article-body mark').length")>0
    assert js("document.getElementById('article-body').textContent===article.contents")
    assert js("Array.from(document.querySelectorAll('#article-body mark')).every(m=>article.assessment.evidence.some(e=>e.quote===m.textContent))")
    js("document.getElementById('prefix-only').click()")
    assert js("Array.from(document.getElementById('article-body').textContent).length===article.e5_input_end")
    shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
    (OUT/'demo-evidence.png').write_bytes(base64.b64decode(shot['data']))
    js("document.getElementById('close-article').click();document.getElementById('suite').value='original';document.getElementById('suite').dispatchEvent(new Event('change'))")
    wait("document.querySelectorAll('.engine').length===3")
    assert js("document.getElementById('assessment-status').hidden"), 'Original qrels must not be labeled as preliminary custom judgments'
    js("document.getElementById('depth').value='20';document.getElementById('depth').dispatchEvent(new Event('change'))")
    wait("document.querySelectorAll('.card').length===60")
    call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
    assert js("document.documentElement.scrollWidth<=window.innerWidth"), 'mobile page overflow'
    shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
    (OUT/'demo-mobile.png').write_bytes(base64.b64decode(shot['data']))
    call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1050,'deviceScaleFactor':1,'mobile':False})
    if not args.skip_live:
        js("document.getElementById('live-tab').click();document.getElementById('live-query').value='jaguar animal habitat conservation';document.getElementById('live-form').requestSubmit()")
        start=time.monotonic()
        while time.monotonic()-start<650:
            status=js("document.getElementById('status').textContent")
            if 'Live search complete' in status: break
            if js("document.getElementById('status').className==='error'"): raise RuntimeError(status)
            print(status,flush=True);time.sleep(10)
        else: raise RuntimeError('live timeout')
        assert js("current.mode==='live' && Object.keys(current.engines).length===3")
        assert js("Object.values(current.engines).every(e=>e.metrics===null && e.hits.every(h=>h.assessment===null))")
        assert js("document.querySelectorAll('.metric-row').length===0")
        report['live_elapsed_seconds']=time.monotonic()-start
        report['live_result']=js("({query:current.query, engines:Object.fromEntries(Object.entries(current.engines).map(([e,r])=>[e,{top5:r.hits.slice(0,5).map(h=>h.doc_id),engine_search_ms:r.engine_search_ms,elapsed_ms_with_startup:r.elapsed_ms_with_startup}]))})")
    report['browser_exceptions']=errors
    assert not errors
    report['ui_checks']=['two-engine custom comparison','evidence highlights equal literal quotes','full body equals source','512-token retained text toggle','three-engine original comparison','20 results per engine','390px responsive layout without horizontal overflow','live form retrieves BM25/E5/RRF with no inferred grades or metrics']
    if args.skip_live:
        report['ui_checks'] = [c for c in report['ui_checks'] if not c.startswith('live form')]
    report['live_test_this_run']=not args.skip_live
    report['assessment_status_checks']=['one context notice for preliminary full-article AI judgments and planned human review', 'assessor provenance retained in article details', 'custom notice hidden for supplied-qrels benchmark']
    report['status']='passed'
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    ws.close()
finally:
    os.killpg(process.pid,signal.SIGTERM)
    try: process.wait(timeout=10)
    except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL);process.wait()
    profile.cleanup()
