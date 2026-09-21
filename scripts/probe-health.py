#!/usr/bin/env python3
"""
Find the cameras that are not actually showing you a camera.

Roughly one in ten of Ora's snapshot cameras is serving something other than a
live view, and the map presents it identically to one that works. Three ways a
camera lies, and the source is no help: Hawaii reports `status: "OK"` on all 52
cameras serving its "Image Temporarily Unavailable" card, and WSDOT reports
`IsActive: true` on ferry cameras frozen since 2003.

  offline      the image does not load at all
  placeholder  the image is a "camera unavailable" card, not a road
  frozen       a real image, but the same one for over a day

Detecting a placeholder needs no per-state list of what placeholders look like.
Two cameras cannot see the same scene byte for byte, so any image served by
three or more cameras at once is not a camera view. The rule finds them itself,
and found Hawaii's card without being told Hawaii exists.

Cheaply, too. A `Range: bytes=0-1023` request returns the first 1KB *and* the
true total size in `Content-Range`, so a camera is fingerprinted as
(total_size, sha256(first 1KB)) for about 1.2KB of traffic. Every DOT host
honours it, which matters: fetching 35,000 whole JPEGs four times a day is 1.4GB
per run off the servers of 27 state governments. This is 42MB. Do not "optimise"
this into a HEAD request; Georgia and North Carolina answer HEAD with
`Content-Length: 0`.

Clusters are confirmed by pulling two full bodies and checking they really are
identical, and confirmed fingerprints are remembered in known-placeholders.json.
That is what catches the placeholder next time only one camera is down, below
the cluster threshold.

Writes states/health/<CODE>.json. Cameras that are fine are simply absent.
Usage: python3 probe-health.py [CODE ...]
"""
import json, os, sys, time, hashlib, datetime, urllib.request, urllib.parse, collections, threading

OUT = 'states/health'
KNOWN = f'{OUT}/known-placeholders.json'
UA = {'User-Agent': 'Mozilla/5.0 (+https://github.com/warner-wvez/Ora health check)'}
PREFIX = 1024
MIN_BYTES = 200         # anything smaller is an error page, not an image
CLUSTER_MIN = 3         # 2 cameras can share an image by being the same camera listed twice
STALE_SEC = 24 * 3600
MAGIC = (b'\xff\xd8', b'\x89P', b'GI')   # jpeg, png, gif
PER_HOST = 8

_sema, _lock = {}, threading.Lock()


def host_slot(url):
    h = url.split('/')[2]
    with _lock:
        if h not in _sema:
            _sema[h] = threading.Semaphore(PER_HOST)
    return _sema[h]


def encode(url):
    """964 of Oregon's snapshot URLs contain a literal space, and urllib raises
    InvalidURL before it ever reaches the server. Left unencoded, that reads back
    as "Oregon is 86% offline". Keep the raw URL as the key; encode only to fetch.
    `%` is safe so an already-encoded URL is not double-encoded."""
    return urllib.parse.quote(url, safe="%:/?#[]@!$&'()*+,;=~")


def fetch(url, prefix=True, tries=2):
    """Returns (status, body, total_size, last_modified). status 0 means unreachable."""
    hdrs = dict(UA)
    if prefix:
        hdrs['Range'] = f'bytes=0-{PREFIX - 1}'
    url = encode(url)
    for i in range(tries):
        try:
            with host_slot(url):
                with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), timeout=20) as r:
                    body = r.read(PREFIX if prefix else None)
                    total = None
                    cr = r.headers.get('Content-Range')       # 'bytes 0-1023/15136'
                    if cr and '/' in cr:
                        try: total = int(cr.rsplit('/', 1)[1])
                        except ValueError: pass
                    if total is None:
                        try: total = int(r.headers.get('Content-Length') or 0) or None
                        except ValueError: total = None
                    return r.status, body, total, r.headers.get('Last-Modified')
        except Exception as e:
            code = getattr(e, 'code', 0)
            if code or i == tries - 1:
                return code, b'', None, None
            time.sleep(1)
    return 0, b'', None, None


def full_sha(url):
    st, body, _, _ = fetch(url, prefix=False)
    return hashlib.sha256(body).hexdigest()[:16] if st in (200, 206) and body else None


def parse_lm(s):
    try:
        import email.utils
        return email.utils.parsedate_to_datetime(s)
    except Exception:
        return None


