#!/usr/bin/env python3
"""
Build Maryland cameras from CHART (chart.maryland.gov, MDOT SHA).

No HAR was needed: CHART's export service is simply open. GET
https://chartexp1.sha.maryland.gov/CHARTExportClientService/getCameraMapDataJSON.do
returns all ~553 cameras with lat/lon, description, and per-camera streaming
host (cctvIp: strmr3/strmr5/strmr10.sha.maryland.gov). The public video page
(chart.maryland.gov/Video/GetVideo/<id>) builds its player source as
https://<cctvIp>/rtplive/<id>/playlist.m3u8 -- Wowza HLS, no token, no DRM,
Access-Control-Allow-Origin: * on playlist and segments alike.

Maryland is VIDEO-ONLY, like Texas and West Virginia: neither CHART nor the
Wowza hosts expose any still/thumbnail endpoint (the Wowza /thumbnail API is
disabled, CHART's own player uses a generic offline.jpg poster). Popups play
the stream over a dark backdrop, and the runtime is-the-picture-moving check
covers dead streams.
"""
import json, os, random, urllib.request

EXPORT = 'https://chartexp1.sha.maryland.gov/CHARTExportClientService/getCameraMapDataJSON.do'
HDRS = {'User-Agent': 'Mozilla/5.0'}
# Maryland plus its Potomac bridge approaches; rejects bad coordinates, not neighbours
BBOX = (-79.6, 37.8, -74.9, 39.9)


def get_json(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
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
    resp = get_json(EXPORT)
    cams = resp.get('data') or []
    feats = []
    for c in cams:
        lat, lon = c.get('lat'), c.get('lon')
        host, cid = c.get('cctvIp'), c.get('id')
        if lat is None or lon is None or not host or not cid:
            continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        # description carries the fuller human name ("I-270 & Old Hundred Rd (MD 109)(CAM 165)");
        # name alone is sometimes just a device number
        name = (c.get('description') or c.get('name') or 'Camera').strip()
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': name, 'kind': 'live',
                                     'directions': [{'snapshot': None,
                                                     'video': f'https://{host}/rtplive/{cid}/playlist.m3u8',
                                                     'label': ''}],
                                     'roadway': f"{c.get('routePrefix') or ''}-{c.get('routeNumber')}".strip('-')
                                                if c.get('routeNumber') else '',
                                     'county': ''}})

    all_vid = [d['video'] for f in feats for d in f['properties']['directions'] if d['video']]
    plays = video_plays_any(all_vid)

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/MD.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['MD'] = {'name': 'Maryland', 'file': 'states/MD.json', 'count': len(feats),
                 'center': [-77.2, 39.2], 'zoom': 7.2, 'video': plays}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'MD: {len(feats)} cameras, video={plays} (video-only, no still endpoint)')


if __name__ == '__main__':
    main()
