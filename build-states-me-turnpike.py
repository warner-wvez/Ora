#!/usr/bin/env python3
"""
Append the Maine Turnpike's cameras to states/ME.json.

The Maine Turnpike Authority (maineturnpike.com) runs its own cameras that are
NOT in newengland511.org's Maine feed. Its map page hardcodes everything in
/assets/js/map.js: a `locations` array (id, name, lat, lng) where ids >= 500
are the camera mileposts, and an if/else chain assigning each id up to three
JPEG views (imagetouseNORTH/SOUTH/EAST) under /cameras/. The images are live
snapshots -- Last-Modified tracks within a minute of now -- refreshed on the
page with a random-number cache-buster. No video is published anywhere on the
site, so these are snapshot views like the rest of Maine.

Run AFTER `python3 build-states.py ME` (which writes states/ME.json wholesale).
Idempotent: any existing maineturnpike.com features are dropped before
appending, so running it twice cannot duplicate pins.
"""
import json, os, re, urllib.parse, urllib.request

MAPJS = 'https://www.maineturnpike.com/assets/js/map.js?v=8'
IMGBASE = 'https://www.maineturnpike.com/cameras/'
HDRS = {'User-Agent': 'Mozilla/5.0'}
BBOX = (-71.2, 42.9, -66.8, 47.6)

# hand-edited JS: some longitudes read "- 70.6" (space after the minus) and one
# row has a bare '-' for a coordinate, so: optional minus, optional space, digits
LOC = re.compile(r"\{\s*'id':\s*(\d+),\s*'name':\s*'([^']*)'.*?'lat':\s*(-?\s*\d+\.\d+),\s*'lng':\s*(-?\s*\d+\.\d+)", re.S)
ASSIGN = re.compile(r"if \(id == (\d+)\)\s*\{([^}]*)\}")
IMG = re.compile(r"imagetouse(NORTH|SOUTH|EAST)\s*=\s*\"([^\"]+)\"")
FACING = {'NORTH': 'Northbound', 'SOUTH': 'Southbound', 'EAST': 'Eastbound'}


def get(url, timeout=45):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def main():
    js = get(MAPJS)
    locs = {int(m.group(1)): (m.group(2), float(m.group(3).replace(' ', '')), float(m.group(4).replace(' ', '')))
            for m in LOC.finditer(js)}
    feats = []
    for m in ASSIGN.finditer(js):
        cam_id = int(m.group(1))
        if cam_id not in locs:
            continue
        name, lat, lng = locs[cam_id]
        if not (BBOX[0] <= lng <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        dirs = []
        for im in IMG.finditer(m.group(2)):
            fn = im.group(2).strip()
            if not fn:
                continue
            dirs.append({'snapshot': IMGBASE + urllib.parse.quote(fn), 'video': None,
                         'label': FACING[im.group(1)], 'facing': FACING[im.group(1)]})
        if not dirs:
            continue
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                      'properties': {'name': f'Maine Turnpike {name}', 'kind': 'live',
                                     'directions': dirs, 'roadway': 'I-95 (Maine Turnpike)', 'county': ''}})
    if not feats:
        raise SystemExit('parsed no turnpike cameras: map.js layout changed, not touching ME')

    me = json.load(open('states/ME.json'))
    kept = [f for f in me['features']
            if 'maineturnpike.com' not in json.dumps(f['properties']['directions'])]
    me['features'] = kept + feats
    json.dump(me, open('states/ME.json', 'w'))
    idx = json.load(open('states/index.json'))
    idx['ME']['count'] = len(me['features'])
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    views = sum(len(f['properties']['directions']) for f in feats)
    print(f'ME: appended {len(feats)} Maine Turnpike sites ({views} views); state now {len(me["features"])} pins')


if __name__ == '__main__':
    main()
