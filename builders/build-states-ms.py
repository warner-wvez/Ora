#!/usr/bin/env python3
"""
Build Mississippi cameras from MDOTtraffic (mdottraffic.com, Mississippi DOT).

The map is an ASP.NET WebForms page whose markers come from a page-method:
POST default.aspx/LoadCameraData with a JSON content type returns every camera
SITE (411 of them) as {tooltip, lat, lon, framehtml}, no auth. A site is a pole
with 1..n views; the per-site bubble (mapbubbles/camerasite.aspx?site=N) lists
each view as switchImage('<thumbnail url>', '<cam id>', '<label>') -- so one
GET per site turns the pole into the Washington-style tabbed-views shape.

Streaming hosts are REGIONAL: streamingjxn1-6 (Jackson) plus streaminglym*,
streamingshvn*, streaminggpt* and friends for the rest of the state. A host
pattern that only accepts jxn silently drops 254 of the 411 sites -- exactly
the mistake this build shipped for an evening while its author blamed a
nonexistent rate limit -- so the pattern accepts any streaming* subdomain and
the build refuses to ship if more than 5% of sites still parse empty.

LIVE VIDEO: every view is a Wowza stream at
https://<streaminghost>.mdottraffic.com/rtplive/<camid>.stream/playlist.m3u8
(the host is whichever one the site's thumbnail URL names). No token, no DRM,
Access-Control-Allow-Origin: * on playlist, chunklist and segments. Sampled
streams are still verified at build time per the house rules.

Snapshots are Wowza's own thumbnail endpoint on the same host
(/thumbnail?application=rtplive&streamname=<id>.stream&size=...) -- the site
itself polls it every 5s. The identity lives in the query string (like
Wyoming's ?ref=), which snapKey/probe-health already preserve because the
first parameter name is not a cache-buster. Size is bumped from the site's
352x240 to 640x480, which the endpoint serves happily.
"""
import json, os, random, re, time, urllib.request

LOAD = 'https://www.mdottraffic.com/default.aspx/LoadCameraData'
SITE = 'https://www.mdottraffic.com/mapbubbles/camerasite.aspx?site={}'
HDRS = {'User-Agent': 'Mozilla/5.0'}
# Mississippi plus its river-bridge approaches; rejects bad coordinates, not neighbours
BBOX = (-91.7, 30.0, -88.0, 35.1)

SITE_ID = re.compile(r'site=(\d+)')
SWITCH = re.compile(r"switchImage\('([^']+)',\s*'(\d+)',\s*'([^']*)'")
THUMB_HOST = re.compile(r'https://(streaming\w+)\.mdottraffic\.com')


def post_json(url, timeout=60):
    req = urllib.request.Request(url, data=b'{}',
                                 headers={**HDRS, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def get(url, timeout=45, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1 + i)
    return ''


def video_plays(url):
    """CORS on the playlist, and no DRM in the chunklist, and no expiring token."""
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


def views_for_site(site_id, unrecognized):
    html = get(SITE.format(site_id))
    views, seen = [], set()
    for m in SWITCH.finditer(html):
        thumb, cam, label = m.group(1), m.group(2), m.group(3)
        if cam in seen:
            continue
        seen.add(cam)
        host = THUMB_HOST.search(thumb)
        if not host:
            # novideo.jpg = the source itself says this view is offline right now;
            # that is an honest location-first placeholder, not a parse failure.
            # Anything else unrecognized means a new host pattern is eating views.
            if 'novideo' not in thumb.lower():
                unrecognized.append(thumb[:120])
            continue
        h = host.group(1)
        views.append({
            'snapshot': (f'https://{h}.mdottraffic.com/thumbnail?application=rtplive'
                         f'&streamname={cam}.stream&size=640x480&format=jpg&fitmode=stretch'),
            'video': f'https://{h}.mdottraffic.com/rtplive/{cam}.stream/playlist.m3u8',
            'label': label.strip(),
        })
    return views


def main():
    sites = post_json(LOAD)['d']
    feats, holes, unrecognized = [], 0, []
    for s in sites:
        m = SITE_ID.search(s.get('framehtml') or '')
        if not m:
            continue
        lat, lon = s.get('lat'), s.get('lon')
        if lat is None or lon is None or not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        try:
            views = views_for_site(m.group(1), unrecognized)
        except Exception:
            views = []
        if not views:
            # location-first: a site with no live views right now still marks a spot
            holes += 1
            views = [{'snapshot': None, 'video': None, 'label': ''}]
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': (s.get('tooltip') or 'Camera').strip(), 'kind': 'live',
                                     'directions': views, 'roadway': '', 'county': ''}})
        time.sleep(0.25)

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/MS.json', 'w'))
    print(f'MS: {len(feats)} sites, {holes} with no live views (source-offline placeholders)')
    if len(unrecognized) > 10:
        for u in unrecognized[:5]:
            print('  unrecognized thumb host:', u)
        raise SystemExit(f'{len(unrecognized)} views point at hosts the pattern does not know '
                         '-- a new region is being eaten; index NOT updated, nothing ships')

    all_vid = [d['video'] for f in feats for d in f['properties']['directions'] if d['video']]
    plays = video_plays_any(all_vid)
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['MS'] = {'name': 'Mississippi', 'file': 'states/MS.json', 'count': len(feats),
                 'center': [-89.7, 32.6], 'zoom': 6.3, 'video': plays}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    views = sum(len(f['properties']['directions']) for f in feats)
    print(f'MS SHIPPED: {len(feats)} sites, {views} views, video={plays}')


if __name__ == '__main__':
    main()
