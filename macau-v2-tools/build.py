from pathlib import Path
import json, shutil, datetime, requests
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'macau-mobile'; OUT=ROOT/'macau-v2'
assert (OUT/'index.html').exists() and (OUT/'app.js').exists()
for name in ['map.json','routes.json','trip.json','offline.js','sw.js','map.js','manifest.json','icon.svg','icon-192.png','icon-512.png','LICENSE-MAP.txt']:
    shutil.copy2(OLD/name,OUT/name)
shutil.copytree(OLD/'img',OUT/'img',dirs_exist_ok=True)
def replace_once(s,a,b):
    assert a in s,a[:100]
    return s.replace(a,b)
p=OUT/'map.js';s=p.read_text()
a=s.index('fit(ps){');b=s.index('\nbind(){',a)
s=s[:a]+'''fit(ps){if(!ps.length||!this.w)return;const vs=ps.map(p=>world([p.lon,p.lat])),xs=vs.map(v=>v[0]),ys=vs.map(v=>v[1]),x1=Math.min(...xs),x2=Math.max(...xs),y1=Math.min(...ys),y2=Math.max(...ys);const card=document.querySelector('#journeyCard')?.offsetHeight||240;const top=this.w<780?126:136,bottom=this.w<780?card+112:110,left=this.w<780?47:455,right=this.w<780?73:110,usableH=Math.max(100,this.h-top-bottom),usableW=Math.max(140,this.w-left-right);const s=Math.min(usableW/Math.max(x2-x1,65),usableH/Math.max(y2-y1,65));this.zoom=Math.max(12.2,Math.min(18.4,18+Math.log2(s)));const scale=2**(this.zoom-18);this.center=[(x1+x2)/2+(right-left)/(2*scale),(y1+y2)/2+(bottom-top)/(2*scale)];this.bound();this.draw();}'''+s[b:]
s=replace_once(s,"if(!l.data||(!this.S.returns&&l.transfer))continue;","if(!l.data)continue;")
s=s.replace("'#db7847'","'#d47749'").replace("'#526fc0'","'#557e98'").replace('c.globalAlpha=l.transfer?.62:1','c.globalAlpha=1')
s=s.replace("'#e4eeec'","'#deece7'").replace("'#f3f4ed'","'#f6f7f0'").replace("'#e2e5dd'","'#e6e9df'").replace("'#d8ded6'","'#e0e4da'")
s=replace_once(s,'const occupied=[];','const occupied=[],seenNames=new Set();')
s=replace_once(s,"for(const o of roads){if(!o.n||o.p.length<2||(!o.major&&this.zoom<16))continue;const q=this.screen(o.p[Math.floor(o.p.length/2)]),width=c.measureText(o.n).width;",r"for(const o of roads){if(!o.n||o.p.length<2||(!o.major&&this.zoom<16))continue;const label=o.n.replace(/\s+(Rua|Estrada|Avenida|Ponte|Calçada|Travessa|Largo|Rotunda|Praça|Alameda|Beco|Pátio)\b[\s\S]*/,'').replace(/\s*[（(].*/, '');if(seenNames.has(label))continue;const q=this.screen(o.p[Math.floor(o.p.length/2)]),width=c.measureText(label).width;")
s=s.replace('q[1]<90||q[1]>this.h-180',"q[1]<112||q[1]>this.h-(this.w<780?(document.querySelector('#journeyCard')?.offsetHeight||240)+65:55)")
s=s.replace('occupied.push([q[0],q[1],width]);','occupied.push([q[0],q[1],width]);seenNames.add(label);').replace('c.strokeText(o.n,q[0],q[1]);','c.strokeText(label,q[0],q[1]);').replace('c.fillText(o.n,q[0],q[1]);','c.fillText(label,q[0],q[1]);')
s=replace_once(s,'.map(({p,day,n})=>','.map(({p,day,n,origin,destination})=>')
s=s.replace("${S.selected===p.id?'selected':''}","${S.selected===p.id||destination?'selected':''} ${origin?'origin':''}")
s=replace_once(s,"${S.done[p.id]?'✓':p.id==='hotel'?'宿':p.id==='port'?'关':n}","${p.id==='hotel'?'宿':p.id==='port'?'关':S.done[p.id]?'✓':n}")
s=replace_once(s,'this.zoomAt(.8,tap.start.x,tap.start.y);this.lastTap','this.zoomAt(.8,tap.start.x,tap.start.y);else this.hitRoute(tap.start);this.lastTap')
pos=s.index('\ndraw(){')
s=s[:pos]+'''\nhitRoute(q){for(const l of this.api.legs()){if(!l.data)continue;const ps=l.data._points.map(p=>this.screen(p));for(let i=1;i<ps.length;i++){const a=ps[i-1],b=ps[i],dx=b[0]-a[0],dy=b[1]-a[1],len=dx*dx+dy*dy;if(len<1)continue;const t=Math.max(0,Math.min(1,((q.x-a[0])*dx+(q.y-a[1])*dy)/len));if(Math.hypot(q.x-a[0]-t*dx,q.y-a[1]-t*dy)<10){this.api.showLeg?.(l);return;}}}}'''+s[pos:]
p.write_text(s)
p=OUT/'trip.json';d=json.loads(p.read_text());d['pois'][0]['name']='关闸（澳门侧）';d['pois'][0]['desc']='珠海拱北口岸完成出境、澳门入境后，从关闸澳门侧开始步行去酒店。标记不是珠海候检大厅入口。';p.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
p=OUT/'routes.json';r=json.loads(p.read_text());warnings=[]
try:
    url='https://routing.openstreetmap.de/routed-foot/route/v1/foot/113.54861,22.21002;113.54088,22.19757?overview=full&geometries=geojson&steps=true'
    resp=requests.get(url,timeout=35);resp.raise_for_status();v=resp.json();assert v['code']=='Ok'
    route=v['routes'][0];names=[]
    for leg in route['legs']:
        for step in leg['steps']:
            n=step.get('name','')
            if n and (not names or names[-1]!=n):names.append(n)
    r['hotel:paul:walk']={'coords':route['geometry']['coordinates'],'distance':route['distance'],'duration':route['duration'],'names':names,'source':'FOSSGIS OSRM walk','date':datetime.datetime.now(datetime.timezone.utc).date().isoformat()}
except Exception as e:
    warnings.append('Optional hotel-to-old-town walk route unavailable: '+str(e))
p.write_text(json.dumps(r,ensure_ascii=False,separators=(',',':')))
p=OUT/'manifest.json';m=json.loads(p.read_text());m.update(name='澳门随行 2.0 · 从口岸到下一站',short_name='澳门随行 2.0',theme_color='#f7f8f4',background_color='#f7f8f4');p.write_text(json.dumps(m,ensure_ascii=False))
p=OUT/'sw.js';s=p.read_text();import re
s=re.sub(r"const CACHE=PREFIX\+'[^']+';","const CACHE=PREFIX+'v2-"+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')+"';",s)
p.write_text(s)
# Installation metadata stays on the same origin. Existing app and default branch are untouched.
files=[str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file()]
report={'files':len(files),'bytes':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),'pois':len(d['pois']),'routes':len(r),'hotel_walk':bool(r.get('hotel:paul:walk')),'warnings':warnings}
Path('/tmp/macau-v2-qa').mkdir(exist_ok=True)
Path('/tmp/macau-v2-qa/build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
