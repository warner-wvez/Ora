#!/usr/bin/env python3
"""
Build cameras for states on Castle Rock's CARS 511x map (api-511x-<agency>.carsprogram.org).

New York moved here from the DataTables platform (build-states.py) around 2026-09-30, and
Colorado from the GraphQL platform (build-states-graphql.py) in October 2026. On both, the
old site's endpoints began answering with the new site's HTML page. New York's old snapshot
path did that for every camera at once, and the health sweep skipped the state as 100%
offline, which left the map showing September's health.

The new site loads its camera layer from one open GET, <api>/map-features (the cameras
layer's `api` in the site's configs/main.json, plus the suffix the site's bundle appends).
It is GeoJSON with Access-Control-Allow-Origin *, one or more views per camera:
  WMP          HLS (token-free, CORS-open on both states), plus a live preview JPEG at
               public.carsprogram.org or cocam.carsprogram.org that answers Range requests
               with the true size, so the health sweep works.
  STILL_IMAGE  a snapshot url and nothing else.

New York's feed also carries NYC DOT's 992 stills; they are skipped because the New York
City layer (cameras-nyc.json) already carries 959 of them.

The new feed has no direction column, and New York's old one gave 1,248 views a compass
chip. Which way a camera looks does not change when the website does, so for New York the
chip is carried forward from the previous states/NY.json, keyed by the stream name
(R4_001), which is the one identifier both platforms share. Colorado never had chips.

Usage (from the repo root): python3 builders/build-states-511x.py          # every state
                            python3 builders/build-states-511x.py NY       # just these
"""
import gzip, json, os, random, re, sys, urllib.request

STATES = {
    # owners: keep only these cameraOwner values (None keeps every owner)
    'NY': {'api': 'https://api-511x-nysdot.carsprogram.org/cameras', 'name': 'New York',
           'center': [-75.5, 42.9], 'zoom': 6.3, 'owners': {'NYSDOT'}, 'carry_facing': True,
           'bbox': (-79.77, 40.47, -71.85, 45.02)},
    'CO': {'api': 'https://api-511x-co.carsprogram.org/cameras', 'name': 'Colorado',
           'center': [-105.5, 39.0], 'zoom': 6, 'owners': None, 'carry_facing': False,
           'bbox': (-109.2, 36.8, -101.9, 41.2)},
}
HDRS = {'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'}
STREAM = re.compile(r'/rtplive/([^/]+)/playlist\.m3u8')


def get(url, timeout=90):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        b = r.read()
        if r.headers.get('Content-Encoding') == 'gzip' or b[:2] == b'\x1f\x8b':
            b = gzip.decompress(b)
        return b.decode('utf-8', 'replace')


def video_plays(url):
    """Refuse a signed URL, a stream the browser may not read, and DRM behind green CORS."""
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
        chunklist = urllib.request.urlopen(urllib.request.Request(
            url.rsplit('/', 1)[0] + '/' + media[0], headers={'User-Agent': 'Mozilla/5.0'}), timeout=12).read()
        return b'#EXT-X-KEY' not in chunklist
    except Exception:
        return False


def video_plays_any(urls, n=8):
    # about 5% of cameras are down at any moment, so one dead sample must not decide the state
    urls = [u for u in urls if u]
    return bool(urls) and any(video_plays(u) for u in random.sample(urls, min(n, len(urls))))


def stream_of(url):
    m = STREAM.search(url or '')
    return m.group(1) if m else None


def previous_facing(code):
    path = f'states/{code}.json'
    if not os.path.exists(path):
        return {}
    out = {}
    for f in json.load(open(path))['features']:
        for d in f['properties']['directions']:
            s = stream_of(d.get('video'))
            if s and d.get('facing'):
                out[s] = d['facing']
    return out


def build(code, cfg):
    facing = previous_facing(code) if cfg['carry_facing'] else {}
    bbox, feats, hls, skipped = cfg['bbox'], [], [], 0
    for f in json.loads(get(cfg['api'] + '/map-features'))['features']:
        p = f['properties']
        if cfg['owners'] and p.get('cameraOwner') not in cfg['owners']:
            continue
        lon, lat = f['geometry']['coordinates'][:2]
        if not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
            skipped += 1
            continue
        dirs = []
        for v in p.get('views') or []:
            video = v.get('url') if v.get('type') == 'WMP' else None
            d = {'snapshot': v.get('videoPreviewUrl') or (None if video else v.get('url')),
                 'video': video, 'label': ''}
            if facing.get(stream_of(video)):
                d['facing'] = facing[stream_of(video)]
            if video:
                hls.append(video)
            dirs.append(d)
        # location-first: a camera with no usable view still marks a spot
        if not dirs:
            dirs = [{'snapshot': None, 'video': None, 'label': ''}]
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': (p.get('name') or 'Camera').strip(), 'kind': 'live',
                                     'directions': dirs, 'roadway': (p.get('route') or '').strip(),
                                     'county': ''}})
    plays = video_plays_any(hls)
    if not plays:
        for f in feats:
            for d in f['properties']['directions']:
                d['video'] = None
    chips = sum(1 for f in feats for d in f['properties']['directions'] if d.get('facing'))
    return feats, plays, len(hls) if plays else 0, chips, skipped


def main():
    want = {c.upper() for c in sys.argv[1:]}
    if want - set(STATES):
        raise SystemExit(f'unknown state(s): {sorted(want - set(STATES))}')
    index = json.load(open('states/index.json'))
    for code, cfg in STATES.items():
        if want and code not in want:
            continue
        feats, plays, vids, chips, skipped = build(code, cfg)
        json.dump({'type': 'FeatureCollection', 'features': feats}, open(f'states/{code}.json', 'w'))
        # a relay or sign field is decided by hand and must survive a rebuild
        keep = {k: index[code][k] for k in ('relay', 'sign') if k in index.get(code, {})}
        index[code] = {'name': cfg['name'], 'file': f'states/{code}.json', 'count': len(feats),
                       'center': cfg['center'], 'zoom': cfg['zoom'], 'video': plays, **keep}
        print(f'{code}: {len(feats)} cameras, {vids} with live video, '
              f'{chips} facing chips carried forward, {skipped} outside the bbox')
    json.dump(index, open('states/index.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
