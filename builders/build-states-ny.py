#!/usr/bin/env python3
"""
Build New York cameras from 511NY's CARS 511x map (api-511x-nysdot.carsprogram.org).

511ny.org left the shared DataTables platform (build-states.py) around 2026-09-30.
The old /map/Cctv/<id> snapshot path now answers every camera with the new site's
HTML page, so every New York snapshot went dark at once while video kept playing.
The probe-health sweep read that as 100% offline and skipped New York, which left the
map showing the last good health file from September.

The new site loads its camera layer from one open GET, <api>/cameras/map-features
(the layer's `api` in demo.511ny.org/configs/main.json, plus the suffix the site's
bundle appends). It is GeoJSON with Access-Control-Allow-Origin *, one view per
camera, and two owners:
  NYSDOT   HLS on s*.nysdot.skyvdn.com (token-free, CORS-open), and a live preview
           JPEG at public.carsprogram.org/cameras/NYSDOT/<stream>.flv.png that
           answers Range requests with the true size, so the health sweep works.
  NYC DOT  stills on nyctmc.org. Skipped: the New York City layer
           (cameras-nyc.json) already carries 959 of these 992 cameras.

The new feed has no direction column, and the old one gave 1,248 views a compass
chip. Which way a camera looks does not change when the website does, so the chip
is carried forward from the previous states/NY.json, keyed by the stream name
(R4_001), which is the one identifier both platforms share.

Usage (from the repo root): python3 builders/build-states-ny.py
"""
import gzip, json, os, random, re, urllib.request

API = 'https://api-511x-nysdot.carsprogram.org/cameras/map-features'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'}
OWNER = 'NYSDOT'
# null island and a lost minus sign, the same box the DataTables build used
BBOX = (-79.77, 40.47, -71.85, 45.02)  # lon_min, lat_min, lon_max, lat_max
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


def previous_facing():
    if not os.path.exists('states/NY.json'):
        return {}
    out = {}
    for f in json.load(open('states/NY.json'))['features']:
        for d in f['properties']['directions']:
            s = stream_of(d.get('video'))
            if s and d.get('facing'):
                out[s] = d['facing']
    return out


def main():
    facing = previous_facing()
    feats, hls, skipped = [], [], 0
    for f in json.loads(get(API))['features']:
        p = f['properties']
        if p.get('cameraOwner') != OWNER:
            continue
        lon, lat = f['geometry']['coordinates'][:2]
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
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
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/NY.json', 'w'))
    index = json.load(open('states/index.json'))
    # a relay or sign field is decided by hand and must survive a rebuild
    keep = {k: index['NY'][k] for k in ('relay', 'sign') if k in index.get('NY', {})}
    index['NY'] = {'name': 'New York', 'file': 'states/NY.json', 'count': len(feats),
                   'center': [-75.5, 42.9], 'zoom': 6.3, 'video': plays, **keep}
    json.dump(index, open('states/index.json', 'w'), indent=1)
    chips = sum(1 for f in feats for d in f['properties']['directions'] if d.get('facing'))
    print(f'NY: {len(feats)} cameras, {len(hls) if plays else 0} with live video, '
          f'{chips} facing chips carried forward, {skipped} outside the bbox')


if __name__ == '__main__':
    main()
