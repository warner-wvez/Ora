#!/usr/bin/env python3
"""
Build Arkansas cameras from IDriveArkansas (ARDOT).

Snapshot-only. IDriveArkansas serves live video, but only over a redirector
(actis.idrivearkansas.com -> worldssl.net) that both origin-locks its CORS to
https://www.idrivearkansas.com AND hands back a short-lived `token=` on the
stream URL. Neither can live in a static, no-backend site, so we take the still
every camera also publishes and label Arkansas honestly as snapshot-only.

  * layers.idrivearkansas.com/cameras.geojson lists every camera with a point,
    a name, a route, and a `default_direction` (N/S/E/W travel heading).
  * The still is layers.idrivearkansas.com/cameras/<id>.jpg. It answers with
    Access-Control-Allow-Origin: * and a moving Last-Modified, and its CDN honours
    a ranged GET, so no proxy is needed. (The server mislabels it
    Content-Type: application/json, but the bytes are a real JPEG/PNG, and the
    map shows it through a plain <img> that ignores the header anyway.)

Cameras that share an exact coordinate (an interchange shot from several
directions) are collapsed into one pin with a view per direction, because stacked
map pins are unclickable -- the same fix Washington uses. The travel heading maps
to the Northbound/Southbound chip vocabulary so each view gets a compass chip.
"""
import os, json, urllib.request
from collections import defaultdict

CAMERAS = 'https://layers.idrivearkansas.com/cameras.geojson'
SNAP = 'https://layers.idrivearkansas.com/cameras/{}.jpg'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.idrivearkansas.com/'}
# reject any pin that lands outside Arkansas rather than trusting a bad coordinate
BBOX = (-94.7, 33.0, -89.6, 36.6)  # lon_min, lat_min, lon_max, lat_max
FACING = {'N': 'Northbound', 'S': 'Southbound', 'E': 'Eastbound', 'W': 'Westbound',
          'North': 'Northbound', 'South': 'Southbound', 'East': 'Eastbound', 'West': 'Westbound'}


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def main():
    d = get(CAMERAS)
    # group cameras by exact coordinate so stacked pins collapse to tabbed views
    groups = defaultdict(list)
    skipped = 0
    for f in d.get('features', []):
        coords = (f.get('geometry') or {}).get('coordinates')
        if not coords or len(coords) < 2:
            skipped += 1; continue
        lon, lat = coords[0], coords[1]
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        groups[(round(lon, 6), round(lat, 6))].append(f['properties'])

    feats, merged = [], 0
    for (lon, lat), cams in groups.items():
        if len(cams) > 1:
            merged += 1
        dirs = []
        for p in cams:
            cid = p.get('id')
            facing = FACING.get((p.get('default_direction') or '').strip())
            view = {'snapshot': SNAP.format(cid), 'video': None,
                    'label': (p.get('direction_name') or '').strip()}
            if facing:
                view['facing'] = facing
            dirs.append(view)
        p0 = cams[0]
        name = (p0.get('name') or '').strip() or 'Camera'
        route = (p0.get('route') or '').strip()
        roadway = f"{p0.get('route_type_abbr') or p0.get('route_type') or ''} {route}".strip()
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': name, 'kind': 'live', 'directions': dirs,
                                     'roadway': roadway, 'county': ''}})

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/AR.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['AR'] = {'name': 'Arkansas', 'file': 'states/AR.json', 'count': len(feats),
                 'center': [-92.4, 34.8], 'zoom': 6.6, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    views = sum(len(f['properties']['directions']) for f in feats)
    print(f'Arkansas: {len(feats)} pins ({views} camera views, {merged} shared-location merges, {skipped} skipped)')


if __name__ == '__main__':
    main()
