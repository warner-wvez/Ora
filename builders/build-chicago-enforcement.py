#!/usr/bin/env python3
"""
Rebuild cameras-chicago-enforcement.json from the Chicago Data Portal.

Combines four open datasets (no API key needed):
  - Red Light Camera Violations   spqx-js37
  - Speed Camera Locations        4i42-qv3h
  - Speed Camera Violations       hhkd-xvj4
  - Traffic Crashes - Crashes     85ca-t3if

For every enforcement camera it computes, within a 150 m radius, the number of
injury crashes since 2023, how many people were hurt/killed, and how many of
those crashes were caused by the exact behavior the camera targets (running the
light / speeding). It then classifies each camera into a "safety verdict"
quadrant by median-splitting last-90-day ticket volume against nearby injury
crashes.

Usage:  python3 build-chicago-enforcement.py
Needs:  Python 3, `requests` (or falls back to urllib). Runs in ~1-2 min.
"""
import json, math, time
from urllib.request import urlopen, Request
from urllib.parse import quote
from collections import defaultdict, Counter

BASE = "https://data.cityofchicago.org/resource"
RADIUS_M = 150.0
CRASH_SINCE = "2023-01-01"

def soda(dataset, params, retries=4):
    """Run a SODA query, returning parsed JSON. Retries on truncated responses."""
    q = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    url = f"{BASE}/{dataset}.json?{q}"
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers={"User-Agent": "ora-build"}), timeout=120) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))

def page(dataset, params, chunk=20000):
    """Page through a large dataset in `chunk`-sized requests."""
    out, off = [], 0
    while True:
        p = dict(params); p["$limit"] = chunk; p["$offset"] = off
        rows = soda(dataset, p)
        out += rows
        if len(rows) < chunk:
            return out
        off += chunk

def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None

# ---- most recent violation date per dataset, so "last 90 days" is meaningful ----
rl_max = soda("spqx-js37", {"$select": "max(violation_date)"})[0]["max_violation_date"][:10]
sp_max = soda("hhkd-xvj4", {"$select": "max(violation_date)"})[0]["max_violation_date"][:10]
def minus_90(d):
    import datetime
    return (datetime.date.fromisoformat(d) - datetime.timedelta(days=90)).isoformat()
rl_since, sp_since = minus_90(rl_max), minus_90(sp_max)
print(f"red light window: >{rl_since}  speed window: >{sp_since}")

# ---- red light: aggregate to intersection level ----
rl_tot = {r["intersection"]: r for r in soda("spqx-js37",
    {"$select": "intersection,avg(latitude) as lat,avg(longitude) as lng,sum(violations) as vtot",
     "$group": "intersection", "$limit": 5000}) if r.get("intersection")}
rl_90 = {r["intersection"]: r for r in soda("spqx-js37",
    {"$select": "intersection,sum(violations) as v90",
     "$where": f"violation_date > '{rl_since}T00:00:00'", "$group": "intersection", "$limit": 5000})
    if r.get("intersection")}

rl_features = []
for name, tot in rl_tot.items():
    if not tot.get("lat") or not tot.get("lng"): continue
    v90 = float(rl_90[name]["v90"]) if name in rl_90 else 0.0
    rl_features.append({"type": "Feature",
        "geometry": {"type": "Point", "coordinates": [float(tot["lng"]), float(tot["lat"])]},
        "properties": {"kind": "redlight", "name": name.title(),
                       "v90": int(v90), "vtot": int(float(tot["vtot"]))}})

# ---- speed: violations joined to location metadata ----
sp90 = {r["camera_id"]: r for r in soda("hhkd-xvj4",
    {"$select": "camera_id,address,latitude,longitude,sum(violations) as v90",
     "$where": f"violation_date > '{sp_since}T00:00:00'",
     "$group": "camera_id,address,latitude,longitude", "$limit": 5000}) if r.get("camera_id")}
sptot = {r["camera_id"]: float(r["vtot"]) for r in soda("hhkd-xvj4",
    {"$select": "camera_id,sum(violations) as vtot", "$group": "camera_id", "$limit": 5000})
    if r.get("camera_id")}
sploc = {r["location_id"]: r for r in soda("4i42-qv3h",
    {"$select": "location_id,address,first_approach,second_approach,go_live_date,latitude,longitude",
     "$limit": 5000}) if r.get("location_id")}

