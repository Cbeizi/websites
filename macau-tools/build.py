import base64, datetime, io, json, pathlib, re, shutil, time, zipfile
import requests, shapefile
from PIL import Image, ImageDraw
ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=pathlib.Path('/tmp/macau-site'); OUT.mkdir(exist_ok=True)
for f in (ROOT/'macau-mobile').iterdir():
    if f.is_file() and f.suffix in ['.html','.css','.js','.json'] and f.name not in ['map.json','routes.json','build-report.json']: shutil.copy(f,OUT/f.name)
S=requests.Session();S.headers['User-Agent']='MacauPocketOffline/1.0 (personal itinerary map; source Cbeizi/websites)'
def get(url):
    last=None
    for i in range(3):
        try:
            r=S.get(url,timeout=65);r.raise_for_status();return r
        except Exception as e:last=e;time.sleep(i+1)
    raise last
z=zipfile.ZipFile(io.BytesIO(get('https://download.geofabrik.de/asia/china/macau-latest-free.shp.zip').content))
outline=get('https://raw.githubusercontent.com/ngsiolei/macau-map-data/master/macau.json').json()
D=json.loads((OUT/'trip.json').read_text());P={p['id']:p for p in D['pois']}
M={'date':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),'land':[],'roads':[],'areas':[],'buildings':[]}
def pts(ps):
    r=[]
    for x,y in ps:
        p=[round(x,6),round(y,6)]
        if not r or p!=r[-1]:r.append(p)
    return r
for f in outline['features']:
    g=f['geometry'];polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    for poly in polys:
        for i,ring in enumerate(poly):M['land'].append({'p':pts(ring),'water':i>0})
def features(name):
    n='gis_osm_'+name+'_1';r=shapefile.Reader(shp=io.BytesIO(z.read(n+'.shp')),dbf=io.BytesIO(z.read(n+'.dbf')),shx=io.BytesIO(z.read(n+'.shx')),encoding='utf-8')
    for sr in r.iterShapeRecords():
        indices=list(sr.shape.parts)+[len(sr.shape.points)]
        for i in range(len(indices)-1):
            p=pts(sr.shape.points[indices[i]:indices[i+1]])
            if len(p)<2:continue
            if not any(113.50<=x<=113.62 and 22.09<=y<=22.23 for x,y in p):continue
            yield sr.record.as_dict(),p
for a,p in features('roads_free'):
    k=a.get('fclass','');n=a.get('name','');c=re.match(r'^[\u3400-\u9fff\d（）()·／/、\s]+',n)
    if c and c.group().strip():n=c.group().strip()
    M['roads'].append({'p':p,'n':n,'major':k.split('_')[0] in ['primary','secondary','trunk'],'foot':k in ['footway','path','steps','pedestrian','cycleway']})
M['roads'].sort(key=lambda r:not r['major'])
for a,p in features('buildings_a_free'):M['buildings'].append({'p':p})
for a,p in features('landuse_a_free'):
    if a['fclass'] in ['forest','park','grass','recreation_ground','scrub','meadow']:M['areas'].append({'p':p,'k':'park'})
for a,p in features('water_a_free'):M['areas'].append({'p':p,'k':'water'})
(OUT/'map.json').write_text(json.dumps(M,ensure_ascii=False,separators=(',',':')))
R={}; failures=[]; cache=ROOT/'macau-mobile/routes.json'
if cache.exists():
    try:R=json.loads(cache.read_text())
    except Exception:pass
for plan in D['plans'].values():
    i=1
    while i<len(plan):
        mode=plan[i][1];j=i+1
        while j<len(plan) and plan[j][1]==mode:j+=1
        group=plan[i-1:j];keys=[':'.join([group[n-1][0],group[n][0],mode]) for n in range(1,len(group))]
        if all(k in R for k in keys):i=j;continue
        coords=';'.join(str(P[x[0]]['lon'])+','+str(P[x[0]]['lat']) for x in group)
        url='https://routing.openstreetmap.de/routed-'+('foot' if mode=='walk' else 'car')+'/route/v1/driving/'+coords+'?overview=false&geometries=geojson&steps=true&continue_straight=false'
        try:
            time.sleep(1.3);v=get(url).json()
            if v.get('code')!='Ok':raise ValueError(str(v)[:200])
            for key,leg in zip(keys,v['routes'][0]['legs']):
                line=[];names=[]
                for step in leg['steps']:
                    for p in step.get('geometry',{}).get('coordinates',[]):
                        p=[round(p[0],6),round(p[1],6)]
                        if not line or p!=line[-1]:line.append(p)
                    name=step.get('name','')
                    if name and (not names or name!=names[-1]):names.append(name)
                if len(line)<2:raise ValueError('route geometry missing')
                R[key]={'coords':line,'distance':leg['distance'],'duration':leg['duration'],'names':names,'source':'FOSSGIS OSRM '+mode,'date':M['date']}
                print('ROUTE',key,len(line),leg['distance'],flush=True)
        except Exception as e:failures.append({'keys':keys,'error':str(e)});print('ROUTE_ERROR',str(e),flush=True)
        i=j
