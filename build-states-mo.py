#!/usr/bin/env python3
"""
Build Missouri cameras from MoDOT's Traveler Information Map (traveler.modot.org).

Live video. The map fetches one static feed,
traveler.modot.org/timconfig/feed/desktop/StreamingCams2.json, an array of
{ location, x (lng), y (lat), rtmp, html }. `html` is the HLS playlist. There is
no still image field, so Missouri is video-only, like Texas: its popup plays the
stream over a dark backdrop instead of a poster.

Two stream-URL shapes, both CORS-open and both token-free *as stored*:

  * ~560 are direct Wowza edges: https://sfs0N-traveler.modot.mo.gov/rtplive/
    <cam>/playlist.m3u8 (and s2.ozarkstrafficoneview.com). They send
    Access-Control-Allow-Origin: * on the playlist and segments.
  * ~320 point at https://traveler.modot.org/tisvc/api/Tms/CameraStream/<code>,
    which 303-redirects to a streamlock.net playlist carrying a fresh Wowza token
    minted *per request*. The stored URL has no token, so it is legal for a static
    file (house rule 2 forbids baking a short-lived credential in, not following a
    redirect that issues one at play time); the browser re-follows it on every
    open and gets a live token, and the redirect target is ACAO:*.

We keep both as-is, refuse any URL that already carries a `token=`, and only set
video=True after sampling real streams and seeing one play. Cameras sharing an
exact coordinate collapse into one pin with a view each, so pins stay clickable.
"""
import os, json, random, urllib.request
from collections import defaultdict

FEED = 'https://traveler.modot.org/timconfig/feed/desktop/StreamingCams2.json'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://traveler.modot.org/'}
# reject any pin that lands outside Missouri rather than trusting a bad coordinate
BBOX = (-95.9, 35.9, -88.9, 40.7)  # lon_min, lat_min, lon_max, lat_max


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def video_plays(url):
    """Usable only if the stream host allows cross-origin playback and the stored
    URL carries no short-lived credential (a token cannot live in a static file)."""
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


def titlecase(s):
    s = (s or '').strip()
    # the feed mixes "141 AT 21" and "CAMPBELL AND WALNUT"; tidy the shouted ones
    return s.title() if s.isupper() else s


def main():
    rows = get(FEED)
    groups = defaultdict(list)
    skipped = 0
    for c in rows:
        u = (c.get('html') or '').strip()
        try:
            lon, lat = float(c['x']), float(c['y'])
        except (TypeError, ValueError, KeyError):
            skipped += 1; continue
        if not u or 'token=' in u.lower() or not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        groups[(round(lon, 5), round(lat, 5))].append((titlecase(c.get('location')), u))

    feats, all_streams = [], []
    for (lon, lat), cams in groups.items():
        seen, dirs = set(), []
        for loc, u in cams:
            if u in seen:
                continue
            seen.add(u)
            dirs.append({'snapshot': None, 'video': u, 'label': loc if len(cams) > 1 else ''})
            all_streams.append(u)
        name = cams[0][0] or 'Camera'
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': name, 'kind': 'live', 'directions': dirs,
                                     'roadway': '', 'county': ''}})

    plays = video_plays_any(all_streams)
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/MO.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['MO'] = {'name': 'Missouri', 'file': 'states/MO.json', 'count': len(feats),
                 'center': [-92.5, 38.5], 'zoom': 6.3, 'video': plays}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'Missouri: {len(feats)} pins ({len(all_streams)} streams, {skipped} skipped), video={plays}')


if __name__ == '__main__':
    main()
