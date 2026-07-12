#!/usr/bin/env python3
"""
Build Kentucky cameras from KYTC's public ArcGIS feed.

Both of Kentucky's camera surfaces -- maps.kytc.ky.gov/trafficcameras and the
GoKY 511 map (goky.ky.gov) -- fetch the same open FeatureServer layer,
trafficCamerasCur_Prd on services2.arcgis.com (no key, f=json). 250 rows:
description, snapshot URL, lat/lng. Snapshot-only: neither surface plays video
anywhere (GoKY's only stream-ish endpoint is a truck-parking API behind a
token=, which the house rules refuse), so there is no live-video door to lose.

The snapshots live on www.trimarc.org, KYTC's traffic-management site, and are
genuinely fast: Last-Modified lands within the last minute on every sampled
image. 237 rows are already https. The 13 http rows split two ways:

- 9 are Indiana-side cameras around Louisville (pws.trafficwise.org, i.e.
  INDOT's TrafficWise, plus three trimarc "IND_"/in-Ind. stills). Every one is
  dead from every door -- http answers an HTML stub, https answers 404 -- and
  Ora's Indiana layer (511in.org) already carries INDOT's cameras with working
  feeds. Dropped: a permanently dead duplicate is not location-first, it is
  just a grey pin lying about a camera another layer shows live.
- 4 are Bowling Green intersections whose https variant serves the same JPEG
  fine; those get upgraded in place, which keeps the whole state on https and
  off the wsrv proxy.
"""
import json, urllib.parse, urllib.request

QUERY = ('https://services2.arcgis.com/CcI36Pduqd0OR4W9/arcgis/rest/services/'
         'trafficCamerasCur_Prd/FeatureServer/0/query?'
         + urllib.parse.urlencode({'where': '1=1', 'outFields': '*',
                                   'returnGeometry': 'true', 'outSR': '4326', 'f': 'json'}))
HDRS = {'User-Agent': 'Mozilla/5.0'}
# Kentucky plus the Louisville/Cincinnati river edge; rejects null island, not neighbours
BBOX = (-89.7, 36.3, -81.8, 39.3)


def fetch_json(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def https_serves_jpeg(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers=HDRS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(3)[:2] == b'\xff\xd8'
    except Exception:
        return False


def main():
    rows = fetch_json(QUERY)['features']
    feats, dropped = [], []
    for f in rows:
        a = f['attributes']
        lat, lng = a.get('latitude'), a.get('longitude')
        snap = (a.get('snapshot') or '').strip()
        if lat is None or lng is None or not snap:
            continue
        if not (BBOX[0] <= lng <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        if snap.startswith('http://'):
            upgraded = 'https://' + snap[len('http://'):]
            if https_serves_jpeg(upgraded):
                snap = upgraded
            else:
                # dead from every door (http = HTML stub, https = 404): the
                # Indiana-side rows whose working feeds live in Ora's IN layer
                dropped.append(a.get('description') or snap)
                continue
        name = (a.get('description') or a.get('name') or 'Camera').strip()
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                      'properties': {'name': name, 'kind': 'live',
                                     'directions': [{'snapshot': snap, 'video': None, 'label': ''}],
                                     'roadway': a.get('highway') or '', 'county': a.get('county') or ''}})

    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/KY.json', 'w'))
    index = json.load(open('states/index.json'))
    index['KY'] = {'name': 'Kentucky', 'file': 'states/KY.json', 'count': len(feats),
                   'center': [-85.7, 37.6], 'zoom': 6.5, 'video': False}
    json.dump(index, open('states/index.json', 'w'), indent=1)
    print(f'KY: {len(feats)} cameras, snapshot-only; dropped {len(dropped)} dead Indiana-side rows:')
    for d in dropped:
        print('  -', d)


if __name__ == '__main__':
    main()