# Every state but Wyoming appends a bare-digit timestamp cache-buster to its
# snapshot URL and keeps the camera's identity in the path, so the query is noise
# to be dropped. Wyoming (map.wyoroad.info) instead puts the identity in ?ref=, so
# a *named* query is identity and must be kept, or all 757 cameras collapse to one
# key. Strip only an empty, bare-number, or known cache-buster query.
CACHEBUST = {'t', '_', 'ts', 'nocache', 'cb', 'rand', 'random', 'v'}


def snap_key(u):
    base, _, q = u.partition('?')
    if not q:
        return u
    name = q.split('=', 1)[0] if '=' in q else ''
    return base if (not name or name in CACHEBUST) else u


def snapshots_for(path):
    d = json.load(open(path))
    urls = set()
    for f in d['features']:
        for x in f['properties']['directions']:
            if x.get('snapshot'):
                urls.add(snap_key(x['snapshot']))
    return sorted(urls)


def probe(code, path, known):
    urls = snapshots_for(path)
    if not urls:
        return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=16) as ex:
        rows = list(ex.map(lambda u: (u,) + fetch(u), urls))

    status, fp = {}, {}
    now = datetime.datetime.now(datetime.timezone.utc)
    for u, st, body, total, lm in rows:
        if st not in (200, 206) or len(body) < MIN_BYTES or not body.startswith(MAGIC):
            status[u] = 'offline'
            continue
        fp[u] = f'{total}:{hashlib.sha256(body).hexdigest()[:12]}'
        if lm:
            t = parse_lm(lm)
            if t and (now - t).total_seconds() > STALE_SEC:
                status[u] = 'frozen'

    # a fingerprint already proven to be a placeholder anywhere counts at any size
    for u, f in fp.items():
        if f in known:
            status[u] = 'placeholder'

    groups = collections.defaultdict(list)
    for u, f in fp.items():
        if status.get(u) != 'placeholder':
            groups[f].append(u)
    for f, us in groups.items():
        if len(us) < CLUSTER_MIN:
            continue
        a, b = full_sha(us[0]), full_sha(us[1])   # confirm the prefix match is a whole-image match
        if not a or a != b:
            continue
        known[f] = {'sha': a, 'first_seen': now.isoformat(timespec='seconds').replace('+00:00', 'Z'), 'state': code}
        for u in us:
            status[u] = 'placeholder'

    counts = collections.Counter(status.values())
    bad = sum(counts.values())

    # A whole state does not go dark at once. That much `offline` means we were
    # throttled, or the URLs never left this machine: Oregon read as 86% offline
    # because 964 of its snapshot URLs contain a space. Publishing that would
    # replace the lie we are fixing with a louder one. Say nothing instead.
    if counts['offline'] / len(urls) > 0.4:
        print(f'  {code:7} {len(urls):6} cameras  SKIPPED, {counts["offline"]} offline '
              f'({counts["offline"]/len(urls):.0%}) looks like our fault, not theirs', flush=True)
        return None

    doc = {'checked_at': now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
           'cameras': len(urls), 'counts': dict(counts),
           'status': dict(sorted(status.items()))}
    os.makedirs(OUT, exist_ok=True)
    json.dump(doc, open(f'{OUT}/{code}.json', 'w'), indent=0)
    print(f'  {code:7} {len(urls):6} cameras  {bad:5} bad  '
          f'({counts["offline"]} offline, {counts["placeholder"]} placeholder, {counts["frozen"]} frozen)'
          f'  {bad/len(urls):.0%}', flush=True)
    return counts


def main():
    idx = json.load(open('states/index.json'))
    targets = {c: v['file'] for c, v in idx.items()}
    targets['IL'] = 'cameras.json'      # not a state layer, same shape
    want = {c.upper() for c in sys.argv[1:]}
    if want:
        targets = {k: v for k, v in targets.items() if k in want}

    os.makedirs(OUT, exist_ok=True)
    known = json.load(open(KNOWN)) if os.path.exists(KNOWN) else {}
    t0 = time.time()
    print(f'probing {len(targets)} layers ({len(known)} placeholder fingerprints known)')
    tot = collections.Counter()
    for code, path in sorted(targets.items()):
        if not os.path.exists(path):
            continue
        try:
            c = probe(code, path, known)
            if c: tot.update(c)
        except Exception as e:
            print(f'  [FAIL] {code}: {str(e)[:70]}', flush=True)
    json.dump(known, open(KNOWN, 'w'), indent=1)
    print(f'\n{sum(tot.values())} cameras are not showing a live view '
          f'({dict(tot)}) in {time.time()-t0:.0f}s')
    print(f'{len(known)} placeholder fingerprints now known')


if __name__ == '__main__':
    main()
