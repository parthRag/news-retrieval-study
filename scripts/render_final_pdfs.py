"""Render generated local HTML to PDFs using an isolated Chromium profile.

No website is published. Use --browser to select an installed Chromium binary.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from urllib.request import urlopen
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',default='/Applications/Brave Browser.app/Contents/MacOS/Brave Browser')
    args=parser.parse_args()
    metadata=json.loads((ROOT/'configs/submission.json').read_text())
    stems=[metadata['group_number']+'_'+metadata['short_title'],'RESEARCH_REPORT']
    with tempfile.TemporaryDirectory(prefix='news-ir-pdf-') as profile:
        process=subprocess.Popen([args.browser,'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                                  '--disable-background-networking','--remote-debugging-address=127.0.0.1',
                                  '--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            portfile=Path(profile)/'DevToolsActivePort'
            for _ in range(100):
                if portfile.exists(): break
                time.sleep(.2)
            port=portfile.read_text().splitlines()[0]
            with urlopen(f'http://127.0.0.1:{port}/json/list') as response:
                target=next(t for t in json.load(response) if t['type']=='page')
            with connect(target['webSocketDebuggerUrl'],max_size=50_000_000) as ws:
                seq=0
                def call(method,params=None):
                    nonlocal seq
                    seq+=1; current=seq
                    ws.send(json.dumps({'id':current,'method':method,'params':params or {}}))
                    while True:
                        message=json.loads(ws.recv(timeout=120))
                        if message.get('id')==current:
                            if 'error' in message: raise RuntimeError(message['error'])
                            return message.get('result',{})
                def js(expression):
                    result=call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
                    if 'exceptionDetails' in result: raise RuntimeError(result['exceptionDetails'])
                    return result['result'].get('value')
                call('Page.enable')
                call('Emulation.setEmulatedMedia',{'media':'print'})
                call('Emulation.setDeviceMetricsOverride',{'width':673,'height':1005,'deviceScaleFactor':1,'mobile':False})
                audits={}
                for stem in stems:
                    source=ROOT/'deliverables'/(stem+'.html')
                    call('Page.navigate',{'url':source.as_uri()})
                    for _ in range(100):
                        if js("document.readyState==='complete'"): break
                        time.sleep(.1)
                    js('document.fonts.ready.then(()=>true)')
                    audit=js("({sections:[...document.querySelectorAll('section.page')].map((p,i)=>({page:i+1,height:p.getBoundingClientRect().height,width:p.getBoundingClientRect().width})),brokenImages:[...document.images].filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src),horizontalOverflow:document.documentElement.scrollWidth>window.innerWidth})")
                    if audit['brokenImages'] or audit['horizontalOverflow']: raise RuntimeError(audit)
                    footer='<div style="width:100%;font-family:Arial;font-size:8px;color:#687986;padding:0 16mm;text-align:right">News IR · '+('Submission brief' if stem!='RESEARCH_REPORT' else 'Research report')+' · <span class="pageNumber"></span> / <span class="totalPages"></span></div>'
                    pdf=call('Page.printToPDF',{'printBackground':True,'preferCSSPageSize':True,'displayHeaderFooter':True,
                                               'headerTemplate':'<span></span>','footerTemplate':footer})
                    output=source.with_suffix('.pdf')
                    output.write_bytes(base64.b64decode(pdf['data']))
                    audits[stem]=audit
                    print(f'Rendered {output.name} ({output.stat().st_size:,} bytes)',flush=True)
                (ROOT/'deliverables/pdf_layout_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
        finally:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL); process.wait()

if __name__=='__main__':main()
