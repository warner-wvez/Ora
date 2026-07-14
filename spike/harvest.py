"""Harvest real frames from Ora cameras for the YOLO transfer spike.

Video slots pull one frame per HLS stream with ffmpeg. Snapshot slots GET the still
endpoint. Every slot has a fallback pool of same-state, same-class cameras, so a dead
camera is replaced from the same state rather than padded with whatever is convenient.

Frames land in spike/frames/, one manifest row each in spike/manifest.json.
"""
import json, math, random, subprocess, sys, io, hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "spike" / "frames"
FRAMES.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"

TZ = {"HI": "Pacific/Honolulu", "WA": "America/Los_Angeles", "TX": "America/Chicago",
      "IL": "America/Chicago", "MS": "America/Chicago", "AL": "America/Chicago",
      "KY": "America/New_York", "NY": "America/New_York", "NYC": "America/New_York",
      "SC": "America/New_York", "MD": "America/New_York", "FL": "America/New_York",
      "RI": "America/New_York"}

FILES = {"IL": "cameras.json", "NYC": "cameras-nyc.json"}
CACHEBUST = {"t", "ts", "time", "cb", "_", "rand", "r", "nocache", "cachebust"}


def snap_key(u):
    base, _, q = u.partition("?")
    if not q:
        return u
    name = q.split("=", 1)[0] if "=" in q else ""
    return base if (not name or name in CACHEBUST) else u


def state_file(code):
    return ROOT / FILES.get(code, f"states/{code}.json")


def bad_urls(code):
    p = ROOT / "states" / "health" / f"{code}.json"
    if not p.exists():
        return set()
    return set(json.load(open(p)).get("status", {}).keys())


def cams(code, src):
    """Every (name, url, lon, lat) in a state whose health sweep did not flag it."""
    d = json.load(open(state_file(code)))
    bad = bad_urls(code)
    out = []
    for f in d["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        for dr in p["directions"]:
            if src == "video":
                url = dr.get("video")
            elif code == "NYC":
                cid = dr.get("camId")
                url = f"https://webcams.nyctmc.org/api/cameras/{cid}/image" if cid else None
            else:
                url = dr.get("snapshot")
            if not url:
                continue
            # health describes the snapshot; a video cam is judged by whether the stream decodes
            if src == "snapshot" and snap_key(url) in bad:
                continue
            out.append({"name": p["name"].strip(), "url": url, "lon": lon, "lat": lat,
                        "label": (dr.get("label") or "").strip()})
    return out


def grab_video(url, dest):
    """One frame off the live edge of an HLS stream."""
    for extra in ([], ["-ss", "3"]):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-user_agent", UA,
               "-rw_timeout", "20000000", *extra, "-i", url,
               "-frames:v", "1", "-q:v", "2", "-update", "1", str(dest)]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=70)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 4000:
            return True, ""
        err = (r.stderr or b"").decode()[-140:].replace("\n", " ")
    return False, err


def grab_snapshot(url, dest):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
    except Exception as e:
        return False, str(e)[:120]
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if "image" not in r.headers.get("content-type", ""):
        return False, f"content-type {r.headers.get('content-type')}"
    if len(r.content) < 4000:
        return False, f"tiny body {len(r.content)}B"
    try:
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception as e:
        return False, f"undecodable {e}"[:120]
    im.save(dest, "JPEG", quality=95)
    return True, ""


def usable(dest):
    """Reject flat/placeholder frames: a real road scene has texture."""
    try:
        im = Image.open(dest).convert("RGB")
    except Exception as e:
        return False, f"unreadable {e}"[:80]
    w, h = im.size
    if w < 240 or h < 180:
        return False, f"too small {w}x{h}"
    a = np.asarray(im.convert("L"), dtype=np.float32)
    if a.std() < 8:
        return False, f"flat image (std {a.std():.1f}) - placeholder/black"
    return True, f"{w}x{h}"


def harvest(slots):
    manifest, used_names = [], set()
    for s in slots:
        code, src = s["state"], s["src"]
        pool = cams(code, src)
        # exact pick first, then same-state fallbacks ordered by class distance
        picks = [c for c in pool if s["match"].lower() in c["name"].lower()]
        rest = [c for c in pool if c not in picks]
        random.Random(hash(s["slug"]) & 0xFFFF).shuffle(rest)
        if s.get("near"):
            lon0, lat0 = s["near"]
            key = lambda c: math.hypot((c["lon"] - lon0) * 85, (c["lat"] - lat0) * 111)
            picks = sorted(picks, key=key)
            rest = sorted(rest, key=key)[:40] if s.get("near_only") else rest
        ok = False
        for cand in (picks + rest)[:12]:
            if cand["name"] in used_names:
                continue
            dest = FRAMES / f"{code}_{src}_{s['slug']}.jpg"
            got, err = (grab_video if src == "video" else grab_snapshot)(cand["url"], dest)
            if not got:
                print(f"  x {cand['name'][:44]:46} {err[:60]}")
                continue
            fine, note = usable(dest)
            if not fine:
                print(f"  x {cand['name'][:44]:46} {note}")
                dest.unlink(missing_ok=True)
                continue
            local = datetime.now(timezone.utc).astimezone(ZoneInfo(TZ[code]))
            used_names.add(cand["name"])
            manifest.append({
                "file": dest.name, "state": code, "source_type": src, "slug": s["slug"],
                "camera": cand["name"], "label": cand["label"], "url": cand["url"],
                "lon": cand["lon"], "lat": cand["lat"], "scene": s["scene"],
                "local_time": local.strftime("%Y-%m-%d %H:%M %Z"),
                "resolution": note, "bytes": dest.stat().st_size,
            })
            print(f"  + {dest.name:44} {note:9} {cand['name'][:40]}")
            ok = True
            break
        if not ok:
            print(f"  !! SLOT FAILED: {s['slug']} ({code})")
    return manifest


