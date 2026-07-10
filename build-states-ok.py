#!/usr/bin/env python3
"""
Build Oklahoma cameras from ODOT's OKTraffic feed.

A video state. CameraPoles returns one pole per location with a mapCameras[] list,
and every mapCamera carries a Wowza HLS stream (stream.oktraffic.org, https,
Access-Control-Allow-Origin: *) that plays in the browser. Every camera on a pole
shares one coordinate, so each pole becomes one pin with a view per direction, the
same shape Illinois uses. There is no still, so it is the Texas noposter shape.

The nested mapCameras only come back when you send the LoopBack `filter` header the
site sends; that header also drops Out Of Service and non-Web cameras server-side,
which is why the count already excludes them.

RWIS DEFERRED. OKTraffic also publishes 33 road-weather stations
(OdotRwisStations/getAllWithLastData), 30 with a camera image on rwis.tulsa.ou.edu
and structured readings (temperature/wind/surface, often null). That host is
unreachable from here and from a real browser alike (it times out on https, cert
bypass and all), and the capture never loaded one, so the RWIS images have no
verified source. Shipping them would put ~30 broken pins on the map. Wire them in
once the OU-Tulsa host answers; the readings themselves come back fine.
"""
import os, json, urllib.request

URL = 'https://oktraffic.org/api/CameraPoles'
# LoopBack filter: pull each pole's in-service Web cameras with their stream URLs
FILTER = ('{"include":[{"relation":"mapCameras","scope":{"include":"streamDictionary",'
          '"where":{"status":{"neq":"Out Of Service"},"type":"Web","blockAtis":{"neq":"1"}}}}]}')
HDRS = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://oktraffic.org', 'filter': FILTER}
# reject any pin outside Oklahoma rather than trusting a bad coordinate
BBOX = (-103.1, 33.5, -94.3, 37.1)  # lon_min, lat_min, lon_max, lat_max
COMPASS = {'N': 'North', 'S': 'South', 'E': 'East', 'W': 'West',
           'NE': 'Northeast', 'NW': 'Northwest', 'SE': 'Southeast', 'SW': 'Southwest'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=90) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def main():
    poles = get(URL)
    feats, skipped = [], 0
    for p in poles:
        dirs, lat, lon, city = [], None, None, None
        for m in p.get('mapCameras', []):
            src = (m.get('streamDictionary') or {}).get('streamSrc')
            if not src:
                continue
            try:
                la, lo = float(m['latitude']), float(m['longitude'])
            except (TypeError, ValueError, KeyError):
                continue
            if lat is None:
                lat, lon, city = la, lo, m.get('city')
            code = (m.get('direction') or '').strip()
            dirs.append({'snapshot': None, 'video': src, 'label': COMPASS.get(code, code)})
        if not dirs or lat is None:
            skipped += 1; continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': (p.get('name') or '').strip(), 'kind': 'live',
                                     'directions': dirs, 'roadway': '', 'county': (city or '').strip()}})

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/OK.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['OK'] = {'name': 'Oklahoma', 'file': 'states/OK.json', 'count': len(feats),
                 'center': [-97.5, 35.5], 'zoom': 6.4, 'video': True}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    views = sum(len(f['properties']['directions']) for f in feats)
    print(f'Oklahoma: {len(feats)} poles, {views} camera views ({skipped} skipped)')


if __name__ == '__main__':
    main()
