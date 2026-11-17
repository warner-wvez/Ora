"""Officer shifts for Ora: the shift rule, fake officer numbers, the published data and its checks.

Real officer numbers come in and never go out. Every structure `build` returns is keyed by fake
numbers; `check` refuses anything else. No network here: build-chicago-officers.py does the I/O.
"""
import datetime, hashlib, hmac, math, re

GAP_MIN = 240                                  # a gap over 4 hours starts a new shift
CHICAGO = (-87.95, 41.62, -87.50, 42.03)       # a published map point must sit inside this box
ROW_LEN = 7                                    # fake, time, lng, lat, address, violation index, fine
TIME = re.compile(r"^\d\d:\d\d$")


def _minutes(ts):
    return int(datetime.datetime.fromisoformat(ts[:19]).timestamp() // 60)


def split_shifts(tickets):
    runs, cur = [], None
    for x in sorted(tickets, key=lambda r: r["ticketDate"]):
        if cur is None or _minutes(x["ticketDate"]) - _minutes(cur[-1]["ticketDate"]) > GAP_MIN:
            cur = []; runs.append(cur)
        cur.append(x)
    return runs


def _pt(x):
    """The ticket's map point, or None. About 0.7% of the source's points are misread addresses
    ("2811 S ST") geocoded far outside the city; those publish as no map point, like a blank one."""
    if x.get("latitude") in (None, "") or x.get("longitude") in (None, ""):
        return None
    p = [round(float(x["longitude"]), 5), round(float(x["latitude"]), 5)]
    if not (CHICAGO[0] <= p[0] <= CHICAGO[2] and CHICAGO[1] <= p[1] <= CHICAGO[3]):
        return None
    return p


def area_center(tickets):
    pts = [p for p in (_pt(x) for x in tickets) if p]
    if not pts:
        return None
    a = [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]
    return min(pts, key=lambda p: math.hypot(p[0] - a[0], p[1] - a[1]))


class FakeIds:
    """Real officer number -> fake number. `known` is the secret list; `published` maps the keyed
    hash (safe to publish) to fake numbers given out on earlier nights, so they never change."""
    def __init__(self, known, key, published):
        self.known = {str(r): int(f) for r, f in known.items()}
        self.key = key
        self.published = dict(published)
        self.used = set(self.known.values()) | set(self.published.values())

    def k(self, real):
        return hmac.new(self.key, str(real).encode(), hashlib.sha256).hexdigest()[:16]

    def get(self, real):
        real = str(real)
        if real in self.known:
            return self.known[real]
        kk = self.k(real)
        if kk in self.published:
            return self.published[kk]
        f = 100 + int(kk, 16) % 900
        while f in self.used:
            f = 100 + (f - 100 + 1) % 900
        self.published[kk] = f; self.used.add(f)
        return f


def build(tickets_by_real, fake, first, last, violations):
    vio = list(violations); idx = {v: i for i, v in enumerate(vio)}
    def vi(v):
        if v not in idx:
            idx[v] = len(vio); vio.append(v)
        return idx[v]
    daily, totals, days, by_officer = {}, {}, {}, {}
    unread = {}
    for x in tickets_by_real.get("0", []):
        d = x["ticketDate"][:10]
        if first <= d <= last:
            u = unread.setdefault(d, [0, 0.0]); u[0] += 1; u[1] += x["ticketAmount"] / 100
    for real in sorted(tickets_by_real, key=lambda r: int(r)):
        if real == "0":
            continue
        fid = None
        for run in split_shifts(tickets_by_real[real]):
            date = run[0]["ticketDate"][:10]
            if not (first <= date <= last):
                continue
            if fid is None:
                fid = fake.get(real)
            c = area_center(run)
            fines = round(sum(x["ticketAmount"] for x in run) / 100, 2)
            daily.setdefault(str(fid), []).append([date, len(run), fines, run[0]["ticketDate"][11:16], run[-1]["ticketDate"][11:16],
                                                   c[0] if c else None, c[1] if c else None])
            for x in run:
                p = _pt(x)
                days.setdefault(date, []).append([fid, x["ticketDate"][11:16], p[0] if p else None, p[1] if p else None,
                                                  x.get("ticketLocation") or "", vi(x.get("ticketDescription") or x.get("ticketType") or ""),
                                                  round(x["ticketAmount"] / 100, 2)])
                if p:
                    by_officer.setdefault(str(fid), []).append([date, p[0], p[1]])
    for d in set(days) | set(unread):
        rows = days.get(d, []); u = unread.get(d, [0, 0.0])
        totals[d] = [len(rows) + u[0], round(sum(r[6] for r in rows) + u[1], 2), u[0]]
    for d in days:
        days[d].sort(key=lambda r: (r[0], r[1]))
    return {"daily": daily, "totals": totals, "days": days, "by_officer": by_officer, "violations": vio}


def merge(old, new, window_start):
    keep = lambda rows: [r for r in rows if r[0] < window_start]
    daily = {k: keep(v) for k, v in old["daily"].items()}
    for k, v in new["daily"].items():
        daily[k] = keep(daily.get(k, [])) + v
    by_officer = {k: keep(v) for k, v in old["by_officer"].items()}
    for k, v in new["by_officer"].items():
        by_officer[k] = keep(by_officer.get(k, [])) + v
    days = {d: r for d, r in old["days"].items() if d < window_start}; days.update(new["days"])
    totals = {d: r for d, r in old["totals"].items() if d < window_start}; totals.update(new["totals"])
    return {"daily": {k: sorted(v) for k, v in daily.items() if v}, "totals": totals, "days": days,
            "by_officer": {k: v for k, v in by_officer.items() if v}, "violations": new["violations"]}


def assign_characters(officers, fakes_in_order, characters):
    have = {o["id"]: o for o in officers}
    taken = {o["c"] for o in officers if o.get("c")}
    free = [c for c in characters if c["character"] not in taken]
    out = list(officers)
    for f in fakes_in_order:
        if f in have:
            continue
        c = free.pop(0) if free else None
        o = {"id": f, "c": c["character"] if c else None, "s": c["s"] if c else None, "k": None}
        out.append(o); have[f] = o
    return out


def types_from_days(days):
    """Each officer's tickets and fines by violation type, per shift date, from the day files.
    Lets the map rank officers by one ticket type over any dates without loading every day."""
    out = {}
    for d, rows in days.items():
        for r in rows:
            t = out.setdefault(str(r[0]), {}).setdefault(d, {}).setdefault(str(r[5]), [0, 0.0])
            t[0] += 1; t[1] = round(t[1] + r[6], 2)
    return out


def check(out, fakes, first, last):
    probs = []
    def where(lng, lat, at):
        if lng is None and lat is None:
            return
        if not (CHICAGO[0] <= lng <= CHICAGO[2] and CHICAGO[1] <= lat <= CHICAGO[3]):
            probs.append(f"{at}: map point outside Chicago")
    for k, shifts in out["daily"].items():
        if int(k) not in fakes:
            probs.append(f"daily {k}: not a fake officer number")
        for s in shifts:
            if not (first <= s[0] <= last):
                probs.append(f"daily {k} {s[0]}: date outside {first} to {last}")
    for d, rows in out["days"].items():
        if not (first <= d <= last):
            probs.append(f"days {d}: date outside {first} to {last}")
        for r in rows:
            if len(r) != ROW_LEN:
                probs.append(f"days {d}: a row has {len(r)} fields, expected {ROW_LEN}")
            if r[0] not in fakes:
                probs.append(f"days {d}: officer {r[0]} is not a fake number")
            if not TIME.match(str(r[1])):
                probs.append(f"days {d}: bad time {r[1]}")
            if not (isinstance(r[6], (int, float)) and r[6] > 0):
                probs.append(f"days {d}: fine must be above $0")
            if not (0 <= r[5] < len(out["violations"])):
                probs.append(f"days {d}: violation index out of range")
            where(r[2], r[3], f"days {d}")
        n = sum(s[1] for v in out["daily"].values() for s in v if s[0] == d)
        if n != len(rows):
            probs.append(f"days {d}: {len(rows)} tickets do not tie out with {n} in daily")
    for k, per in out.get("types", {}).items():
        if int(k) not in fakes:
            probs.append(f"types {k}: not a fake officer number")
        have = {s[0]: 0 for s in out["daily"].get(k, [])}
        for s in out["daily"].get(k, []):
            have[s[0]] += s[1]
        for d, by in per.items():
            if sum(v[0] for v in by.values()) != have.get(d, 0):
                probs.append(f"types {k} {d}: counts do not tie out with daily")
    for k, pts in out["by_officer"].items():
        if int(k) not in fakes:
            probs.append(f"by_officer {k}: not a fake officer number")
        for p in pts:
            where(p[1], p[2], f"by_officer {k}")
    return probs
