#!/usr/bin/env python3
"""
Build Alabama cameras from ALGO Traffic (algotraffic.com, ALDOT).

Snapshot-only, and the reason is a new failure mode for this repo: DRM behind a
green CORS check. api.algotraffic.com/v4.0/Cameras is a plain open GET -- 629
cameras with coordinates, an HLS playlist and a snapshot URL each -- and the
Wowza CDN answers the playlist with Access-Control-Allow-Origin: *, so the house
CORS probe alone would happily flag the state as live video. But every chunklist
carries #EXT-X-KEY:METHOD=SAMPLE-AES pointing at fps.ezdrm.com: FairPlay DRM,
licensed per-session through ezdrm's proxy (the site pairs it with Widevine for
DASH). hls.js cannot decrypt SAMPLE-AES FairPlay, no static page can, and that is
exactly why algotraffic.com itself defaults to the still image and makes you
flip a "live feed" switch that boots a DRM-capable player. So video_plays()
here reads the chunklist and refuses any stream that names a key, the same way
the other builders refuse token= URLs: a stream we cannot actually decrypt must
not put a LIVE badge on the map. All 5 regional CDNs (tuscaloosa/mnt/bhm/
mobile/tuscumbia) were sampled DRM'd on 2026-07-12.

The snapshots are good: https://api.algotraffic.com/v4/Cameras/<id>/snapshot.jpg,
https, no referrer games, Cache-Control max-age=600 (the origin refreshes about
every 10 minutes). Video URLs are written as null on purpose -- storing an
unplayable-by-design URL only invites a future naive CORS check to resurrect it.
"""
import json, random, re, urllib.request

API = 'https://api.algotraffic.com/v4.0/Cameras'
HDRS = {'User-Agent': 'Mozilla/5.0'}
# reject any pin outside Alabama rather than trusting a bad coordinate
BBOX = (-88.6, 30.1, -84.8, 35.1)  # lon_min, lat_min, lon_max, lat_max

# location.direction is the direction of travel the camera covers; expand it to
# the same vocabulary the WSDOT and 511ny chips use.
FACING = {'north': 'Northbound', 'south': 'Southbound', 'east': 'Eastbound',
          'west': 'Westbound', 'both': 'Both directions'}


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def video_plays(url):
    """CORS-open is not enough here: read the chunklist and refuse DRM.

    A signed/expiring URL is refused like everywhere else, and additionally any
    chunklist that declares #EXT-X-KEY (SAMPLE-AES / FairPlay on this CDN) is
    refused, because a green CORS header over an undecryptable stream is still
    a dead popup."""
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
        chunklist = get(url.rsplit('/', 1)[0] + '/' + media[0], timeout=12)
        return not any(l.startswith('#EXT-X-KEY') for l in chunklist.splitlines())
    except Exception:
        return False


def video_plays_any(urls, n=8):
    urls = [u for u in urls if u]
    if not urls:
        return False
    return any(video_plays(u) for u in random.sample(urls, min(n, len(urls))))


def main():
    cams = json.loads(get(API))
    feats = []
    hls_urls = []
    for c in cams:
        loc = c.get('location') or {}
        lat, lng = loc.get('latitude'), loc.get('longitude')
        if lat is None or lng is None:
            continue
        if not (BBOX[0] <= lng <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        road = (loc.get('displayRouteDesignator') or '').strip()
        cross = (loc.get('displayCrossStreet') or '').strip()
        name = f'{road} at {cross}' if road and cross else (road or cross or loc.get('city') or 'Camera')
        snap = c.get('snapshotImageUrl')
        hls = (c.get('playbackUrls') or {}).get('hls')
        if hls:
            hls_urls.append(hls)
        d = {'snapshot': snap, 'video': None, 'label': ''}
        facing = FACING.get((loc.get('direction') or '').strip().lower())
        if facing:
            d['facing'] = facing
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                      'properties': {'name': name, 'kind': 'live', 'directions': [d],
                                     'roadway': road, 'county': loc.get('county') or ''}})

    plays = video_plays_any(hls_urls)
    if plays:
        # the day ALDOT drops DRM this build starts failing loudly instead of
        # silently shipping snapshot-only over a working video state
        raise SystemExit('a sampled ALGO stream now plays without DRM: rework this '
                         'build to carry video URLs before shipping')

    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/AL.json', 'w'))
    index = json.load(open('states/index.json'))
    index['AL'] = {'name': 'Alabama', 'file': 'states/AL.json', 'count': len(feats),
                   'center': [-86.8, 32.8], 'zoom': 6.3, 'video': False}
    json.dump(index, open('states/index.json', 'w'), indent=1)
    print(f'AL: {len(feats)} cameras, snapshot-only (FairPlay DRM on all sampled streams)')


if __name__ == '__main__':
    main()
