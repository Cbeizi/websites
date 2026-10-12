import os, json, pathlib, threading, http.server, functools, traceback, time
from urllib.parse import urlparse,urljoin
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path('/tmp/macau-v2-qa');OUT.mkdir(exist_ok=True)
PUBLIC=os.environ.get('MACAU_PUBLIC_URL')
report={'fallback':'Browser plugin not available; Playwright Chromium and WebKit used','public':bool(PUBLIC),'checks':[]};fatal=[]
def run(bt,name):
    server=None
    if PUBLIC:url=PUBLIC
    else:
        port=8766 if name=='chromium' else 8767
        handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT/'macau-v2'))
        server=http.server.ThreadingHTTPServer(('127.0.0.1',port),handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{port}/index.html'
    b=bt.launch();ctx=b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
    page=ctx.new_page();errors=[];external=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    checks={}
    try:
        page.goto(url,wait_until='domcontentloaded',timeout=90000)
        if page.get_by_text('Open the page',exact=False).count() and not page.locator('#journeyPrimary').count():
            page.get_by_text('Open the page',exact=False).first.click(timeout=20000)
        page.wait_for_function('window.MACAU?.ready && MACAU.version===2',timeout=90000)
        page.wait_for_function('window.macauOfflineReady === true',timeout=120000)
        page.on('request',lambda r:external.append(r.url) if urlparse(r.url).netloc!=urlparse(url).netloc else None)
        checks['title']='2.0' in page.title()
        checks['initial_route']=page.evaluate('MACAU.activeLeg().key')=='port:hotel:walk'
        assert checks['initial_route']
        assert page.locator('[data-poi="hotel"]').count()==1 and page.locator('[data-poi="port"]').count()==1
        page.wait_for_timeout(350)
        hb=page.locator('[data-poi="hotel"]').bounding_box();card=page.locator('#journeyCard').bounding_box()
        assert hb['y']+hb['height']<card['y'],(hb,card)
        page.screenshot(path=str(OUT/(name+'-01-arrival.png')))
        if name=='chromium':
            cd=ctx.new_cdp_session(page);box=page.locator('[data-poi="port"]').bounding_box();x=box['x']+22;y=box['y']+22
            before=page.evaluate('MACAU.map.center.slice()')
            cd.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
            cd.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+25,'y':y+25}]})
            cd.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
            assert page.evaluate('MACAU.map.center.slice()')!=before
            assert page.locator('#sheet').is_hidden()
            z=page.evaluate('MACAU.map.zoom')
            cd.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':100,'y':290},{'x':200,'y':290}]})
            cd.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':80,'y':290},{'x':220,'y':290}]})
            cd.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
            assert page.evaluate('MACAU.map.zoom')>z+.1
            checks['native_touch_drag_and_pinch']=True
            page.locator('#fit').tap()
        page.locator('#journeyDetail').tap()
        assert '维多利亚酒店' in page.locator('#sheetTitle').inner_text()
        assert '拱形' in page.locator('#sheetContent').inner_text()
        page.screenshot(path=str(OUT/(name+'-02-directions.png')))
        page.locator('#sheetClose').tap()
        page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.journey[1].status')=='travel'
        page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.journey[1].status')=='at'
        assert page.evaluate('MACAU.state.visits["1:hotel:1"]===true && !MACAU.state.visits["1:hotel:2"]')
        page.screenshot(path=str(OUT/(name+'-03-hotel.png')))
        page.locator('#journeyDetail').tap();page.locator('[data-task]').first.tap()
        assert page.locator('[data-task]').first.get_attribute('aria-pressed')=='true'
        page.locator('#sheetClose').tap();page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.journey[1].index')==2
        assert page.evaluate('MACAU.activeLeg().from')=='hotel'
        page.wait_for_timeout(300);page.screenshot(path=str(OUT/(name+'-04-departure.png')))
        page.locator('#journeyDetail').tap()
        if page.locator('[data-hotel-mode="walk"]').count():
            page.locator('[data-hotel-mode="walk"]').tap()
            assert page.evaluate('MACAU.activeLeg().key')=='hotel:paul:walk'
            checks['hotel_transport_toggle']=True
        page.locator('#sheetClose').tap()
        state=page.evaluate('JSON.stringify(MACAU.state.journey[1])')
        page.locator('[aria-label="预览下一步"]').tap()
        assert page.evaluate('JSON.stringify(MACAU.state.journey[1])')==state
        assert not page.evaluate('MACAU.state.visits["1:dominic:1"] || false')
        page.locator('#backCurrent').tap()
        checks['preview_does_not_complete_visits']=True
        page.locator('.bottom-nav [data-page="plan"]').tap()
        assert page.locator('.timeline-stop.hotel').count()==2
        assert page.locator('[data-visit="1:hotel:2"]').count()==1
        assert page.locator('[data-visit="1:hotel:2"]').get_attribute('class').find('checked')<0
        page.screenshot(path=str(OUT/(name+'-05-plan.png')))
        page.locator('.bottom-nav [data-page="map"]').tap()
        # Complete every remaining first-day stop through the actual main action.
        for _ in range(25):
            st=page.evaluate('({day:MACAU.state.day,...MACAU.state.journey[1]})')
            if st['day']=='1' and st['index']==10 and st['status']=='at':break
            page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.visits["1:hotel:2"]===true')
        page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.day')=='2'
        assert page.evaluate('MACAU.state.journey[2].index')==0
        assert '从酒店出发' in page.locator('#journeyCard').inner_text()
        page.screenshot(path=str(OUT/(name+'-06-day2.png')))
        page.locator('#journeyDetail').tap();assert '退房出发' in page.locator('#sheetTitle').inner_text();page.locator('#sheetClose').tap()
        page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.visits["2:hotel:1"]===true')
        # Explicitly preview and resume the luggage-pickup visit through the itinerary UI.
        page.locator('.bottom-nav [data-page="plan"]').tap()
        assert page.locator('.timeline-stop.hotel').count()==2
        page.locator('[data-visit="2:hotel:2"] button.timeline-poi').tap()
        assert '取行李' in page.locator('#sheetTitle').inner_text()
        page.locator('#hotelContinue').tap();page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.journey[2].index')==11
        page.locator('#journeyPrimary').tap();page.locator('#journeyPrimary').tap()
        assert '先取行李' in page.locator('#journeyCard').inner_text()
        page.screenshot(path=str(OUT/(name+'-07-luggage.png')))
        assert page.evaluate('MACAU.state.visits["2:hotel:2"]===true')
        page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.activeLeg().key')=='hotel:port:walk'
        page.locator('#journeyPrimary').tap();page.locator('#journeyPrimary').tap()
        assert page.evaluate('MACAU.state.journey[2].status')=='finished'
        checks['four_hotel_visits_independent']=True
        page.locator('.bottom-nav [data-page="spots"]').tap();page.locator('#search').fill('伦敦人');page.locator('#spotsList [data-open="londoner"]').tap()
        assert page.locator('.shot').count()==3
        page.locator('#poiNote').fill('离线保留：天桥与红巴士')
        page.locator('#donePoi').tap()
        page.wait_for_function('document.querySelector(".sheet-hero img").complete && document.querySelector(".sheet-hero img").naturalWidth>0')
        page.screenshot(path=str(OUT/(name+'-08-photo.png')))
        page.locator('#sheetClose').tap()
        page.locator('.bottom-nav [data-page="offline"]').tap()
        page.wait_for_function('window.macauOfflineReady===true');page.screenshot(path=str(OUT/(name+'-09-offline.png')))
        # Test a fresh tab with unavailable networking, not a stale visible page.
        if name=='chromium':ctx.set_offline(True);offline_method='browser offline mode'
        elif server:
            server.shutdown();server.server_close();server=None;offline_method='origin HTTP server shut down'
        else:
            ctx.route('**/*',lambda route:route.abort());offline_method='origin requests blocked; service-worker cache response asserted'
        page.close();page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        response=page.goto(url,wait_until='domcontentloaded',timeout=45000)
        page.wait_for_function('window.MACAU?.ready && MACAU.version===2',timeout=45000)
        assert response.from_service_worker
        assert page.evaluate('MACAU.state.notes.londoner')=='离线保留：天桥与红巴士'
        assert page.evaluate('MACAU.state.visits["1:hotel:1"] && MACAU.state.visits["1:hotel:2"] && MACAU.state.visits["2:hotel:1"] && MACAU.state.visits["2:hotel:2"]')
        page.locator('.bottom-nav [data-page="spots"]').tap();page.locator('#search').fill('伦敦人');page.locator('#spotsList [data-open="londoner"]').tap()
        page.wait_for_function('document.querySelector(".sheet-hero img").complete && document.querySelector(".sheet-hero img").naturalWidth>0')
        page.locator('#sheetClose').tap();page.locator('.bottom-nav [data-page="map"]').tap()
        page.locator('.day-tabs [data-day="1"]').tap();page.locator('#wholeDay').tap()
        page.wait_for_timeout(300);page.screenshot(path=str(OUT/(name+'-10-cold-offline.png')))
        checks['cold_offline_new_tab']=offline_method
        checks['notes_and_journey_retained']=True
        if name=='chromium':
            for w,h in [(360,740),(430,932),(1440,900)]:
                page.set_viewport_size({'width':w,'height':h});page.locator('#fit').click();page.wait_for_timeout(300)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(OUT/(name+f'-{w}x{h}.png')))
            checks['responsive_no_horizontal_overflow']=True
        assert not errors,errors
        assert not external,external
        report['checks'].append({'browser':name,'status':'pass','viewport':'390x844 @2x','url':url,'features':checks,'page_errors':errors,'app_external_requests':external})
    except Exception as e:
        fatal.append(name+': '+str(e));report['checks'].append({'browser':name,'status':'fail','error':str(e),'features':checks,'page_errors':errors})
        try:page.screenshot(path=str(OUT/(name+'-failure.png')))
        except:pass
        traceback.print_exc()
    finally:
        b.close()
        if server:server.shutdown();server.server_close()
with sync_playwright() as p:
    run(p.chromium,'chromium');run(p.webkit,'webkit')
(OUT/('public-qa.json' if PUBLIC else 'local-qa.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False),flush=True)
if fatal:raise SystemExit(1)