(OUT/'routes.json').write_text(json.dumps(R,ensure_ascii=False,separators=(',',':')))
imgdir=OUT/'img';imgdir.mkdir(exist_ok=True)
sprite=Image.open(io.BytesIO(base64.b64decode((ROOT/'macau-tools/thumbs.b64').read_text())))
assert sprite.size==(240,192),sprite.size
for i,p in enumerate(D['pois']):sprite.crop(((i%5)*48,(i//5)*48,(i%5+1)*48,(i//5+1)*48)).save(imgdir/(p['id']+'.webp'),format='WEBP',quality=85)
icon='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect width="192" height="192" rx="42" fill="#294e3e"/><path d="M55 137V65a17 17 0 0 1 34 0v62a17 17 0 0 0 34 0V56" fill="none" stroke="#fff8e7" stroke-width="13" stroke-linecap="round"/><circle cx="123" cy="50" r="11" fill="#dc8655"/></svg>'
(OUT/'icon.svg').write_text(icon)
for size in [192,512]:
    im=Image.new('RGB',(size,size),'#294e3e');d=ImageDraw.Draw(im);k=size/192
    xy=lambda box:tuple(round(x*k) for x in box)
    d.line(xy((55,137,55,65)),fill='#fff8e7',width=round(13*k));d.arc(xy((55,48,89,82)),180,360,fill='#fff8e7',width=round(13*k));d.line(xy((89,65,89,127)),fill='#fff8e7',width=round(13*k));d.arc(xy((89,110,123,144)),0,180,fill='#fff8e7',width=round(13*k));d.line(xy((123,127,123,56)),fill='#fff8e7',width=round(13*k));d.ellipse(xy((112,39,134,61)),fill='#dc8655');im.save(OUT/('icon-'+str(size)+'.png'))
manifest={'id':'./','name':'澳门随行 · 离线旅行地图','short_name':'澳门随行','lang':'zh-CN','start_url':'./index.html','scope':'./','display':'standalone','background_color':'#f7f8f5','theme_color':'#f7f8f5','icons':[{'src':'icon-'+str(n)+'.png','sizes':str(n)+'x'+str(n),'type':'image/png','purpose':'any maskable'} for n in [192,512]]}
(OUT/'manifest.webmanifest').write_text(json.dumps(manifest,ensure_ascii=False))
(OUT/'LICENSE-MAP.txt').write_text('Map data: OpenStreetMap contributors / Geofabrik, ODbL 1.0. https://www.openstreetmap.org/copyright\nCoastline reference: https://github.com/ngsiolei/macau-map-data\nRoute snapshots: FOSSGIS OSRM, https://routing.openstreetmap.de/about.html\nIllustrations: user conversation generated artwork, not photographs.\n')
assets=[str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.name not in ['sw.js','build-report.json']]
sw=(ROOT/'macau-tools/sw-template.js').read_text().replace('__FILES__',json.dumps(assets)).replace('__VERSION__',datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S'))
(OUT/'sw.js').write_text(sw)
needed={':'.join([plan[i-1][0],plan[i][0],plan[i][1]]) for plan in D['plans'].values() for i in range(1,len(plan))}
report={'date':M['date'],'roads':len(M['roads']),'buildings':len(M['buildings']),'pois':len(D['pois']),'routes':len(R),'needed_routes':len(needed),'missing_routes':sorted(needed-set(R)),'routing_errors':failures,'assets':len(assets),'bytes':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())}
(OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
assert not report['missing_routes'],report
