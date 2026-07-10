#!/usr/bin/env python3
"""
Build Tennessee cameras from TDOT's SmartWay open-data feed.

A video state on the same SkyVDN platform as Texas: httpsVideoUrl is HLS that
sends Access-Control-Allow-Origin: *, so it plays in the browser, and every
camera also publishes a still we keep as the poster.

The poster the feed hands out (tnsnapshots.com/thumbs/<name>.flv.png) 301s to
tnsnapshots.com/<name>.png. Both hops are https and the browser and the health
sweep both follow the redirect, so we store the URL verbatim instead of guessing
the rewrite. The rtmp/rtsp/clsp variants are ignored; only httpsVideoUrl plays
without a plugin.
"""
import os, json, urllib.request

URL = 'https://www.tdot.tn.gov/opendata/api/public/RoadwayCameras'
# ApiKey is the public key the smartway.tn.gov client ships in the clear; the feed
# 401s without it. Origin satisfies the same gate the browser preflight passes.
HDRS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
        'ApiKey': '8d3b7a82635d476795c09b2c41facc60', 'Origin': 'https://smartway.tn.gov'}
# reject any pin outside Tennessee rather than trusting a bad coordinate
BBOX = (-90.5, 34.8, -81.5, 36.8)  # lon_min, lat_min, lon_max, lat_max


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=60) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def main():
    cams = get(URL)
    feats, skipped = [], 0
    for c in cams:
        vid, snap = c.get('httpsVideoUrl'), c.get('thumbnailUrl')
        lat, lng = c.get('lat'), c.get('lng')
        if str(c.get('active')).lower() != 'true' or not vid:
            skipped += 1; continue
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            skipped += 1; continue
        if not (BBOX[0] <= lng <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                      'properties': {'name': (c.get('title') or c.get('description') or '').strip(),
                                     'kind': 'live',
                                     'directions': [{'snapshot': snap or None, 'video': vid, 'label': ''}],
                                     'roadway': (c.get('route') or '').strip(),
                                     'county': (c.get('jurisdiction') or '').strip()}})
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/TN.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['TN'] = {'name': 'Tennessee', 'file': 'states/TN.json', 'count': len(feats),
                 'center': [-86.3, 35.8], 'zoom': 6.4, 'video': True}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'Tennessee: {len(feats)} cameras ({skipped} skipped)')


if __name__ == '__main__':
    main()
