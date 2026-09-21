#!/usr/bin/env python3
"""
Build Oklahoma cameras from ODOT's OKTraffic feed.

Location-first: every camera location is a pin, live feed or not. CameraPoles
gives one pole per location with a mapCameras[] list, each on a Wowza HLS stream
(stream.oktraffic.org, https, ACAO:*) that plays in the browser. Every camera on
a pole shares one coordinate, so each pole is one pin with a view per direction,
the Illinois shape. No still, so it is the Texas noposter shape.

We send only the LoopBack `filter` header needed to pull the nested mapCameras and
their streams. We deliberately do NOT drop Out Of Service cameras any more: an
out-of-service camera still marks a spot where a camera exists, and its (dead or
placeholder) stream degrades to an honest offline pin. Only genuinely empty poles
(no camera hardware at all) fall out.

RWIS: OdotRwisStations/getAllWithLastData carries road-weather stations that also
have a camera. Their images live on rwis.tulsa.ou.edu, which is currently
unreachable (down or firewalled), so those pins will read offline until it
answers; we carry them regardless, with whatever readings are present, because the
location and the weather are the point. Stations with no camera image are skipped.
"""
import os, json, urllib.request

CAMERAS = 'https://oktraffic.org/api/CameraPoles'
RWIS = 'https://oktraffic.org/api/OdotRwisStations/getAllWithLastData'
# LoopBack filter: pull each pole's Web cameras with their streams (in service or not)
FILTER = '{"include":[{"relation":"mapCameras","scope":{"include":"streamDictionary","where":{"type":"Web"}}}]}'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://oktraffic.org', 'filter': FILTER}
RHDRS = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://oktraffic.org'}
BBOX = (-103.1, 33.5, -94.3, 37.1)  # lon_min, lat_min, lon_max, lat_max
COMPASS = {'N': 'North', 'S': 'South', 'E': 'East', 'W': 'West',
           'NE': 'Northeast', 'NW': 'Northwest', 'SE': 'Southeast', 'SW': 'Southwest'}


def get(url, hdrs):
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), timeout=90) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def in_bbox(lon, lat):
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


def rwis_text(dd):
    parts = []
    t = dd.get('temperature')
    if isinstance(t, (int, float)) and -60 <= t <= 140:
        parts.append(f'Temp {round(t)} F')
    ws, wd = dd.get('windSpeed'), dd.get('windDirection')
    if isinstance(ws, (int, float)):
        w = f'Wind {round(ws)} mph'
        if isinstance(wd, (int, float)):
            w += ' ' + COMPASS_16(wd)
        parts.append(w)
    p = dd.get('totalPrecipitation')
    if isinstance(p, (int, float)) and p > 0:
        parts.append(f'Precip {p}')
    return ' · '.join(parts)


def COMPASS_16(deg):
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
            'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return dirs[int((deg % 360) / 22.5 + 0.5) % 16]


def camera_features():
    feats, skipped = [], 0
    for p in get(CAMERAS, HDRS):
        dirs, lat, lon, city = [], None, None, None
        for m in p.get('mapCameras', []):
            src = (m.get('streamDictionary') or {}).get('streamSrc')
            try:
                la, lo = float(m['latitude']), float(m['longitude'])
            except (TypeError, ValueError, KeyError):
                continue
            if lat is None:
                lat, lon, city = la, lo, m.get('city')
            code = (m.get('direction') or '').strip()
            dirs.append({'snapshot': None, 'video': src or None, 'label': COMPASS.get(code, code)})
        if not dirs or lat is None or not in_bbox(lon, lat):
            skipped += 1; continue
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': (p.get('name') or '').strip(), 'kind': 'live',
                                     'directions': dirs, 'roadway': '', 'county': (city or '').strip()}})
    return feats, skipped


def rwis_features():
    feats = 0
    out = []
    for s in get(RWIS, RHDRS):
        dd = (s.get('odotRwisStationData') or [{}])[0]
        if not dd.get('pictureName'):
            continue  # a weather sensor with no camera, not a camera location
        try:
            lat, lon = float(s['latitude']), float(s['longitude'])
        except (TypeError, ValueError, KeyError):
            continue
        if not in_bbox(lon, lat):
            continue
        props = {'name': (s.get('shortName') or s.get('name') or '').strip() + ' (RWIS)',
                 'kind': 'live',
                 'directions': [{'snapshot': dd.get('picturePath') or None, 'video': None, 'label': ''}],
                 'roadway': '', 'county': (s.get('city') or '').strip()}
        wx = rwis_text(dd)
        if wx:
            props['rwis'] = wx
        out.append({'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                    'properties': props})
        feats += 1
    return out, feats


def main():
    cams, skipped = camera_features()
    rwis, nrwis = rwis_features()
    feats = cams + rwis
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/OK.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['OK'] = {'name': 'Oklahoma', 'file': 'states/OK.json', 'count': len(feats),
                 'center': [-97.5, 35.5], 'zoom': 6.4, 'video': True}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    views = sum(len(f['properties']['directions']) for f in cams)
    print(f'Oklahoma: {len(feats)} pins ({len(cams)} camera poles / {views} views, '
          f'{nrwis} RWIS; {skipped} empty poles skipped)')


if __name__ == '__main__':
    main()
