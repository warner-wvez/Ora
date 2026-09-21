#!/usr/bin/env python3
"""
Build South Carolina cameras from SCDOT's 511 map (511sc.org), which runs on
Iteris' ATIS platform like South Dakota -- same icons.cameras.geojson layout on
the state's CDN (sc.cdn.iteris-atis.com), so build-states-sd.py was the template.

Unlike South Dakota, this one is LIVE VIDEO. Every row carries a per-camera
Wowza HLS URL (https_url on s1x.us-east-1.skyvdn.com/rtplive/<id>/playlist.m3u8):
no token, no DRM, and Access-Control-Allow-Origin: * on the playlist, the
chunklist, and the .ts segments alike, so hls.js can play it from a static page.
The build still samples streams and refuses token= / #EXT-X-KEY, per the house
rules Kansas and Alabama earned.

Each row also carries a snapshot (scdotsnap.us-east-1.skyvdn.com/thumbs/<id>.flv.png,
fresh within seconds on every sample), which becomes the popup poster the way
the other video states work. The feed's direction column is terse ("SB") and is
expanded to the chip vocabulary the rest of the map uses.
"""
import json, gzip, os, random, time, urllib.request, zlib

CAMERAS = 'https://sc.cdn.iteris-atis.com/geojson/icons/metadata/icons.cameras.geojson'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.511sc.org/', 'Accept-Encoding': 'gzip, deflate'}
# reject any pin that lands outside South Carolina rather than trusting a bad coordinate
BBOX = (-83.4, 32.0, -78.5, 35.3)  # lon_min, lat_min, lon_max, lat_max

FACING = {'nb': 'Northbound', 'sb': 'Southbound', 'eb': 'Eastbound', 'wb': 'Westbound',
          'n': 'Northbound', 's': 'Southbound', 'e': 'Eastbound', 'w': 'Westbound'}


def get(url, timeout=60, tries=4):
    # same iteris CDN family as SD: gzipped bodies, and SD's edge once served a
    # truncated body, so retry instead of shipping half a state
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
                b = r.read()
                enc = r.headers.get('Content-Encoding', '')
                if enc == 'gzip' or b[:2] == b'\x1f\x8b':
                    b = gzip.decompress(b)
                elif enc == 'deflate':
                    b = zlib.decompress(b)
                return json.loads(b.decode('utf-8', 'replace'))
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(2 * (i + 1))
    raise RuntimeError(f'SC feed unreadable after {tries} tries: {last}')


def video_plays(url):
    """CORS-open on the playlist, and no DRM in the chunklist (Alabama's lesson),
    and no short-lived credential (Kansas's lesson)."""
    if not url or 'token=' in url:
        return False
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Origin': 'http://localhost'})
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.headers.get('Access-Control-Allow-Origin') not in ('*', 'http://localhost'):
                return False
            playlist = r.read().decode('utf-8', 'replace')
        media = [l for l in playlist.splitlines() if l and not l.startswith('#')]
        if not media:
            return False
        with urllib.request.urlopen(urllib.request.Request(
                url.rsplit('/', 1)[0] + '/' + media[0],
                headers={'User-Agent': 'Mozilla/5.0'}), timeout=12) as r:
            chunklist = r.read().decode('utf-8', 'replace')
        return not any(l.startswith('#EXT-X-KEY') for l in chunklist.splitlines())
    except Exception:
        return False


def video_plays_any(urls, n=8):
    urls = [u for u in urls if u]
    if not urls:
        return False
    return any(video_plays(u) for u in random.sample(urls, min(n, len(urls))))


def main():
    feats = []
    for f in get(CAMERAS).get('features', []):
        p = f.get('properties') or {}
        coords = (f.get('geometry') or {}).get('coordinates')
        if not coords or len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        d = {'snapshot': (p.get('image_url') or '').strip() or None,
             'video': (p.get('https_url') or '').strip() or None, 'label': ''}
        facing = FACING.get((p.get('direction') or '').strip().lower())
        if facing:
            d['facing'] = facing
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': (p.get('description') or p.get('name') or 'Camera').strip(),
                                     'kind': 'live', 'directions': [d],
                                     'roadway': (p.get('route') or '').strip(),
                                     'county': (p.get('jurisdiction') or '').strip()}})

    all_vid = [d['video'] for f in feats for d in f['properties']['directions'] if d['video']]
    plays = video_plays_any(all_vid)

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/SC.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['SC'] = {'name': 'South Carolina', 'file': 'states/SC.json', 'count': len(feats),
                 'center': [-80.9, 33.9], 'zoom': 6.8, 'video': plays}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'SC: {len(feats)} cameras, {len(all_vid)} with HLS, video={plays}')


if __name__ == '__main__':
    main()
