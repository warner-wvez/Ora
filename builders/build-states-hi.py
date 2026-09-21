#!/usr/bin/env python3
"""
Build Hawaii cameras from GoAkamai (goakamai.org, HDOT / ICx ATIS).

Hawaii's long-standing blocker was coordinates: the obvious API
(a.cameraservice.goakamai.org/cameratours/<tour>/cameras) lists every camera
with snapshot + HLS but no location, and bare /cameras answers 403 Forbidden.
The unlock is in the site's own config (goakamai.org/data/config.json):
MapDataServiceURLs.cctv points at /cameras?format=mapPage, and the service
accepts the request when it carries the two x-icx-* headers the Vue app always
sends. x-icx-copyright is a constant vendor string and x-icx-ts is just "now in
millis" -- neither is a credential or expires, so this is a fetch recipe, not a
stored secret. That endpoint returns all ~361 cameras WITH lat/lon.

Snapshots: betaimageserver.goakamai.org/SnapShot/320x240/<id>.jpg. The feed
writes them as http:// but the host serves the identical JPEG over https, so
they are upgraded in place and Hawaii needs no image proxy. The API's own
imageRefreshRate is 120s. Note probe-health's placeholder rule was originally
calibrated by this very state: HDOT reports status OK on cameras serving its
"Image Temporarily Unavailable" card, so expect the health sweep to grey out a
chunk of these.

Video: cdn3.wowza.com HLS, no token, no DRM, CORS * on playlist and segments --
but stream rot is real (about half of sampled playlists 404), which is exactly
why the popup's runtime is-it-actually-moving check exists. video_plays_any()
samples more than one stream so the dead half cannot veto the living half.
"""
import json, os, random, time, urllib.request

CONFIG_URL = 'https://goakamai.org/data/config.json'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://goakamai.org/',
        'Origin': 'https://goakamai.org', 'Accept': 'application/json, text/plain, */*',
        'x-icx-copyright': 'ICxTransportationGroup'}
BBOX = (-160.7, 18.5, -154.5, 22.5)


def get_json(url, timeout=45):
    req = urllib.request.Request(url, headers={**HDRS, 'x-icx-ts': str(int(time.time() * 1000))})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def video_plays(url):
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
    cfg = get_json(CONFIG_URL)
    cctv_url = (cfg.get('MapDataServiceURLs') or {}).get('cctv')
    if not cctv_url:
        raise SystemExit('goakamai config no longer names a cctv map service; find the new door')
    cams = get_json(cctv_url)

    feats = []
    for c in cams:
        lat, lon = c.get('lat'), c.get('lon')
        if lat is None or lon is None:
            continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        snap = (c.get('cameraImageURL') or '').strip() or None
        if snap and snap.startswith('http://'):
            snap = 'https://' + snap[len('http://'):]
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': (c.get('description') or c.get('id') or 'Camera').strip(),
                                     'kind': 'live',
                                     'directions': [{'snapshot': snap,
                                                     'video': (c.get('streamingURL') or '').strip() or None,
                                                     'label': ''}],
                                     'roadway': '', 'county': ''}})

    all_vid = [d['video'] for f in feats for d in f['properties']['directions'] if d['video']]
    plays = video_plays_any(all_vid)

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/HI.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['HI'] = {'name': 'Hawaii', 'file': 'states/HI.json', 'count': len(feats),
                 'center': [-157.7, 21.1], 'zoom': 7, 'video': plays}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'HI: {len(feats)} cameras, {len(all_vid)} streams, video={plays}')


if __name__ == '__main__':
    main()
