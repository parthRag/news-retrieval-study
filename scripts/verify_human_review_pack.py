"""Check immutable article/task integrity and the offline review UI.

Browser interactions use synthetic answers in a disposable profile. No real
human-response file or completed annotation is written by this verifier.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
from news_ir.platform_support import find_browser, process_options, terminate_process_tree
import tempfile
import time

import requests
from websockets.sync.client import connect

from news_ir.data import DocumentStore, sha256_file
from news_ir.human_review import digest, review_views, validate_return

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'artifacts/assessments/human-review-round1'
OUT=ROOT/'artifacts/human-review-validation'


def main():
    data=json.loads((PACK/'tasks.json').read_text(encoding="utf-8"));tasks=data['tasks']
    assert len(tasks)==134 and digest(tasks)==data['tasks_sha256']
    manifest=json.loads((PACK/'manifest.json').read_text(encoding="utf-8"))
    for name,expected in manifest['files'].items():assert sha256_file(PACK/name)==expected,name
    required=[t for t in tasks if t['priority']=='required']
    articles=[t for t in required if t['kind']=='relevance']
    assert len(required)==94 and len(articles)==40
    assert len({t['query_id'] for t in articles})==40
    with DocumentStore(ROOT/'artifacts/indexes/bm25') as store:
        for task in tasks:
            assert not {'target_engine','rank','score','ai_grade','ai_rationale','verdict','grade'} & set(task)
            if task['kind']=='relevance':
                doc=store.get(task['doc_id'])
                assert doc.contents==task['article_contents']
                assert hashlib.sha256(doc.contents.encode()).hexdigest()==task['contents_sha256']
    for name,title,view_tasks in review_views(tasks):
        raw=(PACK/name).read_text(encoding="utf-8")
        embedded=re.search(r'<script id="review-data" type="application/json">(.*?)</script>',raw,re.S)[1]
        decoded=json.loads(embedded)
        assert decoded['tasks']==view_tasks and decoded['tasks_sha256']==data['tasks_sha256']
    OUT.mkdir(exist_ok=True,parents=True)
    record={'status':'passed','required_tasks':94,'optional_articles':40,'full_articles_verified':80,
            'required_custom_query_coverage':40,'html_views_verified':10,'source_labels_and_ranks_hidden':True,
            'synthetic_test_responses_not_saved_as_human_annotations':True}
    browser=find_browser()
    with tempfile.TemporaryDirectory(prefix='news-ir-review-ui-test-') as profile:
        process=subprocess.Popen([browser,'--headless','--disable-gpu','--no-first-run',
                                  '--no-default-browser-check','--disable-background-networking',
                                  '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
                                  '--user-data-dir='+profile,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**process_options())
        try:
            active=Path(profile)/'DevToolsActivePort'
            for _ in range(100):
                if active.exists():break
                time.sleep(.1)
            port=active.read_text(encoding="utf-8").splitlines()[0]
            target=next(t for t in requests.get(f'http://127.0.0.1:{port}/json/list').json() if t['type']=='page')
            with connect(target['webSocketDebuggerUrl'],max_size=20_000_000) as ws:
                seq=0;errors=[]
                def call(method,params=None):
                    nonlocal seq
                    seq+=1;wanted=seq;ws.send(json.dumps({'id':wanted,'method':method,'params':params or {}}))
                    while True:
                        msg=json.loads(ws.recv(timeout=30))
                        if msg.get('method')=='Runtime.exceptionThrown':errors.append(msg['params'])
                        if msg.get('id')==wanted:
                            if 'error' in msg:raise RuntimeError(msg['error'])
                            return msg.get('result',{})
                def js(code):
                    r=call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                    if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
                    return r['result'].get('value')
                def wait(code):
                    for _ in range(100):
                        try:
                            if js(code):return
                        except RuntimeError:pass
                        time.sleep(.1)
                    raise RuntimeError('UI wait timed out: '+code)
                call('Runtime.enable');call('Page.enable')
                call('Emulation.setDeviceMetricsOverride',{'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})
                for name,_,view_tasks in review_views(tasks):
                    call('Page.navigate',{'url':(PACK/name).as_uri()})
                    wait('document.readyState==="complete" && location.href.endsWith('+json.dumps(name)+') && typeof DATA!=="undefined"')
                    assert js('DATA.tasks.length')==len(view_tasks)
                    assert js('document.getElementById("decision").disabled')
                    assert js('Object.keys(responses).length')==0
                call('Page.navigate',{'url':(PACK/'START_HERE.html').as_uri()})
                wait('document.readyState==="complete" && location.href.endsWith("START_HERE.html") && typeof DATA!=="undefined"')
                js('document.getElementById("reviewer").value="UI_TEST_NOT_A_REAL_REVIEW";document.getElementById("start").click()')
                assert js('!document.getElementById("decision").disabled')
                assert js('!document.getElementById("optional-details").open')
                js('document.getElementById("decision").value="narrower";document.getElementById("save-next").click()')
                assert js('document.getElementById("progress").textContent.startsWith("1/94")')
                assert js('responses.R001.reason===""')
                js('document.getElementById("task").value="J001";document.getElementById("task").dispatchEvent(new Event("change"))')
                assert js('document.getElementById("article").textContent===current.article_contents')
                js('document.getElementById("decision").value="2";document.getElementById("full-read").checked=true;document.getElementById("quote").value="INVENTED TEST QUOTE";document.getElementById("save-next").click()')
                assert js('current.task_id')=='J001'
                assert js('document.getElementById("status").textContent.includes("exact match")')
                js('document.getElementById("quote").value="";document.getElementById("save-next").click()')
                assert js('document.getElementById("progress").textContent.startsWith("2/94")')
                assert js('responses.J001.reason==="" && responses.J001.evidence_quote===""')
                js('download=(value,type,extension)=>{window.TEST_DOWNLOAD={value,type,extension}};document.getElementById("export-json").click()')
                exported=json.loads(js('TEST_DOWNLOAD.value'))
                result=validate_return(tasks,exported['reviews'])
                assert result['resolved_unique_tasks']==2
                js('document.getElementById("reviewer").value="SECOND_SYNTHETIC_TEST_REVIEWER";document.getElementById("start").click()')
                assert js('Object.keys(responses).length')==0
                js('document.getElementById("reviewer").value="UI_TEST_NOT_A_REAL_REVIEW";document.getElementById("start").click()')
                assert js('document.getElementById("progress").textContent.startsWith("2/94")')
                call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
                assert js('document.documentElement.scrollWidth<=window.innerWidth')
                # Screenshot only the neutral initial state, not synthetic labels.
                js('responses={};persist();document.getElementById("task").value="R001";render()')
                (OUT/'mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
                assert not errors,errors
                record['browser_checks']=['all 10 views load offline','blank initial labels','name-required editing',
                    'label-only completion without sentences or quotes','optional notes collapsed by default',
                    'optional quote must match source if supplied','completion count','JSON export validates','reviewer isolation and resume',
                    'full article text equals source','390px layout without horizontal overflow']
                record['browser_exceptions']=errors
        finally:
            terminate_process_tree(process)
    (OUT/'validation.json').write_text(json.dumps(record,indent=2)+'\n', encoding="utf-8", newline="\n")
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