SLOTS = [
    # ---- HLS video (12) : TX is non-negotiable, then SC MD MS FL NY HI ----
    dict(state="TX", src="video", slug="houston-ih45-urban-freeway", match="IH-45 Gulf @ Scott", scene="urban freeway, high mount"),
    dict(state="TX", src="video", slug="dallas-ih35e-downtown", match="IH35E @ Reunion", scene="urban freeway downtown, high mount"),
    dict(state="TX", src="video", slug="rural-fm105-vidor", match="FM105 @ FM1132", scene="rural two-lane highway"),
    dict(state="SC", src="video", slug="greenville-i85-freeway", match="I-85 N @ MM 44", scene="urban freeway, high mount"),
    dict(state="SC", src="video", slug="charleston-surface-road", match="Ben Sawyer Blvd", scene="suburban surface road, low mount"),
    dict(state="MD", src="video", slug="dc-intersection", match="Connecticut Ave (MD 185) at East West Hwy", scene="urban signalized intersection, low mount"),
    dict(state="MD", src="video", slug="baltimore-i695-beltway", match="I-695 I/L AT EX 20", scene="urban beltway, high mount"),
    dict(state="MS", src="video", slug="jackson-i20-i220", match="I-20 at I-220", scene="urban freeway interchange"),
    dict(state="MS", src="video", slug="rural-i55-canton", match="I-55 at MS 22", scene="rural interstate"),
    dict(state="FL", src="video", slug="tampa-i75-i4", match="I-75 SBM at I-4", scene="urban freeway interchange"),
    dict(state="NY", src="video", slug="nyc-gowanus-i278", match="I-278 at NY27", scene="dense urban expressway"),
    dict(state="HI", src="video", slug="honolulu-dillingham", match="Dillingham and Puuhale", scene="urban arterial intersection, midday sun"),
    # ---- snapshot JPEG (12) : WA IL AL KY RI NYC, two each ----
    dict(state="WA", src="snapshot", slug="seattle-i5-freeway", match="I-5 at MP 162.9: Spokane St", scene="urban freeway, high mount"),
    dict(state="WA", src="snapshot", slug="rural-snoqualmie-pass", match="I-90 at MP 52: Snoqualmie Summit", scene="rural mountain interstate"),
    dict(state="IL", src="snapshot", slug="chicago-urban", match="K.I.D.S. Camera 9", scene="Chicago urban expressway"),
    dict(state="IL", src="snapshot", slug="tollway-i88-suburban", match="Highland / I-88", scene="suburban tollway ramp"),
    dict(state="AL", src="snapshot", slug="montgomery-i85-urban", match="I-85 at Mulberry St", scene="urban freeway ramps"),
    dict(state="AL", src="snapshot", slug="rural-i65-mp206", match="I-65 at MP 206", scene="rural interstate"),
    dict(state="KY", src="snapshot", slug="louisville-i264-urban", match="I-264 at Newburg", scene="urban freeway, high mount"),
    dict(state="KY", src="snapshot", slug="rural-i24-mp92", match="I-24 WB @ MP 92.6", scene="rural interstate"),
    dict(state="RI", src="snapshot", slug="providence-i195", match="I-195 E @ Rt 114", scene="urban freeway"),
    dict(state="RI", src="snapshot", slug="providence-henderson-bridge", match="Henderson Bridge, Providence", scene="urban bridge/surface, low mount"),
    dict(state="NYC", src="snapshot", slug="manhattan-dense", match="", scene="dense Manhattan street, low mount", near=(-73.985, 40.755), near_only=True),
    dict(state="NYC", src="snapshot", slug="bronx-expressway", match="", scene="outer-borough expressway", near=(-73.87, 40.84), near_only=True),
]

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    slots = [s for s in SLOTS if not only or s["src"] == only]
    print(f"Harvesting {len(slots)} slots at {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n")
    m = harvest(slots)
    out = ROOT / "spike" / "manifest.json"
    prev = json.load(open(out)) if out.exists() else []
    keep = [r for r in prev if r["slug"] not in {x["slug"] for x in m}]
    json.dump(sorted(keep + m, key=lambda r: (r["source_type"], r["state"])), open(out, "w"), indent=1)
    print(f"\n{len(m)}/{len(slots)} slots filled -> {out}")
