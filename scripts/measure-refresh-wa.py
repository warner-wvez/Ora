#!/usr/bin/env python3
"""
Measure how often each WSDOT camera actually replaces its JPEG.

  WSDOT_API_KEY=... python3 measure-refresh-wa.py [passes] [cadence_sec]

WSDOT publishes no refresh-rate field anywhere: not in the REST API, not in the
map's appconfig.json, not on the cameras page. What it does publish is a
`Last-Modified` header on every image. Poll HEAD on a cadence, watch that
timestamp move, and the refresh rate falls out.

Ages are measured against the server's own `Date` header, so a skewed local
clock cannot corrupt the result.

Two estimators, because either one alone is wrong in a predictable way:

  T_gap = window / (times Last-Modified changed)
      Right when the camera is slower than our cadence. When it is faster we
      miss refreshes between passes, undercount, and overestimate T.

  T_age = max(observed image age) * (n+1)/n
      An image's age at a random moment is ~uniform on [0, T], so the largest
      age we see approximates T. Aliasing cannot fool it. Weak only when T
      approaches the length of the whole run.

Their failure modes do not overlap, and both err upward, so we take the min.

A camera whose image never changes and is over a day old is dead, however
cheerfully the API reports `IsActive: true`. Those get `stale_since` instead of
a rate. There were 17 of them on 2026-07-09, six stamped in 2003.

Writes states/WA-refresh.json, which build-states-wa.py folds in if present.
Run order: build-states-wa.py, then this, then build-states-wa.py again.
"""
import os, sys, json, time, urllib.request, email.utils, datetime
from concurrent.futures import ThreadPoolExecutor

KEY = os.environ.get('WSDOT_API_KEY')
if not KEY:
    raise SystemExit('Set WSDOT_API_KEY (free key at https://wsdot.wa.gov/traffic/api/)')

PASSES = int(sys.argv[1]) if len(sys.argv) > 1 else 14
CADENCE = int(sys.argv[2]) if len(sys.argv) > 2 else 60
STALE_SEC = 24 * 3600
UA = {'User-Agent': 'Mozilla/5.0 (ora-traffic-cams)'}
API = ('https://wsdot.wa.gov/Traffic/api/HighwayCameras/HighwayCamerasREST.svc'
       f'/GetCamerasAsJson?AccessCode={KEY}')


def head(item):
    cid, url = item
    try:
        req = urllib.request.Request(url, headers=UA, method='HEAD')
        with urllib.request.urlopen(req, timeout=12) as r:
            lm, date = r.headers.get('Last-Modified'), r.headers.get('Date')
            if not lm or not date:
                return None
            return (cid,
                    email.utils.parsedate_to_datetime(date),
                    email.utils.parsedate_to_datetime(lm))
    except Exception:
        return None


def estimate(obs):
    """obs: [(server_time, last_modified)] for one camera, in pass order.

    Times come from that one camera's own host, so a third-party webcam with a
    skewed clock cannot corrupt anything but itself.
    """
    if len(obs) < 2:
        return None
    ages = [(t - lm).total_seconds() for t, lm in obs]
    window = (obs[-1][0] - obs[0][0]).total_seconds()
    changes = sum(1 for a, b in zip(obs, obs[1:]) if a[1] != b[1])

    if changes == 0 and min(ages) > STALE_SEC:
        return {'stale_since': obs[-1][1].astimezone(datetime.timezone.utc)
                                          .isoformat().replace('+00:00', 'Z')}
    # One refresh does not measure an interval. Seeing a single change puts the
    # rate somewhere between max(ages) and forever, and t_gap would just echo the
    # window back: it is how 85 cameras once got confidently labelled "~14 min"
    # on a 14 min run. Say nothing and let the map fall back to generic wording.
    if changes < 2:
        return None

    t_gap = window / changes
    t_age = max(ages) * (len(ages) + 1) / len(ages)
    return {'refresh_sec': int(round(min(t_gap, t_age))),
            'changes': changes, 'samples': len(obs)}


def main():
    with urllib.request.urlopen(urllib.request.Request(API, headers=UA), timeout=60) as r:
        cams = json.loads(r.read())
    targets = [(c['CameraID'], c['ImageURL'].split('?')[0])
               for c in cams if c.get('ImageURL')]
    print(f'{len(targets)} cameras, {PASSES} passes every {CADENCE}s '
          f'(~{PASSES * CADENCE // 60} min)')

    obs = {cid: [] for cid, _ in targets}
    for p in range(PASSES):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=8) as ex:
            rows = [r for r in ex.map(head, targets) if r]
        for cid, date, lm in rows:
            obs[cid].append((date, lm))
        print(f'  pass {p + 1}/{PASSES}: {len(rows)} ok in {time.time() - t0:.0f}s', flush=True)
        if p < PASSES - 1:
            time.sleep(max(0, CADENCE - (time.time() - t0)))

    out, stale = {}, 0
    for cid, o in obs.items():
        e = estimate(o)
        if not e:
            continue
        out[str(cid)] = e
        stale += 'stale_since' in e

    rates = sorted(e['refresh_sec'] for e in out.values() if 'refresh_sec' in e)
    # median of each camera's own window: a handful of images live on third-party
    # hosts (a ski lodge, the Park Service) whose clocks are off by an hour, and
    # taking min/max across all of them reports a 97 minute run that never happened
    spans = sorted((o[-1][0] - o[0][0]).total_seconds() for o in obs.values() if len(o) > 1)
    doc = {'measured_at': datetime.datetime.now(datetime.timezone.utc)
                                  .isoformat(timespec='seconds').replace('+00:00', 'Z'),
           'window_sec': int(spans[len(spans) // 2]) if spans else 0,
           'passes': PASSES, 'cameras': out}
    os.makedirs('states', exist_ok=True)
    json.dump(doc, open('states/WA-refresh.json', 'w'), indent=1)
    if rates:
        med = rates[len(rates) // 2]
        print(f'\n{len(rates)} rated, median {med}s, '
              f'p90 {rates[int(len(rates) * .9)]}s, {stale} stale')
    print(f'wrote states/WA-refresh.json')


if __name__ == '__main__':
    main()
