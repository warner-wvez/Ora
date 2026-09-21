#!/usr/bin/env python3
"""
Build New Mexico cameras from NMRoads (NMDOT).

Snapshot-only. NMRoads streams video over RTMP (rtmp://video.nmroads.com), which
no browser plays, so we take the still image every camera also publishes and
ignore the stream. That makes New Mexico a normal snapshot state: it gets a
health file, greys dead pins, the works.

Two feeds, joined by name:

  * GetCameraInfo returns cameraInfo[], one row per camera, with lat/lon, title,
    a `snapshotFile` URL, and a `cameraType`. Types seen: iDome, Pelco Spectra,
    "" and RWIS2. The RWIS2 rows are the road-weather stations; they carry a
    camera exactly like the others, so we keep them alongside the traffic cameras
    rather than dropping them.
  * GetCachedObject?key=RWISData returns [{name, text}] where text is a block like
    "Temperature: 81.3 F  Humidity: 23%  Pressure: 789.4 hPa\nWind: W at 3.1 MPH".
    We attach it to the RWIS cameras it matches by name (8 of 9 match; some read
    n/a for temperature or humidity while wind is filled, which we keep as-is).

THE TRAP: snapshotFile is http://ss.nmroads.com, and that host has no HTTPS at
all (port 443 refuses the connection). Ora is served over https, so the browser
blocks the image as mixed content and every pin goes blank. We keep the honest
http origin URL in the data anyway, because:

  * the health sweep runs server-side in Python, where mixed content is a
    non-issue, and it must fingerprint the real bytes off the origin, not a proxy
    that might re-encode them; and
  * index.html carries the state's `imgproxy: "wsrv"` flag and rewrites the image
    through an https proxy only at render time, so the data and the health file
    stay keyed by the true URL and keep matching each other.

Both feeds are JSONP; we add a callback name and strip the wrapper.
"""
import os, re, json, urllib.request

CAMERAS = 'https://servicev5.nmroads.com/RealMapWAR/GetCameraInfo'
RWIS = 'https://servicev4admin.nmroads.com/RealMapWAR/GetCachedObject?key=RWISData'
HDRS = {'Referer': 'https://nmroads.com/', 'User-Agent': 'Mozilla/5.0'}
# reject any pin that lands outside New Mexico rather than trusting a bad coordinate
BBOX = (-109.2, 31.2, -102.9, 37.1)  # lon_min, lat_min, lon_max, lat_max
JSONP = re.compile(r'^[^(]*\(|\);?\s*$')


def get_jsonp(url):
    sep = '&' if '?' in url else '?'
    req = urllib.request.Request(url + sep + 'callback=cb', headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode('utf-8', 'replace')
    return json.loads(JSONP.sub('', body))


def clean_rwis(text):
    # drop the leading "<timestamp>  <station id>" line, keep the weather readings
    lines = [ln.strip() for ln in (text or '').replace('\r', '').split('\n') if ln.strip()]
    weather = [ln for ln in lines if re.search(r'temp|humid|wind|pressure|precip|visib', ln, re.I)]
    return ' · '.join(weather)


def main():
    cams = get_jsonp(CAMERAS).get('cameraInfo', [])
    rwis = {r['name']: clean_rwis(r.get('text')) for r in get_jsonp(RWIS) if r.get('name')}

    feats, skipped, rwis_cams, rwis_with_data = [], 0, 0, 0
    for c in cams:
        snap, lat, lon = c.get('snapshotFile'), c.get('lat'), c.get('lon')
        if not c.get('enabled') or c.get('mobile') or not snap:
            skipped += 1; continue
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            skipped += 1; continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        title = (c.get('title') or c.get('name') or '').strip()
        roadway = title.split('@')[0].strip() if '@' in title else ''
        props = {'name': title, 'kind': 'live',
                 'directions': [{'snapshot': snap, 'video': None, 'label': ''}],
                 'roadway': roadway, 'county': (c.get('grouping') or '').strip()}
        if c.get('cameraType') in ('RWIS', 'RWIS2'):
            rwis_cams += 1
            text = rwis.get(c.get('name'))
            if text:
                props['rwis'] = text
                rwis_with_data += 1
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': props})

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/NM.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['NM'] = {'name': 'New Mexico', 'file': 'states/NM.json', 'count': len(feats),
                 'center': [-106.1, 34.4], 'zoom': 6.2, 'video': False, 'imgproxy': 'wsrv'}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'New Mexico: {len(feats)} cameras ({skipped} skipped); '
          f'{rwis_cams} RWIS, {rwis_with_data} with weather')


if __name__ == '__main__':
    main()
