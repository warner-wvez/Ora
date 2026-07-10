#!/usr/bin/env python3
"""
Build Washington cameras from the WSDOT Traveler Information API.
Requires a free WSDOT AccessCode, read from the WSDOT_API_KEY environment
variable so it never lands in the repo:

  WSDOT_API_KEY=your-key python3 build-states-wa.py

Free key: https://wsdot.wa.gov/traffic/api/

Snapshot-only. WSDOT serves refreshing JPEGs from images.wsdot.wa.gov; there is
no HLS anywhere in the product, and the images carry no CORS header, so nothing
about them can be read from the browser at runtime.

Two per-view properties that no other Ora state carries, both from WSDOT itself:

  facing       CameraLocation.Direction, a single letter. WSDOT's own road-alert
               feed spells the identical vocabulary out in full ("Northbound",
               "Both Directions"), which is where FACING below comes from. It is
               the direction of travel the camera covers, not a compass bearing.
  refresh_sec  How often the camera really replaces its JPEG. WSDOT publishes no
               such field anywhere, so measure-refresh-wa.py derives it from the
               Last-Modified header into states/WA-refresh.json. Optional: without
               that file the build still runs and the map falls back to the
               generic per-state wording.

188 cameras sit on 47 shared coordinates (a ferry terminal points three cameras
at one holding lane). Stacked pins are unclickable, so those collapse into one
feature with several `directions`, which is what that array is for. Both fields
above therefore hang off each direction, not off the location.

Three exclusions, all deliberate:

  * tripcheck.com images are ODOT's cameras, which WSDOT redistributes. 61 of
    the 65 already appear in Ora's Oregon layer; the other 4 are Portland.
  * RoadName == 'Airports' is WSDOT Aviation's airfield webcams (fuel pumps,
    gates), not road cameras.
  * a loose bounding box, purely as a guard against a future bad row.

Do NOT filter this state with states-outline.json. That outline is far too
coarse: it places every Whidbey, Vashon and Anacortes ferry camera, and the
entire Vancouver riverbank, outside Washington. Point-in-polygon against it
silently deletes 67 real cameras and nothing errors.
"""
import os, json, urllib.request, collections

KEY = os.environ.get('WSDOT_API_KEY')
if not KEY:
    raise SystemExit('Set WSDOT_API_KEY (free key at https://wsdot.wa.gov/traffic/api/)')

API = ('https://wsdot.wa.gov/Traffic/api/HighwayCameras/HighwayCamerasREST.svc'
       f'/GetCamerasAsJson?AccessCode={KEY}')
# WSDOT's own alerts feed spells these out; the camera feed abbreviates them.
FACING = {'N': 'Northbound', 'S': 'Southbound', 'E': 'Eastbound',
          'W': 'Westbound', 'B': 'Both directions', 'O': 'Other'}
# the popup is 264px wide and a mast can hold five views, so buttons get the short tag
SHORT = {'Northbound': 'NB', 'Southbound': 'SB', 'Eastbound': 'EB',
         'Westbound': 'WB', 'Both directions': 'Both', 'Other': 'Other'}
BBOX = (-125.0, 45.5, -116.5, 49.1)   # generous; the real filters are above


def shared_name(names):
    """Longest common prefix, never cut mid-word. Three cameras called
    'WSF Lopez Ferry Holding Looking {North,South}' and '... Middle' name one
    location, 'WSF Lopez Ferry Holding'. Falls back to a real camera title when
    the cameras share too little to name the place."""
    if len(set(names)) == 1:                   # a 5-preset PTZ mast: every view has one title
        return names[0]
    pre = os.path.commonprefix(names)
    if pre and not pre[-1].isspace():          # 'WSF Clinton ' is a boundary, 'Winslow Way' is not
        pre = pre[:pre.rfind(' ') + 1] if ' ' in pre else ''
    pre = pre.strip(' :-@')
    return pre if len(pre) >= 8 else names[0]


def tabs_for(labels, facings):
    """One button per view, always unique and never blank. Prefer the part of the
    camera's own title that differs; fall back to a short compass tag; number any
    that still collide, because a mast can aim two cameras the same way."""
    base = [l or SHORT.get(f) or 'View' for l, f in zip(labels, facings)]
    total, seen, out = collections.Counter(base), collections.Counter(), []
    for b in base:
        seen[b] += 1
        out.append(f'{b} {seen[b]}' if total[b] > 1 else b)
    return out


def main():
    req = urllib.request.Request(API, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        cams = json.loads(r.read())

    rates = {}
    if os.path.exists('states/WA-refresh.json'):
        rates = json.load(open('states/WA-refresh.json'))['cameras']

    keep, drop = [], collections.Counter()
    for c in cams:
        url = c.get('ImageURL') or ''
        lng, lat = c.get('DisplayLongitude'), c.get('DisplayLatitude')
        # location-first: keep inactive and image-less cameras; drop only rows with no coordinate
        if lat is None or lng is None:
            drop['nocoord'] += 1; continue
        if 'tripcheck.com' in url.lower():
            drop['oregon'] += 1; continue
        if c['CameraLocation'].get('RoadName') == 'Airports':
            drop['airport'] += 1; continue
        if not (BBOX[0] <= lng <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            drop['bbox'] += 1; continue
        keep.append(c)

    at = collections.defaultdict(list)
    for c in keep:
        at[(c['DisplayLongitude'], c['DisplayLatitude'])].append(c)

    feats = []
    for (lng, lat), group in at.items():
        group.sort(key=lambda c: c['Title'])
        names = [(c.get('Title') or 'Camera').strip() for c in group]
        name = shared_name(names)
        facings = [FACING.get(c['CameraLocation'].get('Direction')) for c in group]
        # what is left of a camera's own name once the shared part is gone is what
        # tells the views apart: "Looking South", "Uphill", "Terminal"
        labels = [''] * len(group)
        if len(group) > 1:
            labels = tabs_for([n[len(name):].strip(' :-@') if n.startswith(name) else ''
                               for n in names], facings)
        dirs = []
        for c, facing, label in zip(group, facings, labels):
            d = {'snapshot': c.get('ImageURL') or None, 'video': None, 'label': label}
            if facing:
                d['facing'] = facing
            m = rates.get(str(c['CameraID']), {})
            for k in ('refresh_sec', 'stale_since'):
                if k in m:
                    d[k] = m[k]
            dirs.append(d)
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                      'properties': {'name': name, 'kind': 'live', 'directions': dirs,
                                     'roadway': (group[0]['CameraLocation'].get('RoadName') or '').strip(),
                                     'county': ''}})

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/WA.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['WA'] = {'name': 'Washington', 'file': 'states/WA.json', 'count': len(keep),
                 'center': [-120.5, 47.4], 'zoom': 6.3, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)

    alld = [d for f in feats for d in f['properties']['directions']]
    timed = sum(1 for d in alld if 'refresh_sec' in d)
    stale = sum(1 for d in alld if 'stale_since' in d)
    faced = sum(1 for d in alld if 'facing' in d)
    print(f'Washington: {len(keep)} cameras at {len(feats)} locations '
          f'({faced} with a facing, {timed} with a measured refresh, {stale} stale)')
    print(f'  dropped: {drop["oregon"]} ODOT/tripcheck, {drop["airport"]} airport, '
          f'{drop["bbox"]} out of bbox, {drop["nocoord"]} without coordinates')
    if not rates:
        print('  no states/WA-refresh.json yet; run measure-refresh-wa.py, then rebuild')


if __name__ == '__main__':
    main()
