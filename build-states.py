#!/usr/bin/env python3
"""
Build per-state traffic-camera GeoJSON files from the shared "511" platform
(Castle Rock) that many state DOTs run. One adapter, many states.

Each state exposes:
  /List/GetData/Cameras   -> paged DataTables JSON: name, latLng (WKT), image + video URLs
  /map/Cctv/<imageId>     -> the live JPEG snapshot
  images[].videoUrl       -> an HLS (.m3u8) live stream on some states

Writes states/<code>.json (one FeatureCollection each) and merges them into
states/index.json, leaving states built by the other scripts alone.

Usage: python3 build-states.py            # every state below
       python3 build-states.py NY CT      # just these
"""
import urllib.request, json, gzip, zlib, urllib.parse, re, os, sys, time, random, concurrent.futures

# Optional per-state keys:
#   bbox        (w, s, e, n). Rows outside it are dropped.
#   only_state  drop any row whose own `state` column names a different state.
# 511ny carries 324 Connecticut and 66 New Jersey cameras on shared roads, and a
# bbox cannot separate them: Connecticut sits inside any New York bbox, and Ora
# already has Connecticut from ctroads.org. The feed labels them, so believe it.
STATES = {
  'FL': {'host':'fl511.com',            'name':'Florida',        'center':[-81.7,28.2],'zoom':6},
  'GA': {'host':'511ga.org',            'name':'Georgia',        'center':[-83.6,32.8],'zoom':6.5},
  'UT': {'host':'udottraffic.utah.gov', 'name':'Utah',           'center':[-111.7,39.9],'zoom':6},
  'PA': {'host':'www.511pa.com',        'name':'Pennsylvania',   'center':[-77.7,40.9],'zoom':6.5},
  'NC': {'host':'drivenc.gov',          'name':'North Carolina', 'center':[-79.4,35.5],'zoom':6.5},
  'NV': {'host':'nvroads.com',          'name':'Nevada',         'center':[-116.9,39.3],'zoom':5.8},
  'AZ': {'host':'az511.com',            'name':'Arizona',        'center':[-111.9,34.3],'zoom':6},
  'WI': {'host':'511wi.gov',            'name':'Wisconsin',      'center':[-89.7,44.5],'zoom':6.5},
  'ID': {'host':'511.idaho.gov',        'name':'Idaho',          'center':[-114.5,44.4],'zoom':5.8},
  'NE-ENG': {'host':'www.newengland511.org','name':'New England (ME/NH/VT)','center':[-71.5,44.0],'zoom':6.5},
  'CT': {'host':'ctroads.org',          'name':'Connecticut',    'center':[-72.7,41.6],'zoom':8.5},
  'LA': {'host':'511la.org',            'name':'Louisiana',      'center':[-92.0,31.0],'zoom':6.5},
  'AK': {'host':'511.alaska.gov',       'name':'Alaska',         'center':[-149.6,61.2],'zoom':5},
  'NY': {'host':'511ny.org',            'name':'New York',       'center':[-75.5,42.9],'zoom':6.3,
         'bbox':(-79.77,40.47,-71.85,45.02), 'only_state':'New York'},
}

# the popup renders a compass chip from this; anything else ('Unknown', 'Inbound') gets none
FACING = {'northbound':'Northbound', 'southbound':'Southbound', 'eastbound':'Eastbound',
          'westbound':'Westbound', 'both directions':'Both directions'}

def fetch(url, timeout=45, tries=4):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip, deflate'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b=r.read()
                if r.headers.get('Content-Encoding')=='gzip' or b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
                elif r.headers.get('Content-Encoding')=='deflate': b=zlib.decompress(b)
                return b
        except Exception as e:
            if i==tries-1: raise
            time.sleep(1.5*(i+1))

def video_plays(url):
    """Video is only usable in-browser if its host allows cross-origin playback."""
    if not url: return False
    # a signed token cannot be baked into a static JSON file; it dies minutes later
    if 'token=' in url: return False
    try:
        req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Origin':'http://localhost'})
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.headers.get('Access-Control-Allow-Origin') in ('*','http://localhost')
    except Exception:
        return False

def video_plays_any(urls, n=8):
    """One dead camera must not decide a whole state.

    Roughly 5% of DOT cameras are down at any moment, so testing the single first
    stream is a coin flip. New York's first camera (R5_007) is one of the dead
    ones: sampling it alone marks the state snapshot-only and throws away 1,553
    working live feeds, with nothing logged and nothing raised.
    """
    urls=[u for u in urls if u]
    if not urls: return False
    return any(video_plays(u) for u in random.sample(urls, min(n, len(urls))))

