#!/usr/bin/env python3
"""
Build Virginia cameras from VDOT 511's public REST endpoint:
  https://511.vdot.virginia.gov/services/map/array/cameras
Returns GeoJSON-ish features with geometry.coordinates, an `active` flag, a
snapshot `image_url`, and (unused here) HLS `ios_url`. The human-readable name
is in `description` (`name` holds the stream token). Snapshot-only: the video
host wouldn't verify CORS and its stream tokens may be short-lived.

Usage: python3 build-states-va.py
"""
import urllib.request, json, gzip, os

def main():
    req=urllib.request.Request('https://511.vdot.virginia.gov/services/map/array/cameras',
        headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip','Referer':'https://511.vdot.virginia.gov/'})
    b=urllib.request.urlopen(req, timeout=60).read()
    if b[:2]==b'\x1f\x8b': b=gzip.decompress(b)
    d=json.loads(b)
    items=d if isinstance(d,list) else next((v for v in d.values() if isinstance(v,list)), [])
    feats=[]
    for it in items:
        p=it['properties']; coords=(it.get('geometry') or {}).get('coordinates')
        if not coords: continue   # location-first: keep inactive + image-less cams, drop only no-coordinate rows
        nm=(p.get('description') or '').strip() or 'Traffic camera'
        rd=((p.get('route') or '').strip()+' '+(p.get('direction') or '').strip()).strip()
        feats.append({'type':'Feature','geometry':{'type':'Point','coordinates':coords},
            'properties':{'name':nm,'kind':'live','directions':[{'snapshot':p.get('image_url') or None,'video':None,'label':''}],
                'roadway':rd,'county':(p.get('jurisdiction') or '').strip()}})
    os.makedirs('states', exist_ok=True)
    json.dump({'type':'FeatureCollection','features':feats}, open('states/VA.json','w'))
    idx=json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['VA']={'name':'Virginia','file':'states/VA.json','count':len(feats),'center':[-78.7,37.9],'zoom':6.3,'video':False}
    json.dump(idx, open('states/index.json','w'), indent=1)
    print(f'Virginia: {len(feats)} cameras')

if __name__=='__main__': main()
