#!/usr/bin/env python3
"""
Build Montana cameras from MDT's ATMS public feed.

A location-first snapshot state: Montana is 6 traffic cameras + 112 RWIS
road-weather sites, and none of them is live video. Each site publishes one or
more still "views" as timestamped files on mdt.mt.gov (https), whose filenames
rotate roughly every 15 minutes with no stable "latest" URL, so the images we
capture here freeze until the builder re-runs and the health sweep will grey them
after a day. We carry them anyway: the pin marks that a camera exists at this
spot, which is the point for a travel map, and a recent still beats nothing.

Two fetches joined by siteId. listDeviceLocations gives every device's coordinate,
name, route and siteId (under rwisRpu for RWIS, under camera for cameras). The
public/cameras page embeds the current image URL for every view of every site in
one shot, so we parse it once instead of scraping 118 detail pages. A device whose
siteId has no image becomes a location-only pin (no feed published).
"""
import os, re, json, urllib.request

DEVICES = 'https://app.mdt.mt.gov/atms/public/listDeviceLocations'
CAMERAS = 'https://app.mdt.mt.gov/atms/public/cameras'
HDRS = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://app.mdt.mt.gov'}
# reject any pin outside Montana rather than trusting a bad coordinate
BBOX = (-116.2, 44.3, -104.0, 49.1)  # lon_min, lat_min, lon_max, lat_max
IMG = re.compile(r'https://mdt\.mt\.gov/other/WebAppData/External/RRS/[A-Za-z]+/[^\s"\'<>]+\.jpg')


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=90) as r:
        return r.read().decode('utf-8', 'replace')


def images_by_site(html):
    """Map siteId -> {view index: image url}. Filenames read <name>-<siteId>-<NN>-<ts>.jpg."""
    out = {}
    for url in set(IMG.findall(html)):
        m = re.search(r'-(\d{4,7})-(\d{2})-\d', url)
        if not m:
            continue
        site, view = m.group(1), m.group(2)
        out.setdefault(site, {}).setdefault(view, url)  # first url per view is enough
    return out


def main():
    devices = json.loads(get(DEVICES))
    if isinstance(devices, dict):
        devices = next(v for v in devices.values() if isinstance(v, list))
    imgs = images_by_site(get(CAMERAS))

    feats, skipped, with_img = [], 0, 0
    for d in devices:
        lat, lon = d.get('lat'), d.get('lon')
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            skipped += 1; continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            skipped += 1; continue
        site = str((d.get('rwisRpu') or {}).get('siteId') or (d.get('camera') or {}).get('siteId') or '')
        views = imgs.get(site, {})
        if views:
            with_img += 1
            dirs = [{'snapshot': views[v], 'video': None, 'label': f'View {i+1}'}
                    for i, v in enumerate(sorted(views))]
        else:
            dirs = [{'snapshot': None, 'video': None, 'label': ''}]  # location-only pin
        kind = 'Camera' if d.get('resourceTypeDescription') == 'Camera' else 'RWIS'
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                      'properties': {'name': (d.get('locationName') or '').strip(),
                                     'kind': 'live',
                                     'directions': dirs,
                                     'roadway': (d.get('signRte') or '').strip(),
                                     'county': (d.get('maintDivName') or '').strip(),
                                     'cameraType': kind}})
    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/MT.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['MT'] = {'name': 'Montana', 'file': 'states/MT.json', 'count': len(feats),
                 'center': [-109.6, 47.0], 'zoom': 5.8, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'Montana: {len(feats)} sites ({with_img} with imagery, {len(feats)-with_img} location-only, {skipped} skipped)')


if __name__ == '__main__':
    main()
