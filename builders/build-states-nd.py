#!/usr/bin/env python3
"""
Build North Dakota cameras from NDDOT's Travel Information Map (travel.dot.nd.gov).

Snapshot-only. The React app pulls a single static GeoJSON,
travelfiles.dot.nd.gov/geojson/cameras/cameras.json (the `?ts=` the app appends
is a cache-buster; the bare path serves the current file). Each feature is a
camera *site* with a nested `Cameras` array, one entry per lens
("Ray - West", "Ray - Pavement"), so a site becomes one pin with a view per lens,
the same shape Washington and South Dakota use. No HLS anywhere, so snapshot-only.

  * Images are https://www.dot.nd.gov/travel-info/cameras/<name>.jpg. A handful
    302-redirect to a "not found" page when a lens is temporarily retired; the
    health sweep will grey those, and the location still marks a real camera site.
  * `Direction` on each lens ("West", "North", "Pavement") is a view label, not a
    travel heading, so it drives the per-view tab; there is no travel-direction
    chip to hang because the feed does not carry one.
  * `Region` (NDDOT maintenance area, e.g. "Williston Area") is the closest thing
    to a county, so it fills that slot; `Highways[0].HwyDesc` fills roadway.
"""
import os, json, urllib.request

CAMERAS = 'https://travelfiles.dot.nd.gov/geojson/cameras/cameras.json'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://travel.dot.nd.gov/'}
# reject any pin that lands outside North Dakota rather than trusting a bad coordinate
BBOX = (-104.2, 45.8, -96.4, 49.1)  # lon_min, lat_min, lon_max, lat_max


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def main():
    d = get(CAMERAS)
    feats, skipped, views = [], 0, 0
    for f in d.get('features', []):
        geom = f.get('geometry') or {}
        coords = geom.get('coordinates')
        if not coords or len(coords) < 2:
            skipped += 1; continue
        lon, lat = coords[0], coords[1]
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        p = f.get('properties') or {}
        dirs = []
        for cam in p.get('Cameras') or []:
            url = (cam.get('FullPath') or cam.get('LinkPath') or '').strip()
            if not url:
                continue
            dirs.append({'snapshot': url, 'video': None,
                         'label': (cam.get('Direction') or '').strip()})
        # location-first: a site whose every lens is missing still marks the spot
        if not dirs:
            dirs = [{'snapshot': None, 'video': None, 'label': ''}]
        views += len([x for x in dirs if x['snapshot']])
        hwys = p.get('Highways') or []
        roadway = (hwys[0].get('HwyDesc') if hwys else '') or ''
        # name the site after its road + first lens description, minus the trailing agency tag
        first_desc = (p.get('Cameras') or [{}])[0].get('Description', '') or ''
        name = first_desc.split(' - ')[0].strip() or roadway or 'Camera'
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': name, 'kind': 'live', 'directions': dirs,
                                     'roadway': roadway.strip(),
                                     'county': (p.get('Region') or '').strip()}})

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/ND.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['ND'] = {'name': 'North Dakota', 'file': 'states/ND.json', 'count': len(feats),
                 'center': [-100.5, 47.4], 'zoom': 6.3, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'North Dakota: {len(feats)} camera sites ({views} views, {skipped} skipped)')


if __name__ == '__main__':
    main()