sp_features = []
for cid in (set(sptot) | set(sploc)):
    meta, rec = sploc.get(cid, {}), sp90.get(cid, {})
    lat = rec.get("latitude") or meta.get("latitude")
    lng = rec.get("longitude") or meta.get("longitude")
    if not lat or not lng: continue
    approaches = [a for a in [meta.get("first_approach"), meta.get("second_approach")] if a]
    sp_features.append({"type": "Feature",
        "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
        "properties": {"kind": "speed", "name": (rec.get("address") or meta.get("address") or cid).title(),
                       "camId": cid, "v90": int(float(rec["v90"])) if rec else 0,
                       "vtot": int(sptot.get(cid, 0)), "approaches": approaches,
                       "goLive": (meta.get("go_live_date") or "")[:10]}})

features = rl_features + sp_features
print(f"cameras: {len(rl_features)} red light + {len(sp_features)} speed = {len(features)}")

# ---- injury crashes since 2023, joined spatially ----
print("pulling injury crashes...")
crashes = page("85ca-t3if",
    {"$select": "latitude,longitude,injuries_total,injuries_fatal,prim_contributory_cause",
     "$where": f"crash_date > '{CRASH_SINCE}' AND latitude IS NOT NULL AND injuries_total > 0",
     "$order": "crash_date"})
print(f"injury crashes: {len(crashes)}")

grid = defaultdict(list)
for c in crashes:
    lat, lng = fnum(c.get("latitude")), fnum(c.get("longitude"))
    if lat is None or lng is None: continue
    grid[(round(lat, 2), round(lng, 2))].append(
        (lat, lng, fnum(c.get("injuries_total")) or 0, fnum(c.get("injuries_fatal")) or 0,
         (c.get("prim_contributory_cause") or "").upper()))

SPEED_CAUSES = ("EXCEEDING AUTHORIZED SPEED", "EXCEEDING SAFE SPEED", "FAILING TO REDUCE SPEED")
RL_CAUSES = ("DISREGARDING TRAFFIC SIGNALS", "DISREGARDING OTHER TRAFFIC SIGNS")

def meters(la1, lo1, la2, lo2):
    return math.hypot((la2 - la1) * 111320.0, (lo2 - lo1) * 111320.0 * math.cos(math.radians(la1)))

def nearby(lat, lng, kind):
    n = inj = fat = cause = 0
    keys = SPEED_CAUSES if kind == "speed" else RL_CAUSES
    for dla in (-1, 0, 1):
        for dlo in (-1, 0, 1):
            for p in grid.get((round(lat, 2) + dla * 0.01, round(lng, 2) + dlo * 0.01), []):
                if meters(lat, lng, p[0], p[1]) <= RADIUS_M:
                    n += 1; inj += p[2]; fat += p[3]
                    if any(k in p[4] for k in keys): cause += 1
    return n, int(inj), int(fat), cause

for f in features:
    lng, lat = f["geometry"]["coordinates"]
    n, inj, fat, cm = nearby(lat, lng, f["properties"]["kind"])
    f["properties"].update(crash_injury=n, crash_hurt=inj, crash_fatal=fat, crash_cause=cm)

# ---- verdict quadrant via median split ----
def median(a):
    a = sorted(a); n = len(a)
    return a[n // 2] if n % 2 else (a[n // 2 - 1] + a[n // 2]) / 2
V_MED = median([f["properties"]["v90"] for f in features])
C_MED = median([f["properties"]["crash_injury"] for f in features])
for f in features:
    p = f["properties"]
    hiV, hiC = p["v90"] >= V_MED, p["crash_injury"] >= C_MED
    p["quad"] = ("justified" if hiV and hiC else "revenue" if hiV else "gap" if hiC else "quiet")

out = {"type": "FeatureCollection", "features": features,
       "meta": {"vMedian": V_MED, "crashMedian": C_MED,
                "crashWindow": f"{CRASH_SINCE} to now", "radius_m": int(RADIUS_M),
                "violationWindow": "last 90 days"}}
json.dump(out, open("cameras-chicago-enforcement.json", "w"))
print("verdict counts:", dict(Counter(f["properties"]["quad"] for f in features)))
print(f"medians -> tickets:{V_MED}  injury crashes:{C_MED}")
print("wrote cameras-chicago-enforcement.json")
