#!/usr/bin/env python3
"""
Build per-state camera GeoJSON for states on Castle Rock's NEWER "511" platform,
which exposes a GraphQL API at /api/graphql (the older states use DataTables —
see build-states.py). Two queries per state, joined on the camera's uri: the
map's MapFeatures query gives each camera's location, and listCameraViewsQuery
gives every view with its snapshot url and HLS video sources.

Writes states/<code>.json for each and merges them into states/index.json.
Usage: python3 build-states-graphql.py
"""
import urllib.request, json, gzip, re, os, time, random, concurrent.futures
from collections import defaultdict

# Colorado left this platform for the CARS 511x site around October 2026; maps.cotrip.org
# now answers /api/graphql with the new site's HTML page.
STATES = {
  'MN': {'host':'511mn.org',            'name':'Minnesota',    'center':[-94.3,46.3],'zoom':5.8},
  'IA': {'host':'www.511ia.org',        'name':'Iowa',         'center':[-93.5,42.0],'zoom':6.5},
  'NE': {'host':'www.511.nebraska.gov', 'name':'Nebraska',     'center':[-99.8,41.5],'zoom':6},
  'IN': {'host':'511in.org',            'name':'Indiana',      'center':[-86.3,39.9],'zoom':6.5},
  'KS': {'host':'www.kandrive.gov',     'name':'Kansas',       'center':[-98.3,38.5],'zoom':6},
  'MA': {'host':'mass511.com',          'name':'Massachusetts','center':[-71.8,42.2],'zoom':7.5},
}

# By 2026-10-20 the platform answered only query documents its own website sends, word for
# word: any other text, even a bare `{ totalRecords }`, is a 400 with {"message":"Server
# error."}. So both queries below are copied verbatim from the sites' own requests, and
# fields this builder does not read stay in them. Do not trim or reformat them. If the 400
# comes back, open the state's map and camera list in a browser, copy the new text from
# the /api/graphql requests, and paste it here.
LIST_QUERY = ('query ($input: ListArgs!) { listCameraViewsQuery(input: $input) { cameraViews { category icon '
              'lastUpdated { timestamp timezone } title uri url sources { type src } parentCollection { title uri '
              'icon color location { routeDesignator } lastUpdated { timestamp timezone } } } totalRecords error '
              '{ message type } } }')
MAP_QUERY = ('query MapFeatures($input: MapFeaturesArgs!, $plowType: String) { mapFeaturesQuery(input: $input) { '
             'mapFeatures { bbox title tooltip uri features { id geometry properties type } ... on Cluster { maxZoom } '
             '... on Sign { signDisplayType } ... on Event { priority } __typename ... on Camera { active views(limit: '
             '5) { uri ... on CameraView { url } category } } ... on Plow { views(limit: 5, plowType: $plowType) { uri '
             '... on PlowCameraView { url } category } } } error { message type } } }')

def gql(host, query, variables, timeout=60, tries=4):
    body=json.dumps({'query':query,'variables':variables}).encode()
    for i in range(tries):
        try:
            # no Accept-Encoding: gzip. Minnesota's ~1MB camera list answers a gzip request with a
            # 502 from its gateway (checked 2026-10-20), and plain is only a megabyte or two
            req=urllib.request.Request(f'https://{host}/api/graphql', data=body,
                headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/json','Origin':f'https://{host}'})
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

# the whole world at street zoom: at zoom 14 the map never groups cameras into clusters,
# so one request returns every camera as its own feature (checked on all six states)
def map_all():
    return {"input":{"north":85,"south":-85,"east":180,"west":-180,"zoom":14,
            "layerSlugs":["normalCameras"],"nonClusterableUris":["dashboard"]},"plowType":"plowCameras"}

# Paged the way the site pages it. Minnesota's whole list (about 1,950 views) in one request
# sometimes takes over 15s server side and the gateway answers 502; 500 per page took ~9s
# each, so 250 keeps every page well inside that limit.
PAGE = 250

def list_views(host):
    views, off = [], 0
    while True:
        v = input_all(PAGE); v['input']['recordOffset'] = off
        q = gql(host, LIST_QUERY, v)['data']['listCameraViewsQuery']
        page = q.get('cameraViews') or []
        views += page; off += PAGE
        if len(page) < PAGE or off >= (q.get('totalRecords') or 0):
            if len(views) != q.get('totalRecords'):
                raise RuntimeError(f'list query: got {len(views)} views of {q.get("totalRecords")}')
            return views

def locations(host):
    q=gql(host, MAP_QUERY, map_all())['data']['mapFeaturesQuery']
    feats=q.get('mapFeatures') or []
    clusters=sum(1 for f in feats if f.get('__typename')=='Cluster')
    if q.get('error') or clusters:
        raise RuntimeError(f'map query: error={q.get("error")} clusters={clusters}')
    return {f['uri']:(f['bbox'][:2], f.get('title')) for f in feats if f.get('__typename')=='Camera' and f.get('bbox')}

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
    where=locations(host)
    views=list_views(host)
    # group views by physical camera (parentCollection.uri), placed by the map's location
    cams=defaultdict(lambda:{'name':None,'coords':None,'dirs':[]})
    for v in views:
        pc=v.get('parentCollection') or {}
        key=pc.get('uri') or v.get('uri')
        if key not in where: continue                                            # no location -> cannot place a pin
        lng,lat=where[key][0]  # point bbox [w,s,e,n]
        c=cams[key]
        c['name']=c['name'] or v.get('title') or pc.get('title')
        c['coords']=c['coords'] or [lng,lat]
        vid=None
        for s in (v.get('sources') or []):
            if s.get('type')=='application/x-mpegURL' or (s.get('src','').endswith('.m3u8')): vid=s['src']; break
        # a camera that is down right now gets the site's own icon path as its url
        # (/images/icon-camera-closed-fill-solid-padded.svg on Minnesota), which is no image at all
        url=v.get('url') if (v.get('url') or '').startswith('http') else None
        if url or vid:
            # the copied query now returns `category` (VIDEO, IMAGE); the label stays empty as it always has
            c['dirs'].append({'snapshot':url,'video':vid,'label':''})
    # location-first: a camera on the map with no view in the list still marks a spot
    for key,(coords,title) in where.items():
        if key not in cams: cams[key].update(name=title, coords=list(coords))
    feats=[]
    for c in cams.values():
        if not c['coords']: continue                                             # no location -> cannot place a pin
        if not c['dirs']: c['dirs']=[{'snapshot':None,'video':None,'label':''}]   # location-first: keep feed-less cameras
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
            # a relay or sign field is decided by hand and must survive a rebuild (eccf4aa)
            keep={k:index[code][k] for k in ('relay','sign') if k in index.get(code,{})}
            index[code]={'name':cfg['name'],'file':f'states/{code}.json','count':n,'center':cfg['center'],'zoom':cfg['zoom'],'video':plays,**keep}
            print(f'  {code:3} {cfg["name"]:14} {n:5} cams  video={plays}')
    json.dump(index, open('states/index.json','w'), indent=1)
    print(f'\nindex now has {len(index)} states, {sum(v["count"] for v in index.values())} cameras')

if __name__=='__main__': main()
