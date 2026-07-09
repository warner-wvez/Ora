#!/usr/bin/env python3
"""
Build Ohio cameras from OHGO's public API (https://publicapi.ohgo.com).
Requires a free OHGO API key, read from the OHGO_API_KEY environment variable
so it never lands in the repo:

  OHGO_API_KEY=your-key python3 build-states-oh.py

Snapshot-only: OHGO cameras are refreshing JPEGs on itscameras.dot.state.oh.us,
no HLS stream.
"""
import os, urllib.request, json, gzip

KEY=os.environ.get('OHGO_API_KEY')
if not KEY:
    raise SystemExit('Set OHGO_API_KEY (get a free key at https://publicapi.ohgo.com)')

def api(path, timeout=40):
    req=urllib.request.Request(f'https://publicapi.ohgo.com/api/v1/{path}',
        headers={'Authorization':f'APIKEY {KEY}','User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b=r.read()
        if b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
        return json.loads(b)

def main():
    feats=[]; page=1
    while True:
        d=api(f'cameras?page-size=500&page={page}')
        for c in d.get('results',[]):
            lat,lng=c.get('latitude'),c.get('longitude')
            if not lat or not lng: continue
            dirs=[]
            for v in (c.get('cameraViews') or []):
                u=v.get('largeUrl') or v.get('smallUrl')
                if u: dirs.append({'snapshot':u,'video':None,'label':(v.get('direction') or '').strip()})
            if not dirs: continue
            feats.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lng,lat]},
                'properties':{'name':(c.get('location') or c.get('description') or 'Camera').strip(),
                              'kind':'live','directions':dirs,'roadway':'','county':''}})
        if page>=d.get('totalPageCount',1): break
        page+=1
    os.makedirs('states', exist_ok=True)
    json.dump({'type':'FeatureCollection','features':feats}, open('states/OH.json','w'))
    idx=json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['OH']={'name':'Ohio','file':'states/OH.json','count':len(feats),'center':[-82.8,40.3],'zoom':6.3,'video':False}
    json.dump(idx, open('states/index.json','w'), indent=1)
    print(f'Ohio: {len(feats)} cameras')

if __name__=='__main__': main()
