#!/usr/bin/env python3
"""
Build West Virginia cameras from WV511 (wv511.org, WVDOH).

Live video. WV511's Google-Maps front end pulls its camera markers from
/wsvc/gmap.asmx/buildCamerasJSONjs, a .asmx web method that answers with a
JavaScript file: marker-cluster styling followed by a JSON array literal of
cameras. We slice out that array and read it directly.

Each camera row: { origin, md5 (the CAM id), title (road), description (an HTML
blob whose first cell is the human location), start_lat, start_lng }. There is no
still image field -- the description's <img> points at /images/cam_unavailable.jpg
-- so West Virginia is video-only, like Texas: its popup plays the HLS stream over
a dark backdrop instead of a poster.

The stream is https://vtc1.roadsummary.com/rtplive/<CAMID>/playlist.m3u8, a Wowza
edge that returns Access-Control-Allow-Origin: * on the playlist AND the segments,
with no token, so it plays cross-origin from a static page. We still sample real
streams and only set video=True if one actually plays (house rule: one dead
camera must not decide a whole state, and a signed/expiring URL is refused).
"""
import os, re, json, random, urllib.request

FEED = 'https://wv511.org/wsvc/gmap.asmx/buildCamerasJSONjs'
STREAM = 'https://vtc1.roadsummary.com/rtplive/{}/playlist.m3u8'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://wv511.org/'}
# reject any pin that lands outside West Virginia rather than trusting a bad coordinate
BBOX = (-82.8, 37.1, -77.6, 40.7)  # lon_min, lat_min, lon_max, lat_max
CAMDESC = re.compile(r'camDescription">([^<]+)')
TAG = re.compile(r'<[^>]+>')


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def video_plays(url):
    """Usable only if the stream host allows cross-origin playback and carries no
    short-lived credential (a token cannot live in a static JSON file)."""
    if not url or 'token=' in url:
        return False
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Origin': 'http://localhost'})
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.headers.get('Access-Control-Allow-Origin') in ('*', 'http://localhost')
    except Exception:
        return False


def video_plays_any(urls, n=8):
    urls = [u for u in urls if u]
    if not urls:
        return False
    return any(video_plays(u) for u in random.sample(urls, min(n, len(urls))))


def clean_location(description):
    m = CAMDESC.search(description or '')
    text = m.group(1) if m else TAG.sub(' ', description or '')
    text = re.sub(r'\s+', ' ', text).strip()
    # drop the leading district tag, e.g. "[BER]I-81 @ 0.5" -> "I-81 @ 0.5"
    return re.sub(r'^\[[A-Za-z]{2,4}\]\s*', '', text)[:80]


def main():
    js = get(FEED)
    m = re.search(r'(\[\s*\{"origin".*?\}\s*\])', js, re.S)
    if not m:
        raise SystemExit('WV: could not find the camera JSON array in buildCamerasJSONjs')
    rows = json.loads(m.group(1))

    feats, skipped, all_streams = [], 0, []
    for r in rows:
        camid = (r.get('md5') or '').strip()
        try:
            lat, lon = float(r['start_lat']), float(r['start_lng'])
        except (TypeError, ValueError, KeyError):
            skipped += 1; continue
        if not camid or not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        stream = STREAM.format(camid)
        all_streams.append(stream)
        loc = clean_location(r.get('description'))
        road = (r.get('title') or '').strip()
        name = loc or road or camid
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': name, 'kind': 'live',
                                     'directions': [{'snapshot': None, 'video': stream, 'label': ''}],
                                     'roadway': road, 'county': ''}})

    plays = video_plays_any(all_streams)
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/WV.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['WV'] = {'name': 'West Virginia', 'file': 'states/WV.json', 'count': len(feats),
                 'center': [-80.4, 38.8], 'zoom': 7, 'video': plays}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'West Virginia: {len(feats)} cameras ({skipped} skipped), video={plays}')


if __name__ == '__main__':
    main()
