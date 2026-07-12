#!/usr/bin/env python3
"""
Build South Dakota cameras from SDDOT's SafeTravelUSA map (sd511.org), which runs
on Iteris' ATIS platform and serves static GeoJSON off sd.cdn.iteris-atis.com.

Snapshot-only. Two feeds, both camera sources, joined into one layer:

  * icons.cameras.geojson  -> the traffic-camera sites. Each has a `cameras`
    array (one lens per view: "Camera Looking South", "Road Surface View"), so a
    site is one pin with a view per lens, the Washington/North Dakota shape.
  * icons.rwis.geojson     -> the road-weather stations, which ALSO carry a
    `cameras` array in the identical shape, plus `atmos`/`surface` readings. We
    keep them as camera pins (their images are real road views) and hang the
    weather off the pin as an RWIS caption, the way New Mexico and Oklahoma do.

Images are https://sd.cdn.iteris-atis.com/camera_images/<site>/<lens>/latest.jpg,
a CDN that answers a ranged GET, so no proxy and no CORS special-casing. Each lens
carries its own `updateTime` (unix seconds); the freshest lens's age drives the
site's refresh wording, capped into the popup's 15s..5min poll range. No HLS is
published anywhere, so South Dakota is honestly snapshot-only.
"""
import os, json, time, urllib.request

CAMERAS = 'https://sd.cdn.iteris-atis.com/geojson/icons/metadata/icons.cameras.geojson'
RWIS = 'https://sd.cdn.iteris-atis.com/geojson/icons/metadata/icons.rwis.geojson'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.sd511.org/'}
# reject any pin that lands outside South Dakota rather than trusting a bad coordinate
BBOX = (-104.6, 42.4, -96.3, 46.0)  # lon_min, lat_min, lon_max, lat_max


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def val(node, key):
    v = (node or {}).get(key) or {}
    return v.get('value')


def rwis_text(p):
    atmos = (p.get('atmos') or [{}])[0]
    parts = []
    t = val(atmos, 'air_temperature')
    if isinstance(t, (int, float)):
        parts.append(f'Air {round(t)} F')
    rh = val(atmos, 'relative_humidity')
    if isinstance(rh, (int, float)):
        parts.append(f'Humidity {round(rh)}%')
    ws = val(atmos, 'wind_speed')
    if isinstance(ws, (int, float)):
        wd = val(atmos, 'wind_direction')
        parts.append(f'Wind {round(ws)} mph' + (f' {wd}' if isinstance(wd, str) and wd else ''))
    st = val((p.get('surface') or [{}])[0], 'surface_condition')
    if isinstance(st, str) and st and st.lower() not in ('none', 'unknown'):
        parts.append(f'Surface {st}')
    pt = val(atmos, 'precip_type')
    if isinstance(pt, str) and pt and pt.lower() not in ('none', 'unknown'):
        parts.append(pt)
    return ' · '.join(parts)


def views_for(cams):
    dirs, newest = [], 0
    for c in cams or []:
        img = (c.get('image') or '').strip()
        if not img:
            continue
        label = (c.get('name') or '').replace('Camera Looking', '').strip() or (c.get('name') or '')
        dirs.append({'snapshot': img, 'video': None, 'label': label})
        ut = c.get('updateTime')
        if isinstance(ut, (int, float)):
            newest = max(newest, ut)
    return dirs, newest


def site_feature(feat, is_rwis):
    p = feat.get('properties') or {}
    geom = feat.get('geometry') or {}
    coords = geom.get('coordinates')
    if not coords or len(coords) < 2:
        return None
    lon, lat = coords[0], coords[1]
    if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
        return None
    dirs, newest = views_for(p.get('cameras'))
    if not dirs:
        return None  # an RWIS station with readings but no camera is not a camera pin
    name = (p.get('name') or p.get('description') or 'Camera').strip()
    props = {'name': name + (' (RWIS)' if is_rwis else ''), 'kind': 'live',
             'directions': dirs, 'roadway': (p.get('route') or p.get('description') or '').strip(),
             'county': ''}
    # freshest lens age -> per-view refresh hint the popup understands
    if newest:
        age = int(time.time()) - int(newest)
        if 0 < age < 6 * 3600:
            for dv in dirs:
                dv['refresh_sec'] = max(60, age)
    if is_rwis:
        wx = rwis_text(p)
        if wx:
            props['rwis'] = wx
    return {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
            'properties': props}


def main():
    feats = []
    traffic = get(CAMERAS).get('features', [])
    for f in traffic:
        sf = site_feature(f, is_rwis=False)
        if sf:
            feats.append(sf)
    n_traffic = len(feats)
    rwis = get(RWIS).get('features', [])
    rwis_kept = 0
    for f in rwis:
        sf = site_feature(f, is_rwis=True)
        if sf:
            feats.append(sf); rwis_kept += 1

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/SD.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['SD'] = {'name': 'South Dakota', 'file': 'states/SD.json', 'count': len(feats),
                 'center': [-100.3, 44.4], 'zoom': 6.3, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    views = sum(len(f['properties']['directions']) for f in feats)
    print(f'South Dakota: {len(feats)} sites ({n_traffic} traffic, {rwis_kept} RWIS; {views} views)')


if __name__ == '__main__':
    main()
