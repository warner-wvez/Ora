#!/usr/bin/env python3
"""
Build Delaware cameras from DelDOT's TMC video feed.

Delaware is the Texas shape: live video, no snapshots. Every direction gets
`snapshot: None`, and index.html's `.noposter` path fades the HLS in over a dark
backdrop instead of a poster. It gets no health file, same as Texas, because the
sweep fingerprints snapshots and there are none to fingerprint.

Two fields describe a camera and they do not mean the same thing:

  * `enabled` (bool) is whether DelDOT operates the camera at all. Stable; all
    358 are true.
  * `status` ("Active"/"Unavailable") is whether the stream is up this second. It
    flaps: 11 read "Unavailable" right now, and a different 11 will an hour later.

We key on `enabled`, not `status`. Filtering a flapping signal would freeze a
moving target and permanently drop cameras that recover, and the browser's
watchLiveness() already flips a dead stream's badge to NOT LIVE, so keeping a
currently-down camera never makes it falsely claim LIVE. The count therefore
means "cameras DelDOT runs", which is true and stable.

The HLS lives in `urls.m3u8s` on video.deldot.gov:443, verified
`Access-Control-Allow-Origin: *` with a valid #EXTM3U master playlist. The `id`
query param and the Referer header both turn out to be optional (the endpoint
200s without either), but we send them anyway to look like the map page and to
survive a future WAF tightening.
"""
import os, json, urllib.request

URL = 'https://tmc.deldot.gov/json/videocamera.json?id=4yte'
HDRS = {'Referer': 'https://deldot.gov/', 'User-Agent': 'Mozilla/5.0'}
# reject any pin that lands outside Delaware rather than dropping a bad coordinate
BBOX = (-75.85, 38.40, -74.98, 39.90)  # lon_min, lat_min, lon_max, lat_max


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def main():
    data = get(URL)
    feats, skipped, unavailable = [], 0, 0
    for c in data.get('videoCameras', []):
        m3u8s = (c.get('urls') or {}).get('m3u8s')
        lat, lon = c.get('lat'), c.get('lon')
        if not c.get('enabled') or not m3u8s or not m3u8s.startswith('https://'):
            skipped += 1; continue
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            skipped += 1; continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        if c.get('status') != 'Active':
            unavailable += 1
        title = (c.get('title') or '').strip()
        # DelDOT titles read "ROUTE @ LOCATION"; the roadway is the part before @
        roadway = title.split('@')[0].strip() if '@' in title else ''
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': title,
                                     'kind': 'live',
                                     'directions': [{'snapshot': None, 'video': m3u8s, 'label': ''}],
                                     'roadway': roadway,
                                     'county': (c.get('county') or '').strip()}})
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/DE.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['DE'] = {'name': 'Delaware', 'file': 'states/DE.json', 'count': len(feats),
                 'center': [-75.45, 39.1], 'zoom': 7.8, 'video': True}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'Delaware: {len(feats)} cameras '
          f'({skipped} skipped, {unavailable} currently Unavailable but kept)')


if __name__ == '__main__':
    main()
