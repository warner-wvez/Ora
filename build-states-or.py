#!/usr/bin/env python3
"""
Build Oregon cameras. ODOT TripCheck publishes its full camera inventory as an
ESRI-style JSON file: tripcheck.com/Scripts/map/data/cctvinventory.js
Each feature has latitude/longitude, title, route, and a filename; the snapshot
image is tripcheck.com/RoadCams/cams/{filename}. Snapshot-only.

Usage: python3 build-states-or.py
"""
import urllib.request, json, os

def main():
    req=urllib.request.Request('https://tripcheck.com/Scripts/map/data/cctvinventory.js', headers={'User-Agent':'Mozilla/5.0'})
    d=json.loads(urllib.request.urlopen(req, timeout=60).read())
    feats=[]
    for f in d['features']:
        a=f['attributes']; lat,lng,fn=a.get('latitude'),a.get('longitude'),a.get('filename')
        if not lat or not lng or not fn: continue
        feats.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lng,lat]},
            'properties':{'name':(a.get('title') or 'Camera').strip(),'kind':'live',
                'directions':[{'snapshot':f'https://tripcheck.com/RoadCams/cams/{fn}','video':None,'label':''}],
                'roadway':(a.get('route') or '').strip(),'county':''}})
    os.makedirs('states', exist_ok=True)
    json.dump({'type':'FeatureCollection','features':feats}, open('states/OR.json','w'))
    idx=json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['OR']={'name':'Oregon','file':'states/OR.json','count':len(feats),'center':[-120.5,44.0],'zoom':6,'video':False}
    json.dump(idx, open('states/index.json','w'), indent=1)
    print(f'Oregon: {len(feats)} cameras')

if __name__=='__main__': main()
