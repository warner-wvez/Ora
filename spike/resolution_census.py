"""How many of Ora's ~46,100 cameras can actually support vehicle detection?

The spike found the binding constraint is delivered resolution, not the model: at >=640px
stock YOLO works, at ~320px nothing does. That makes "what resolution does each camera
actually deliver" the roadmap question, so measure it across the network rather than
guessing from the 24 test frames.

Samples a few cameras per state, records the real delivered pixel size.
Snapshots: fetch and read the header. Video: ffprobe the HLS variant.
"""
import json, random, subprocess, io, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
PER_STATE = int(sys.argv[1]) if len(sys.argv) > 1 else 4
EXTRA = {"IL": ROOT / "cameras.json", "NYC": ROOT / "cameras-nyc.json"}


def snap_dims(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15, stream=True)
        if r.status_code != 200 or "image" not in r.headers.get("content-type", ""):
            return None
        im = Image.open(io.BytesIO(r.content))
        return im.size
    except Exception:
        return None


def video_dims(url):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-user_agent", UA, "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", url],
            capture_output=True, timeout=45)
        t = r.stdout.decode().strip().split("\n")[0]
        w, h = t.split(",")[:2]
        return (int(w), int(h))
    except Exception:
        return None


def probe(job):
    code, kind, url = job
    d = video_dims(url) if kind == "video" else snap_dims(url)
    return code, kind, d


def jobs_for(code, path):
    d = json.load(open(path))
    vids, snaps = [], []
    for f in d["features"]:
        for dr in f["properties"]["directions"]:
            if dr.get("video"):
                vids.append(dr["video"])
            cid = dr.get("camId")
            s = dr.get("snapshot") or (f"https://webcams.nyctmc.org/api/cameras/{cid}/image"
                                       if code == "NYC" and cid else None)
            if s:
                snaps.append(s)
    rnd = random.Random(hash(code) & 0xFFFF)
    out = []
    if vids:
        out += [(code, "video", u) for u in rnd.sample(vids, min(PER_STATE, len(vids)))]
    if snaps:
        out += [(code, "snapshot", u) for u in rnd.sample(snaps, min(PER_STATE, len(snaps)))]
    return out


if __name__ == "__main__":
    idx = json.load(open(ROOT / "states" / "index.json"))
    counts = {c: v["count"] for c, v in idx.items()}
    counts["IL"], counts["NYC"] = 1328, 957
    jobs = []
    for code, v in idx.items():
        jobs += jobs_for(code, ROOT / v["file"])
    for code, p in EXTRA.items():
        jobs += jobs_for(code, p)
    print(f"probing {len(jobs)} cameras across {len(counts)} layers ...")

    res = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for code, kind, dims in ex.map(probe, jobs):
            res.setdefault(code, {"video": [], "snapshot": []})
            if dims:
                res[code][kind].append(dims)

    out = {}
    for code, v in sorted(res.items()):
        for kind in ("video", "snapshot"):
            dims = v[kind]
            if not dims:
                continue
            widths = sorted(d[0] for d in dims)
            med = widths[len(widths) // 2]
            out.setdefault(code, {})[kind] = {
                "n": len(dims), "median_width": med,
                "sizes": sorted({f"{w}x{h}" for w, h in dims}),
                "tier": "workable (>=640px)" if med >= 640 else "blind (<640px)"}
    json.dump({"cameras": counts, "probe": out}, open(Path(__file__).parent / "resolution_census.json", "w"), indent=1)

    # A state is judged on the fraction of its sampled cameras that cleared 640px, not on
    # its best camera: several states ship a mix, and the best one flatters the whole state.
    tally = {"workable": 0, "mixed": 0, "blind": 0, "unknown": 0}
    print(f"\n{'state':5} {'cams':>6}  {'median':>8} {'>=640':>6}  {'tier':9} sizes seen")
    for code, n in sorted(counts.items(), key=lambda x: -x[1]):
        p = out.get(code, {})
        if not p:
            tally["unknown"] += n
            print(f"{code:5} {n:6}  {'-':>8} {'-':>6}  {'unknown':9}")
            continue
        widths = [int(s.split("x")[0]) for v in p.values() for s in v["sizes"]]
        frac = sum(w >= 640 for w in widths) / len(widths)
        med = sorted(widths)[len(widths) // 2]
        tier = "workable" if frac >= 0.5 else ("mixed" if frac > 0 else "blind")
        tally[tier] += n
        sizes = ", ".join(sorted({s for v in p.values() for s in v["sizes"]}))[:30]
        print(f"{code:5} {n:6}  {med:7}px {100*frac:5.0f}%  {tier:9} {sizes}")

    tot = sum(tally.values())
    print(f"\n  {'tier':9} {'cameras':>7}   share    (>=640px is NECESSARY for detection,")
    for k in ("workable", "mixed", "blind", "unknown"):
        print(f"  {k:9} {tally[k]:7}   {100*tally[k]/tot:3.0f}%")
    print(f"  {'TOTAL':9} {tot:7}            but NOT sufficient: a 720px tower PTZ zoomed")
    print("                                 far out still renders 6px vehicles.)")
