#!/usr/bin/env python3
"""
Build New Jersey cameras from 511nj.org (NJDOT and the NJ Turnpike Authority).

Video-only, played through the relay. Traced 2026-10-22 from a HAR of 511nj.org/camera:

1. The page logs in silently as a guest: POST /account/login with
   {"username": "public", "password": "", "role": "public"}. Nobody types anything. The
   answer is a bearer token good for six minutes, sent back in a `Token` header.
2. POST /client/trafficMap/getTourList lists 85 road "tours"; POST
   /client/trafficMap/getCameraDataByTourId with {"tourId": N} lists each tour's cameras.
   No single call lists them all, so every tour is read and the cameras are merged by id.

511nj.org's own JavaScript AES-encrypts each request body (CBC, a fixed key and IV that sit
in its public main-*.js) and sends {"encryptedData": "<hex>"}. Python's standard library
has no AES, so this shells out to openssl, which every Mac and GitHub runner has.

Every camera is HLS video with no still image, on one of two hosts:
  - nj-511.wink.co (NJDOT), which needed a five-minute ?otp= code in July and no longer
    checks it, and
  - njtpk-wink.xcmdata.org (the Turnpike), which wants 511nj.org's Referer.
Both answer CORS to 511nj.org only, so a page elsewhere cannot play them; the map routes
them through relay.wvez.org/nj, which sends the headers 511nj.org's page would. URLs are
stored as the agency serves them; the page rewrites them (videoFor in index.html).
Cameras NJ marks stopped point at a literal Camera-Unavailable.png and become
location-only pins (decision 0001).

If 511nj.org changes its key, the login stops answering and this exits without touching
the committed file. Run from the repo root: python3 builders/build-states-nj.py
"""
import os, re, json, random, subprocess, urllib.request

SITE = 'https://511nj.org'
# 511nj.org's request-body key and IV, copied from its public main-*.js (etH)
AES_KEY = 'lIo3M)_83,ALC0Wz'.encode().hex()
AES_IV = '.%A}8Qvqm23jYVc9'.encode().hex()
GUEST = {'username': 'public', 'password': '', 'role': 'public'}
# Azure's firewall in front of 511nj.org refuses a desktop-browser User-Agent that arrives
# without the rest of a browser's headers, and lets a plain request through.
HDRS = {'Content-Type': 'application/json'}
STREAM_HOSTS = ('https://nj-511.wink.co/', 'https://njtpk-wink.xcmdata.org/')
# reject any pin that lands outside New Jersey rather than trusting a bad coordinate
BBOX = (-75.6, 38.9, -73.85, 41.4)  # lon_min, lat_min, lon_max, lat_max
RELAY = 'https://relay.wvez.org/nj'
# the road a camera watches, when its name leads with one ("NJ-3 East of Bloomfield Avenue")
ROAD = re.compile(r'^(I-\d+|US-\d+(?:&\d+)?|NJ-\d+|CR-\d+)\b')


def encrypt(obj):
    plain = json.dumps(obj, separators=(',', ':')).encode()
    out = subprocess.run(['openssl', 'enc', '-aes-128-cbc', '-K', AES_KEY, '-iv', AES_IV],
                         input=plain, capture_output=True, check=True)
    return out.stdout.hex()


def post(path, obj=None, token=None, timeout=60):
    hdrs = dict(HDRS, **({'Token': f'Bearer {token}'} if token else {}))
    body = json.dumps({'encryptedData': encrypt(obj)} if obj is not None else {}).encode()
    req = urllib.request.Request(SITE + path, data=body, headers=hdrs, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def video_plays(url):
    """Usable only if the upstream playlist answers when asked the way 511nj.org's page
    asks. CORS is the relay's job, so it is not checked here."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0',
                                               'Origin': SITE, 'Referer': SITE + '/'})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.read(7) == b'#EXTM3U'
    except Exception:
        return False


def video_plays_any(urls, n=8):
    urls = [u for u in urls if u]
    if not urls:
        return False
    return any(video_plays(u) for u in random.sample(urls, min(n, len(urls))))


def main():
    token = post('/account/login', GUEST)['data']['accessToken']
    tours = post('/client/trafficMap/getTourList', token=token)['data']

    cams = {}
    for t in tours:
        for c in post('/client/trafficMap/getCameraDataByTourId', {'tourId': t['id']}, token)['data'] or []:
            cams[c['id']] = c
    if not cams:
        raise SystemExit('NJ: 511nj.org returned no cameras')

    feats, skipped, located_only, streams = [], 0, 0, []
    for cid, c in cams.items():
        try:
            lat, lon = float(c['latitude']), float(c['longitude'])
        except (TypeError, ValueError, KeyError):
            skipped += 1; continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        url = next((d.get('url') for d in c.get('cameraMainDetail') or []
                    if (d.get('url') or '').startswith(STREAM_HOSTS)), None)
        if c.get('stopCameraFlag') or not url:
            url = None; located_only += 1
        else:
            streams.append(url)
        name = re.sub(r'\s+', ' ', c.get('name') or '').strip() or str(cid)
        # The road is the name's lead ("NJ-21 @ Murray Street"). Tours cannot say it: each
        # sweeps in cameras on crossing roads. Turnpike and Parkway cameras share one host and
        # are named by milepost ("MM 104.5 South of Interchange 14") with no road, so they stay
        # blank rather than guessed.
        m = ROAD.match(name)
        road = m.group(1) if m else name.split(' @ ')[0].strip() if ' @ ' in name else ''
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': name[:80], 'kind': 'live',
                                     'directions': [{'snapshot': None, 'video': url, 'label': ''}],
                                     'roadway': road, 'county': ''}})

    plays = video_plays_any(streams)
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/NJ.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['NJ'] = {'name': 'New Jersey', 'file': 'states/NJ.json', 'count': len(feats),
                 'center': [-74.6, 40.1], 'zoom': 7.5, 'video': plays, 'relay': RELAY}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'New Jersey: {len(feats)} cameras ({located_only} location-only, {skipped} skipped), video={plays}')


if __name__ == '__main__':
    main()
