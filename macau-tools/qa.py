import json, os, pathlib, threading, http.server, functools, sys, time, traceback, re, subprocess
from urllib.parse import urlparse
import requests
from playwright.sync_api import sync_playwright
OUT=pathlib.Path('/tmp/macau-qa');OUT.mkdir(exist_ok=True)
URL=os.environ.get('MACAU_TEST_URL','http://127.0.0.1:8765/index.html')
PUBLIC=bool(os.environ.get('MACAU_TEST_URL'))
if not PUBLIC:
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory='/tmp/macau-site')
    server=http.server.ThreadingHTTPServer(('127.0.0.1',8765),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
report={'url':URL,'fallback':'Browser plugin not available; Playwright Chromium and WebKit used','webkit_outage_method':'Origin server stopped locally; outbound HTTP/HTTPS rejected by runner firewall for public test. Avoids known setOffline WebKit bug microsoft/playwright#42775.','checks':[]};fatal=[]
def shot(page,name):
    page.wait_for_timeout(250)
    page.screenshot(path=str(OUT/name),animations='disabled')
def enter(page,name):
    page.goto(URL,wait_until='domcontentloaded',timeout=60000)
    page.wait_for_timeout(500)
    if not page.locator('#map').count() and 'githack.com' in URL:
        (OUT/(name+'-hosting-confirmation.html')).write_text(page.content())
        shot(page,name+'-hosting-confirmation.png')
        choices=page.get_by_role('button',name=re.compile('continue|proceed|confirm|understand|visit|open',re.I))
        if choices.count():choices.first.click()
        else:
            choices=page.get_by_role('link',name=re.compile('continue|proceed|confirm|understand|visit|open',re.I))
            if choices.count():choices.first.click()
    page.wait_for_function('window.MACAU?.ready',timeout=60000)
    page.wait_for_function('window.macauOfflineReady === true',timeout=120000)
def run(browser_type,name):
    browser=browser_type.launch();ctx=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
    page=ctx.new_page();errors=[];external=[];firewalls=[];outage='Chromium offline emulation';negative=False
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:external.append(r.url) if urlparse(r.url).netloc!=urlparse(URL).netloc else None)
    try:
        enter(page,name)
        counts=page.evaluate('({roads:MACAU.roads,routes:MACAU.routes,pois:MACAU.data.pois.length})');assert counts['roads']>1000 and counts['pois']==20
        shot(page,name+'-map.png')
        if name=='chromium':
            cd=ctx.new_cdp_session(page);box=page.locator('[data-poi="paul"]').bounding_box();x=box['x']+22;y=box['y']+22;before=page.evaluate('MACAU.map.center.slice()')
            cd.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]});cd.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+32,'y':y+25}]});cd.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(150)
            assert page.evaluate('MACAU.map.center.slice()')!=before;assert page.locator('#sheet').is_hidden()
            z=page.evaluate('MACAU.map.zoom')
            cd.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':140,'y':300},{'x':240,'y':300}]});cd.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':110,'y':300},{'x':270,'y':300}]});cd.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});assert page.evaluate('MACAU.map.zoom')>z+.2
            page.locator('#fit').tap()
        page.locator('[data-page="plan"]').tap();page.locator('#planList [data-open="paul"]').tap();assert '大三巴' in page.locator('#sheetTitle').inner_text();page.locator('#poiNote').fill('离线测试笔记');page.locator('#donePoi').tap();page.locator('#sheetClose').tap()
        page.locator('.plan-days [data-day="2"]').tap();page.locator('[data-plan="night"]').tap();assert page.evaluate('MACAU.state.variant')=='night';page.locator('[data-page="spots"]').tap();page.locator('#search').fill('伦敦人');assert page.locator('#spotsList .spot-card').count()==1;page.locator('#spotsList [data-open="londoner"]').tap();assert page.locator('.shot').count()==3;shot(page,name+'-detail.png');page.locator('#sheetClose').tap()
        page.locator('[data-page="offline"]').tap();page.wait_for_function('window.macauOfflineReady === true');shot(page,name+'-offline.png')
        if name=='webkit':
            if PUBLIC:
                for binary in ['iptables','ip6tables']:
                    for port in ['443','80']:
                        cmd=['sudo',binary,'-I','OUTPUT','-p','tcp','--dport',port,'-j','REJECT']
                        subprocess.run(cmd,check=True);firewalls.append(cmd)
                outage='Actual runner outbound HTTP/HTTPS firewall rejection'
            else:
                server.shutdown();server.server_close();outage='Origin HTTP server stopped'
            try:requests.get(URL,timeout=4)
            except requests.RequestException:negative=True
            assert negative,'Negative control reached origin despite outage'
        else:ctx.set_offline(True)
        page.close();page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));response=page.goto(URL,wait_until='domcontentloaded',timeout=30000);page.wait_for_function('window.MACAU?.ready',timeout=30000);assert page.evaluate('MACAU.state.done.paul === true');assert page.evaluate('MACAU.state.notes.paul')=='离线测试笔记';assert response.from_service_worker
        page.locator('.days [data-day="2"]').tap();shot(page,name+'-cold-offline.png')
        page.locator('[data-page="spots"]').tap();page.locator('#search').fill('伦敦人');page.locator('#spotsList [data-open="londoner"]').tap();page.wait_for_function('document.querySelector(".sheet-hero img").complete && document.querySelector(".sheet-hero img").naturalWidth>0');shot(page,name+'-offline-detail.png');page.locator('#sheetClose').tap();page.locator('[data-page="map"]').tap()
        assert not errors,errors
        report['checks'].append({'browser':name,'status':'pass','counts':counts,'phone':'390x844 @2x','cold_offline_reopen':True,'outage_method':outage,'negative_control_network_blocked':negative if name=='webkit' else 'Browser offline flag','notes_retained':True,'external_requests':external,'page_errors':errors})
        if name=='chromium':
            ctx.set_offline(False)
            for w,h in [(360,780),(430,932),(1440,900)]:
                page.set_viewport_size({'width':w,'height':h});page.locator('#fit').click();page.wait_for_timeout(200);assert page.evaluate('document.documentElement.scrollWidth <= innerWidth');shot(page,name+f'-{w}x{h}.png')
    except Exception as e:
        fatal.append(name+': '+str(e));report['checks'].append({'browser':name,'status':'fail','error':str(e),'page_errors':errors});shot(page,name+'-failure.png');(OUT/(name+'-failure.html')).write_text(page.content());traceback.print_exc()
    finally:
        for cmd in reversed(firewalls):
            cmd[2]='-D';subprocess.run(cmd,check=False)
        browser.close()
with sync_playwright() as p:
    run(p.chromium,'chromium');run(p.webkit,'webkit')
(OUT/'qa-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
if fatal:sys.exit(1)
