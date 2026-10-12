from pathlib import Path
import json,datetime,time,requests,re
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'macau-v2'
p=OUT/'app.js';s=p.read_text()
if 'function renderOverview()' not in s:
    overview='''function renderOverview(){const a=plan(),cur=journey();$('#journeyCard').innerHTML=`<div class="journey-top"><span class="stage"><i></i>整天路线 · 酒店与往返完整保留</span><span class="section-label">0${S.day}</span></div><div class="journey-body"><h2 class="small">${S.day==='1'?'口岸起步，酒店收尾。':'取回行李，再回关闸。'}</h2><p class="subtitle">${a.length} 个到访步骤 · ${S.day==='1'?'寄存 → 老城 → 海边 → 回住':'退房 → 离岛 → 取行李 → 关闸'}</p></div><div class="journey-actions"><button id="journeyPrimary" class="primary">返回当前路段 ${ico('arrow')}</button><button id="journeyDetail" class="secondary">行程列表</button></div>`;$('#journeyPrimary').onclick=()=>{S.view='leg';renderAll();requestAnimationFrame(fitMap);};$('#journeyDetail').onclick=()=>showPage('plan');$('#wholeDay').classList.add('active');$('#wholeDay').setAttribute('aria-pressed','true');$('#viewBadge').textContent='整天全程';$('#viewDescription').textContent='口岸、酒店与全部往返均已显示';cardSize();}
'''
    s=s.replace('function renderCard(){if(!D)return;',overview+"function renderCard(){if(!D)return;$('#mapPage').classList.toggle('overview',S.view==='day');if(S.view==='day'){renderOverview();return;}")
    s=s.replace("$('#wholeDay').innerHTML=ico(k)","$('#wholeDay').innerHTML=ico(k)")
# Append a short label to the previously icon-only full-day toggle.
if "$('#wholeDay').append" not in s:
    s=s.replace("document.addEventListener('click',async e=>", "$('#wholeDay').append(Object.assign(document.createElement('small'),{textContent:'全程'}));document.addEventListener('click',async e=>")
s=s.replace("title='回到酒店，好好休息。'","title='回酒店，好好休息。'")
p.write_text(s)
p=OUT/'style.css';s=p.read_text()
if '/* overview refinements */' not in s:
    s+='''
/* overview refinements */
#wholeDay{gap:1px;align-content:center}#wholeDay>.ui-icon{width:20px;height:20px}#wholeDay small{display:block;font-size:9px;line-height:1.1;font-weight:500}.overview .journey-body{padding-bottom:10px}.overview .journey-body h2{font-size:20px}.overview .journey-top{padding-bottom:4px}.overview .journey-actions{padding-bottom:12px}.overview .marker b{width:27px;height:27px;font-size:10px}.overview .marker.selected b{width:30px;height:30px}.overview .marker small{font-size:9px;padding:4px 6px;top:41px}@media(max-width:374px){.journey-body h2{font-size:20px}.journey-body h2.small{font-size:19px}.journey-mainline{gap:9px}.journey-body{padding-left:17px;padding-right:17px}.journey-art,.place-symbol.journey-art{width:48px;height:48px}.primary{font-size:12px;padding-left:12px;padding-right:12px}.secondary{font-size:11px;padding-left:11px;padding-right:11px}}
'''
p.write_text(s)
p=OUT/'map.js';s=p.read_text()
s=s.replace("const label=this.zoom>15||!used.some(v=>Math.hypot(v[0]-q[0],v[1]-q[1])<58);used.push(q);", "const label=destination||S.selected===p.id||!used.some(v=>Math.abs(v[0]-q[0])<115&&Math.abs(v[1]-q[1])<44);if(label)used.push(q);")
p.write_text(s)
p=OUT/'routes.json';r=json.loads(p.read_text())
if 'hotel:paul:walk' not in r:
    url='https://routing.openstreetmap.de/routed-foot/route/v1/foot/113.54861,22.21002;113.54088,22.19757'
    for attempt in range(2):
        time.sleep(3)
        try:
            v=requests.get(url,params={'overview':'full','geometries':'geojson','steps':'true'},timeout=35).json();assert v['code']=='Ok';route=v['routes'][0];names=[]
            for leg in route['legs']:
                for step in leg['steps']:
                    n=step.get('name','')
                    if n and (not names or names[-1]!=n):names.append(n)
            r['hotel:paul:walk']={'coords':route['geometry']['coordinates'],'distance':route['distance'],'duration':route['duration'],'names':names,'source':'FOSSGIS OSRM walk','date':datetime.datetime.now(datetime.timezone.utc).date().isoformat()};break
        except Exception as e:print('Optional walking route retry failed:',str(e))
    p.write_text(json.dumps(r,ensure_ascii=False,separators=(',',':')))
report=Path('/tmp/macau-v2-qa/build.json');d=json.loads(report.read_text());d.update(routes=len(r),hotel_walk='hotel:paul:walk' in r,bytes=sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file()))
if d['hotel_walk']:d['warnings']=[]
report.write_text(json.dumps(d,ensure_ascii=False,indent=2))
