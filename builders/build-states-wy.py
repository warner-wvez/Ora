#!/usr/bin/env python3
"""
Build Wyoming cameras from WYDOT's new 511 map (map.wyoroad.info/511-map).

Snapshot-only. WYDOT's map is an ArcGIS/SvelteKit app that fetches its webcam
layer as a Protocol Buffers blob, not GeoJSON, and lightly obfuscates the text
fields. Two steps to read it, both reproduced here so the build needs no browser:

  1. The layer geometry is
     https://map.wyoroad.info/wti511map-data/Msg-FFBK373B.pbf, a
     `webcameras_v1_pkg.WebCamerasFeed`: repeated Xyz { id=1, name=2,
     images=3 (repeated Image{ id=1, title=2, url=3, sort=4 }), lon=8, lat=9 }.
     We parse it with a tiny field-walker rather than a generated stub.
  2. Every string field (camera name, view title, image URL) is base64 of bytes
     XOR'd with the ASCII key below, lifted verbatim from the map bundle. Decode
     is symmetric, so the same routine reads them back.

Each Xyz is a camera site with one or more lenses, so it becomes one pin with a
view per lens, the Washington multi-view shape. The image URL is
https://www.wyoroad.info/web-cam/cache?ref=<blob>; that ref is a stable handle
(the same one from a week-old capture still resolves), the host is https and
serves a normal JPEG, so no proxy is needed. No HLS is exposed anywhere the
browser can play, so Wyoming is honestly snapshot-only.

If WYDOT rotates the Msg-*.pbf filename (the geometry URL is content-addressed),
re-read it from the running map: it is layer id `webcameras`'s `geometryURL`.
"""
import os, re, json, base64, struct, urllib.request

FEED = 'https://map.wyoroad.info/wti511map-data/Msg-FFBK373B.pbf'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://map.wyoroad.info/511-map/'}
KEY = b'EkhJp6wsgahsqkiw5nahFOSCwAND1zhZ'   # from the 511-map bundle's decode routine
# reject any pin that lands outside Wyoming rather than trusting a bad coordinate
BBOX = (-111.1, 40.9, -104.0, 45.1)  # lon_min, lat_min, lon_max, lat_max


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return r.read()


def dexor(s):
    """base64 -> XOR with KEY -> utf-8, the inverse of the map's field encoder."""
    if not s:
        return ''
    b = base64.b64decode(s)
    return bytes(b[i] ^ KEY[i % len(KEY)] for i in range(len(b))).decode('utf-8', 'replace')


ROUTE = re.compile(r'^\s*(I|US|WYO|WY|Loop|Bus|Alt)\s*0*(\d+[A-Za-z]?)', re.I)


def route_of(title):
    """Lift the leading highway designator from a view title ("I 80 Summit - West"
    -> "I-80") so Wyoming is searchable by road, the way its own map is organized."""
    m = ROUTE.match(title or '')
    if not m:
        return ''
    return f'{m.group(1).upper()}-{m.group(2).upper()}'


def _varint(b, i):
    r = s = 0
    while True:
        x = b[i]; i += 1
        r |= (x & 0x7f) << s
        if not x & 0x80:
            return r, i
        s += 7


def fields(b):
    """Yield (field_number, value) for a protobuf message; value is int, float, or bytes."""
    i = 0
    while i < len(b):
        tag, i = _varint(b, i)
        fn, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = _varint(b, i)
        elif wt == 1:
            v = struct.unpack('<d', b[i:i + 8])[0]; i += 8
        elif wt == 2:
            ln, i = _varint(b, i)
            v = b[i:i + ln]; i += ln
        elif wt == 5:
            v = struct.unpack('<f', b[i:i + 4])[0]; i += 4
        else:
            raise ValueError(f'unsupported wire type {wt}')
        yield fn, v


def main():
    data = get(FEED)
    feats, skipped, views = [], 0, 0
    for fn, xyz in fields(data):
        if fn != 1 or not isinstance(xyz, (bytes, bytearray)):
            continue
        name, lon, lat, images = '', None, None, []
        for f, v in fields(xyz):
            if f == 2 and isinstance(v, (bytes, bytearray)):
                name = dexor(v)
            elif f == 8:
                lon = v
            elif f == 9:
                lat = v
            elif f == 3 and isinstance(v, (bytes, bytearray)):
                title = url = ''
                for g, gv in fields(v):
                    if g == 2 and isinstance(gv, (bytes, bytearray)):
                        title = dexor(gv)
                    elif g == 3 and isinstance(gv, (bytes, bytearray)):
                        url = dexor(gv)
                if url:
                    images.append({'title': title, 'url': url})
        if lon is None or lat is None or not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        roadway = ''
        dirs = []
        for im in images:
            # the view title is "<route> <site> - <lens>"; keep just the lens for the
            # tab, and lift the leading route designator once so the state is
            # searchable by highway ("I-80"), which the site is organized around.
            lbl = im['title']
            if not roadway:
                roadway = route_of(lbl)
            if ' - ' in lbl:
                lbl = lbl.rsplit(' - ', 1)[1]
            elif name and lbl.startswith(name):
                lbl = lbl[len(name):].lstrip(' -')
            dirs.append({'snapshot': im['url'], 'video': None, 'label': lbl.strip()})
        if not dirs:
            dirs = [{'snapshot': None, 'video': None, 'label': ''}]
        views += len([d for d in dirs if d['snapshot']])
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': name or 'Camera', 'kind': 'live',
                                     'directions': dirs, 'roadway': roadway, 'county': ''}})

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/WY.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['WY'] = {'name': 'Wyoming', 'file': 'states/WY.json', 'count': len(feats),
                 'center': [-107.5, 43.0], 'zoom': 6.2, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'Wyoming: {len(feats)} camera sites ({views} views, {skipped} skipped)')


if __name__ == '__main__':
    main()