def page(host, start, length=100):
    q={"draw":1,"columns":[{"data":str(i),"name":"","searchable":True,"orderable":True,"search":{"value":"","regex":False}} for i in range(8)],
       "order":[{"column":0,"dir":"asc"}],"start":start,"length":length,"search":{"value":"","regex":False}}
    url=f'https://{host}/List/GetData/Cameras?query='+urllib.parse.quote(json.dumps(q))+'&lang=en-US'
    return json.loads(fetch(url))

WKT=re.compile(r'POINT\s*\(([-\d.]+)\s+([-\d.]+)\)')
def coords(row):
    try:
        wkt=row['latLng']['geography']['wellKnownText']
        m=WKT.search(wkt); return [float(m.group(1)), float(m.group(2))]
    except Exception: return None

def build_state(code, cfg):
    host=cfg['host']; rows=[]; start=0
    total=page(host,0)  # first page also gives recordsTotal
    rec=total.get('recordsTotal',0); rows+=total.get('data',[])
    start=100
    while start<rec:
        rows+=page(host,start).get('data',[]); start+=100
    feats=[]; bbox=cfg.get('bbox'); only=cfg.get('only_state')
    for r in rows:
        c=coords(r)
        if not c: continue
        # a neighbouring state's cameras on a shared road, labelled as theirs
        if only and r.get('state') and r.get('state')!=only: continue
        # null island, and one camera whose longitude lost its minus sign
        if bbox and not (bbox[0]<=c[0]<=bbox[2] and bbox[1]<=c[1]<=bbox[3]): continue
        name=(r.get('location') or r.get('roadway') or 'Camera')
        imgs=[]
        for im in r.get('images',[]):
            if im.get('disabled') or im.get('blocked'): continue
            iu=im.get('imageUrl')
            if not iu: continue
            imgs.append({
                'snapshot': f'https://{host}{iu}' if iu.startswith('/') else iu,
                'video': im.get('videoUrl') or None,
                'label': (im.get('description') or '').strip()
            })
        # location-first: a camera whose every view is disabled/blocked still marks a spot
        if not imgs: imgs=[{'snapshot':None,'video':None,'label':''}]
        # where the feed says which way the camera looks, hang it on the view,
        # same shape Washington uses. 'Unknown' and 'Inbound' get no chip.
        facing=FACING.get((r.get('direction') or '').strip().lower())
        if facing:
            for im in imgs: im['facing']=facing
        feats.append({'type':'Feature','geometry':{'type':'Point','coordinates':c},
            'properties':{'name':name,'kind':'live','directions':imgs,
                          'roadway':r.get('roadway') or '','county':r.get('county') or ''}})
    return feats

def main():
    os.makedirs('states', exist_ok=True)
    want={c.upper() for c in sys.argv[1:]}
    todo={k:v for k,v in STATES.items() if not want or k in want}
    if want-set(STATES): raise SystemExit(f'unknown state(s): {sorted(want-set(STATES))}')
    # merge, never clobber: California, Texas, Washington and the rest live in here too
    index=json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    def run(item):
        code,cfg=item
        try:
            feats=build_state(code,cfg)
            # a state counts as "video" only if a stream actually allows cross-origin
            # playback. Sample several: any single one of them may simply be broken.
            all_vid=[d['video'] for f in feats for d in f['properties']['directions'] if d['video']]
            plays=video_plays_any(all_vid)
            vids=len(all_vid) if plays else 0
            json.dump({'type':'FeatureCollection','features':feats}, open(f'states/{code}.json','w'))
            return code,cfg,len(feats),vids,None
        except Exception as e:
            return code,cfg,0,0,str(e)[:80]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for code,cfg,n,vids,err in ex.map(run, todo.items()):
            if err: print(f'  [FAIL] {code}: {err}'); continue
            index[code]={'name':cfg['name'],'file':f'states/{code}.json','count':n,
                         'center':cfg['center'],'zoom':cfg['zoom'],'video':vids>0}
            print(f'  {code:7} {cfg["name"]:22} {n:5} cams  {vids:5} with live video')
    json.dump(index, open('states/index.json','w'), indent=1)
    print(f'\nwrote states/index.json ({len(index)} states, {sum(v["count"] for v in index.values())} cameras)')

if __name__=='__main__': main()
