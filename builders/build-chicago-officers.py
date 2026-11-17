#!/usr/bin/env python3
"""
Rebuild chicago-officers/ (Ora's officer shifts) from Second City Citation.

Nightly (GitHub Action): pull the last 8 days for every officer, rebuild the last 7 days, keep
older days as committed. Once, on Warner's Mac: --from-raw reads his full local pull instead.
Real officer numbers come from the OFFICER_MAP secret (JSON {"real": fake}) and stay in memory;
new officers get a fake number from a keyed hash (OFFICER_KEY secret). Nothing is written unless
every check in officers.check passes; then the committed files stay as they were.

Usage:  python3 builders/build-chicago-officers.py                       (nightly pull)
        python3 builders/build-chicago-officers.py --from-raw DIR --map FILE   (one-time backfill)
Needs:  Python 3 standard library. About 40 minutes nightly (8 s between requests).
"""
import argparse, datetime, json, os, sys, time
from urllib.request import urlopen, Request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import officers as of

BASE = "https://secondcitycitation.com"
OUT = "chicago-officers"
FIRST = "2026-08-01"
PAUSE_S = 8
_last_call = [0.0]


def get_json(path, tries=4):
    for i in range(tries):
        wait = PAUSE_S - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        try:
            _last_call[0] = time.time()
            with urlopen(Request(BASE + path, headers={"User-Agent": "ora-build"}), timeout=180) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"  {path}: {e}; retrying in 60 s", flush=True); time.sleep(60)


def read_existing(d):
    def j(p, default):
        try:
            return json.load(open(os.path.join(d, p)))
        except (FileNotFoundError, json.JSONDecodeError):
            return default
    o = j("officers.json", {"officers": [], "violations": [], "first": FIRST, "last": None})
    dl = j("daily.json", {"shifts": {}, "totals": {}})
    days = {f[:-5]: j(f"days/{f}", []) for f in (os.listdir(os.path.join(d, "days")) if os.path.isdir(os.path.join(d, "days")) else []) if f.endswith(".json")}
    bo = {f[:-5]: j(f"by-officer/{f}", []) for f in (os.listdir(os.path.join(d, "by-officer")) if os.path.isdir(os.path.join(d, "by-officer")) else []) if f.endswith(".json")}
    data = {"daily": dl["shifts"], "totals": dl["totals"], "days": days, "by_officer": bo, "violations": o["violations"]}
    return data, o["officers"], {"first": o.get("first", FIRST), "last": o.get("last")}


def write_all(d, out, officers, meta):
    def w(p, obj):
        path = os.path.join(d, p); os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"; json.dump(obj, open(tmp, "w"), separators=(",", ":")); os.replace(tmp, path)
    w("officers.json", {"updated": datetime.date.today().isoformat(), "first": meta["first"], "last": meta["last"],
                        "violations": out["violations"], "officers": sorted(officers, key=lambda o: o["id"])})
    w("daily.json", {"shifts": out["daily"], "totals": out["totals"]})
    if "types" in out:
        w("types.json", out["types"])
    for day, rows in out["days"].items():
        w(f"days/{day}.json", rows)
    for k, pts in out["by_officer"].items():
        w(f"by-officer/{k}.json", pts)


def chicago_yesterday():
    return (datetime.datetime.now(ZoneInfo("America/Chicago")).date() - datetime.timedelta(days=1)).isoformat()


def pull(window_from, known_ids):
    """Every officer's tickets from window_from (a day early, so night shifts stay whole).
    /api/officers lists only recently active officers (124 of about 300 on 11-16), so every officer
    on the private list is pulled too, plus 0 (unreadable officer number, counted in totals only)."""
    ids = sorted({str(o["officerId"]) for o in get_json("/api/officers")} | set(known_ids) | {"0"}, key=int)
    by_real = {}
    for i, real in enumerate(ids):
        limit, rows = 800, []
        while True:
            rows = get_json(f"/api/tickets?officerId={real}&limit={limit}")
            if not rows or len(rows) < limit or rows[-1]["ticketDate"][:10] < window_from or limit >= 50000:
                break
            limit *= 4
        by_real[real] = [r for r in rows if r["ticketDate"][:10] >= window_from]
        if i % 25 == 0:
            print(f"  {i + 1}/{len(ids)} officers pulled", flush=True)
    return by_real


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-raw"); ap.add_argument("--map"); ap.add_argument("--last")
    a = ap.parse_args()
    key = os.environ.get("OFFICER_KEY", "").encode()
    if not key:
        sys.exit("OFFICER_KEY is not set")
    old, officers, meta = read_existing(OUT)
    last = a.last or chicago_yesterday()
    if a.from_raw:                                   # one-time backfill on Warner's Mac
        priv = json.load(open(a.map))
        known = {str(o["realId"]): o["fakeId"] for o in priv}
        by_real = {}
        for f in os.listdir(os.path.join(a.from_raw, "raw")):
            if f.startswith("officer-") and f.endswith(".json"):
                by_real[f[8:-5]] = json.load(open(os.path.join(a.from_raw, "raw", f)))
        first, window_start = FIRST, FIRST
        chars = json.load(open(os.path.join(OUT, "characters.json")))
        cell = {c["character"]: c["s"] for c in chars}
        officers = [{"id": o["fakeId"], "c": o["character"], "s": cell.get(o["character"]), "k": None} for o in priv]
    else:                                            # nightly
        known = json.loads(os.environ["OFFICER_MAP"])
        first = meta["first"]
        window_start = (datetime.date.fromisoformat(last) - datetime.timedelta(days=6)).isoformat()
        pull_from = (datetime.date.fromisoformat(window_start) - datetime.timedelta(days=1)).isoformat()
        by_real = pull(pull_from, known)
    fake = of.FakeIds(known, key, {o["k"]: o["id"] for o in officers if o.get("k")})
    new = of.build(by_real, fake, window_start if not a.from_raw else first, last, old["violations"])
    out = new if a.from_raw else of.merge(old, new, window_start)
    # keyed hashes for officers given a number tonight, then characters for any newcomer
    for kk, f in fake.published.items():
        for o in officers:
            if o["id"] == f and not o.get("k"):
                o["k"] = kk
    chars = json.load(open(os.path.join(OUT, "characters.json")))
    fakes_by_fines = sorted({int(k) for k in out["daily"]}, key=lambda f: -sum(s[2] for s in out["daily"][str(f)]))
    officers = of.assign_characters(officers, fakes_by_fines, chars)
    for kk, f in fake.published.items():
        for o in officers:
            if o["id"] == f:
                o["k"] = kk
    out["types"] = of.types_from_days(out["days"])   # per officer, date and ticket type, for ranking by type
    out["by_officer"] = of.points_from_days(out["days"])   # dots for ranges, with each ticket's type
    probs = of.check(out, {o["id"] for o in officers}, first, last)
    if probs:
        print("CHECKS FAILED, nothing written:\n  " + "\n  ".join(probs[:40]))
        sys.exit(1)
    write_all(OUT, out, officers, {"first": first, "last": last})
    print(f"wrote {len(out['days'])} days, {len(out['daily'])} officers, last day {last}")


if __name__ == "__main__":
    main()
