#!/usr/bin/env python3
"""
Build Michigan cameras from MDOT's Mi Drive map (mdotjboss.state.mi.us).

Snapshot-only. Mi Drive publishes no HLS/RTSP anywhere the browser can reach;
every camera is a periodically-refreshed still, so Michigan is a normal snapshot
state: health file, grey dead pins, the works.

  * /MiDrive/camera/AllForMap/  returns one row per camera with lat/lon, id,
    title, and a `weatherId`. The list endpoint does NOT carry the image URL, so
    we fold in the per-camera detail:
  * /MiDrive/camera/getCameraInformation/<id> returns the same row plus `link`
    (the snapshot URL) and `weatherText` (an HTML table of RWIS readings, present
    only on the road-weather cameras). Traffic cameras live on
    micamerasimages.net/thumbs/<name>.flv.jpg; RWIS cameras on
    mdotjboss.state.mi.us/docs/drive/camfiles/rwis/<id>.jpg.

Both image hosts are https and answer a ranged GET, so no proxy and no CORS
special-casing is needed (snapshots render through a plain <img>, and the health
sweep fetches them server-side). The RWIS still-image host is the same jboss box
that serves the API, so it is up whenever the map is.

`orientation` is a full sentence ("Traffic closest to camera is traveling
south."), not a compass token, so we surface it as the camera's caption rather
than trying to force it into the Northbound/Southbound chip vocabulary.
"""
import os, re, json, html, urllib.request, concurrent.futures
from collections import OrderedDict

ALLFORMAP = 'https://mdotjboss.state.mi.us/MiDrive/camera/AllForMap/'
DETAIL = 'https://mdotjboss.state.mi.us/MiDrive/camera/getCameraInformation/{}'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://mdotjboss.state.mi.us/MiDrive/map'}
# reject any pin that lands outside Michigan rather than trusting a bad coordinate
BBOX = (-90.5, 41.6, -82.3, 48.4)  # lon_min, lat_min, lon_max, lat_max
TAG = re.compile(r'<[^>]+>')


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def rwis_text(weather_html):
    """Flatten MDOT's <table> of readings into 'Air Temp: 71.0F  Humidity: 77.0%'."""
    if not weather_html:
        return ''
    txt = html.unescape(TAG.sub(' ', weather_html))
    txt = txt.replace('\xa0', ' ')
    parts = [p.strip() for p in re.split(r'\s{2,}', txt) if p.strip()]
    # rejoin "Label:" with the value that follows it
    out, i = [], 0
    while i < len(parts):
        if parts[i].endswith(':') and i + 1 < len(parts):
            out.append(parts[i] + ' ' + parts[i + 1]); i += 2
        else:
            out.append(parts[i]); i += 1
    return ' · '.join(out)


def detail(cam):
    try:
        return get(DETAIL.format(cam['id']))
    except Exception:
        return None


def main():
    cams = get(ALLFORMAP)
    skipped, rwis_cams = 0, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        details = list(ex.map(detail, cams))

    # Mi Drive lists some cameras twice ("I-275 @ M-14" and "I-275 @ M14") on one
    # coordinate; stacked map pins are unclickable, so group by location and keep one
    # view per distinct snapshot -- a true duplicate collapses to one, a genuinely
    # co-located pair becomes a tabbed pin.
    groups = OrderedDict()
    for base, det in zip(cams, details):
        d = det or base
        lat, lon = d.get('latitude'), d.get('longitude')
        snap = (d.get('link') or '').strip() or None
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            skipped += 1; continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        # strip the ?item=/?random= cache-buster; the app re-adds one at render time
        if snap:
            snap = snap.split('?')[0]
        key = (round(lon, 6), round(lat, 6))
        groups.setdefault(key, []).append(d)

    feats = []
    for (lon, lat), members in groups.items():
        dirs, seen, rwis = [], set(), None
        for d in members:
            snap = (d.get('link') or '').strip() or None
            if snap:
                snap = snap.split('?')[0]
            if snap in seen:
                continue
            seen.add(snap)
            dirs.append({'snapshot': snap, 'video': None, 'label': (d.get('orientation') or '').strip()})
            rwis = rwis or rwis_text(d.get('weatherText'))
        title = (members[0].get('title') or 'Camera').strip()
        roadway = title.split('@')[0].strip() if '@' in title else ''
        props = {'name': title, 'kind': 'live', 'directions': dirs, 'roadway': roadway, 'county': ''}
        if rwis:
            props['rwis'] = rwis
            rwis_cams += 1
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': props})

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/MI.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['MI'] = {'name': 'Michigan', 'file': 'states/MI.json', 'count': len(feats),
                 'center': [-85.4, 44.3], 'zoom': 6, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'Michigan: {len(feats)} pins ({skipped} skipped); {rwis_cams} with RWIS weather')


if __name__ == '__main__':
    main()
