#!/usr/bin/env python3
"""
Build Texas cameras from the MapLarge table behind drivetexas.org (TxDOT).

Two things that are easy to get wrong:

  * The geometry lives in the `XY` column as WKT ("POINT (lng lat)"), but only if
    you name it in `sqlselect`. Omit it and the response carries no coordinates
    at all (`allGeo` is always {}).
  * The table id rotates, so resolve it fresh on every run.

The API rejects unknown query keys with a bare HTTP 500, so a `where` clause that
no longer parses looks identical to a server fault. There is no need for one:
the full table pages cleanly with start/take.

Video-only: `imageurl` is a `https://localhost/thumbs/...` placeholder, so every
direction gets `snapshot: None`. The streams are SkyVDN HLS and send
`Access-Control-Allow-Origin: *` on both playlist and segments, hence video=True.
"""
import os, json, time, re, urllib.request, urllib.parse

BASE = 'https://dtx-e-cdn.maplarge.com'
HDRS = {'Referer': 'https://drivetexas.org/', 'User-Agent': 'Mozilla/5.0'}
COLS = ['name', 'description', 'route', 'jurisdiction', 'direction', 'httpsurl', 'active', 'XY']
POINT = re.compile(r'POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)')
# reject anything that lands outside Texas rather than dropping a bad pin on the map
BBOX = (-107.0, 25.5, -93.0, 36.8)

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))

def table_id():
    return get(f'{BASE}/Remote/GetActiveTableID?shortTableId=' +
               urllib.parse.quote('appgeo/cameraPoint', safe=''))['table']

def query(tid, start, take):
    q = {'action': 'table/query',
         'query': {'table': tid, 'start': start, 'take': take, 'sqlselect': COLS}}
    return get(f'{BASE}/Api/ProcessDirect?request=' + urllib.parse.quote(json.dumps(q), safe=''))

def rows(tid):
    start, take = 0, 1000
    while True:
        d = query(tid, start, take)['data']
        cols, total = d['data'], d['totals']['Records']
        n = len(cols['name'])
        for i in range(n):
            yield {c: cols[c][i] for c in COLS}
        start += n
        if not n or start >= total:
            return
        time.sleep(0.3)

def main():
    feats, skipped = [], 0
    for r in rows(table_id()):
        m = POINT.match(r['XY'] or '')
        # location-first: keep inactive and stream-less cameras (their pin marks the spot);
        # still drop rows with no coordinate and the Paris_test_WWD test feed (not a road camera)
        if not m or not r['name'].startswith('TX_'):
            skipped += 1; continue
        lng, lat = float(m.group(1)), float(m.group(2))
        if not (BBOX[0] <= lng <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        label = (r['direction'] or '').strip()
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                      'properties': {'name': (r['description'] or r['name']).strip(),
                                     'kind': 'live',
                                     'directions': [{'snapshot': None, 'video': r['httpsurl'] or None, 'label': label}],
                                     'roadway': (r['route'] or '').strip(),
                                     'county': (r['jurisdiction'] or '').strip()}})
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/TX.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['TX'] = {'name': 'Texas', 'file': 'states/TX.json', 'count': len(feats),
                 'center': [-99.3, 31.3], 'zoom': 5.4, 'video': True}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'Texas: {len(feats)} cameras ({skipped} skipped)')

if __name__ == '__main__':
    main()
