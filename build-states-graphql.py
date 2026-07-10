#!/usr/bin/env python3
"""
Build per-state camera GeoJSON for states on Castle Rock's NEWER "511" platform,
which exposes a GraphQL API at /api/graphql (the older states use DataTables —
see build-states.py). One listCameraViewsQuery returns every camera with a bbox
(location), snapshot url, and HLS video sources.

Writes states/<code>.json for each and merges them into states/index.json.
Usage: python3 build-states-graphql.py
"""
import urllib.request, json, gzip, re, os, time, random, concurrent.futures
from collections import defaultdict

STATES = {
  'MN': {'host':'511mn.org',            'name':'Minnesota',    'center':[-94.3,46.3],'zoom':5.8},
  'CO': {'host':'maps.cotrip.org',      'name':'Colorado',     'center':[-105.5,39.0],'zoom':6},
  'IA': {'host':'www.511ia.org',        'name':'Iowa',         'center':[-93.5,42.0],'zoom':6.5},
  'NE': {'host':'www.511.nebraska.gov', 'name':'Nebraska',     'center':[-99.8,41.5],'zoom':6},
  'IN': {'host':'511in.org',            'name':'Indiana',      'center':[-86.3,39.9],'zoom':6.5},
  'KS': {'host':'www.kandrive.gov',     'name':'Kansas',       'center':[-98.3,38.5],'zoom':6},
  'MA': {'host':'mass511.com',          'name':'Massachusetts','center':[-71.8,42.2],'zoom':7.5},
}

QUERY = ('query ($input: ListArgs!) { listCameraViewsQuery(input: $input) { '
         'cameraViews { title uri url sources { type src } '
         'parentCollection { uri bbox location { routeDesignator } } } totalRecords } }')

def gql(host, variables, timeout=60, tries=4):
    body=json.dumps({'query':QUERY,'variables':variables}).encode()
    for i in range(tries):
        try:
            req=urllib.request.Request(f'https://{host}/api/graphql', data=body,
                headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/json','Accept-Encoding':'gzip','Origin':f'https://{host}'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b=r.read()
                if b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
                return json.loads(b)
        except Exception as e:
            if i==tries-1: raise
            time.sleep(2*(i+1))

def input_all(limit=6000):
    return {"input":{"west":-180,"south":-85,"east":180,"north":85,"sortDirection":"DESC",
            "sortType":"ROADWAY","freeSearchTerm":"","classificationsOrSlugs":[],"recordLimit":limit,"recordOffset":0}}

def video_plays(url):
    if not url: return False
    # A signed token cannot be baked into a static JSON file. Kansas hands out
    # KDOT stream URLs carrying a JWT with a 300 second TTL: it CORS-checks green
    # here at build time, then every one of them 401s five minutes later, and the
    # map cheerfully shows a red LIVE badge over 184 dead cameras. Massachusetts
    # (trafficland.com) does the same. Refuse them at the source, not in index.json.
    if 'token=' in url: return False
    try:
        req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Origin':'http://localhost'})
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.headers.get('Access-Control-Allow-Origin') in ('*','http://localhost')
    except Exception: return False

def video_plays_any(urls, n=8):
    """One dead camera must not decide a whole state: roughly 5% of DOT streams are
    down at any moment, so testing a single stream is a coin flip."""
    urls=[u for u in urls if u]
    if not urls: return False
    return any(video_plays(u) for u in random.sample(urls, min(n, len(urls))))

def build(code, cfg):
    host=cfg['host']
    d=gql(host, input_all())
    views=d['data']['listCameraViewsQuery']['cameraViews']
    # group views by physical camera (parentCollection.uri)
    cams=defaultdict(lambda:{'name':None,'coords':None,'dirs':[]})
    for v in views:
        pc=v.get('parentCollection') or {}
        key=pc.get('uri') or v.get('uri')
        bbox=pc.get('bbox')
        if not bbox: continue
        lng,lat=bbox[0],bbox[1]  # point bbox [w,s,e,n]
        c=cams[key]
        c['name']=c['name'] or v.get('title') or pc.get('title')
        c['coords']=c['coords'] or [lng,lat]
        vid=None
        for s in (v.get('sources') or []):
            if s.get('type')=='application/x-mpegURL' or (s.get('src','').endswith('.m3u8')): vid=s['src']; break
        if v.get('url') or vid:
            c['dirs'].append({'snapshot':v.get('url'),'video':vid,'label':(v.get('category') or '').title()})
    feats=[]
    for c in cams.values():
        if not c['coords'] or not c['dirs']: continue
        feats.append({'type':'Feature','geometry':{'type':'Point','coordinates':c['coords']},
            'properties':{'name':c['name'] or 'Camera','kind':'live','directions':c['dirs'],'roadway':'','county':''}})
    # video flag: do any of several sampled streams allow cross-origin playback?
    all_vid=[di['video'] for f in feats for di in f['properties']['directions'] if di['video']]
    plays=video_plays_any(all_vid)
    return feats, plays

def main():
    os.makedirs('states', exist_ok=True)
    index=json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    def run(item):
        code,cfg=item
        try:
            feats,plays=build(code,cfg)
            json.dump({'type':'FeatureCollection','features':feats}, open(f'states/{code}.json','w'))
            return code,cfg,len(feats),plays,None
        except Exception as e:
            return code,cfg,0,False,str(e)[:90]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        for code,cfg,n,plays,err in ex.map(run, STATES.items()):
            if err: print(f'  [FAIL] {code}: {err}'); continue
            index[code]={'name':cfg['name'],'file':f'states/{code}.json','count':n,'center':cfg['center'],'zoom':cfg['zoom'],'video':plays}
            print(f'  {code:3} {cfg["name"]:14} {n:5} cams  video={plays}')
    json.dump(index, open('states/index.json','w'), indent=1)
    print(f'\nindex now has {len(index)} states, {sum(v["count"] for v in index.values())} cameras')

if __name__=='__main__': main()
