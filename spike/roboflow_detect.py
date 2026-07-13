"""Candidate 3: the Roboflow Universe vehicles model (roboflow-100/vehicles-q0x2v).

Hosted inference, stock weights, no fine-tuning. All 12 of its classes are vehicles
(car / small-mid-big truck / small-big bus), so every prediction counts and there is no
class filtering to do.

Threshold note. Roboflow's hosted API defaults to confidence=0.40; ultralytics defaults to
0.25. Scoring it only at its own default would confound "different model" with "different
threshold", so this runs both:
    roboflow      - its own stock default (the honest cold run)
    roboflow_c25  - confidence 0.25, matched to YOLO, for an apples-to-apples read
Neither is tuned per frame or per state.

The API key is read from the ROBOFLOW_API_KEY env var and is never written to disk.
"""
import base64, json, os, sys, time
from pathlib import Path
import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "frames"
MODEL = "vehicles-q0x2v/1"
KEY = os.environ.get("ROBOFLOW_API_KEY")
if not KEY:
    sys.exit("ROBOFLOW_API_KEY not set. Free key: app.roboflow.com -> Settings -> API Keys.")


def infer(path, conf=None):
    """POST the frame to the hosted model. conf=None means use Roboflow's own default."""
    b64 = base64.b64encode(path.read_bytes())
    url = f"https://serverless.roboflow.com/{MODEL}?api_key={KEY}"
    if conf is not None:
        url += f"&confidence={conf}"
    for attempt in range(4):
        r = requests.post(url, data=b64,
                          headers={"Content-Type": "application/x-www-form-urlencoded"},
                          timeout=90)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"{path.name}: HTTP {r.status_code} {r.text[:160]}")
    raise RuntimeError(f"{path.name}: retries exhausted")


def draw(src, preds, out, tag):
    im = Image.open(src).convert("RGB")
    s = max(1, round(1100 / im.width))
    im = im.resize((im.width * s, im.height * s), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for p in preds:
        x, y, w, h = p["x"], p["y"], p["width"], p["height"]
        box = [(x - w / 2) * s, (y - h / 2) * s, (x + w / 2) * s, (y + h / 2) * s]
        d.rectangle(box, outline=(255, 120, 0), width=2)
        d.text((box[0] + 2, max(0, box[1] - 10)), f"{p['class'][:6]} {p['confidence']:.2f}",
               fill=(255, 120, 0))
    d.rectangle([0, 0, im.width, 18], fill=(0, 0, 0))
    d.text((4, 4), f"{tag}: {len(preds)} vehicles", fill=(255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=92)


if __name__ == "__main__":
    res = json.load(open(ROOT / "detections.json"))
    for tag, conf in [("roboflow", None), ("roboflow_c25", 25)]:
        res.setdefault(tag, {})
        label = "roboflow (stock conf .40)" if conf is None else "roboflow @conf .25"
        print(f"\n=== {label} ===")
        for f in sorted(FRAMES.glob("*.jpg")):
            preds = infer(f, conf)["predictions"]
            draw(f, preds, ROOT / "annotated" / tag / f.name, label)
            by = {}
            for p in preds:
                by[p["class"]] = by.get(p["class"], 0) + 1
            res[tag][f.stem] = {"count": len(preds), "by_class": by,
                                "confs": sorted((round(p["confidence"], 3) for p in preds),
                                                reverse=True)}
            print(f"  {f.stem:46} {len(preds):3}  {by}")
        json.dump(res, open(ROOT / "detections.json", "w"), indent=1)
    print("\nwrote detections.json")


# ---- appended: same 2x2 tiling that rescued YOLO, applied to Roboflow ----
# If Roboflow were scale-limited like YOLO, tiling would rescue it too. If it stays broken,
# its failure is generalization, not scale, and the two models fail for different reasons.
def tiled_rf(path, rows=2, cols=2, overlap=0.2):
    from diagnose import nms
    im = Image.open(path).convert("RGB")
    W, H = im.size
    tw, th = W / cols, H / rows
    ox, oy = tw * overlap, th * overlap
    out = []
    for r in range(rows):
        for c in range(cols):
            x0, y0 = max(0, c * tw - ox), max(0, r * th - oy)
            x1, y1 = min(W, (c + 1) * tw + ox), min(H, (r + 1) * th + oy)
            crop = im.crop((int(x0), int(y0), int(x1), int(y1)))
            s = min(3.0, 1280 / max(crop.width, crop.height))
            crop = crop.resize((int(crop.width * s), int(crop.height * s)), Image.LANCZOS)
            tmp = ROOT / "_tile.jpg"
            crop.save(tmp, quality=95)
            for p in infer(tmp, 25)["predictions"]:
                x, y, w, h = p["x"] / s + x0, p["y"] / s + y0, p["width"] / s, p["height"] / s
                out.append([x - w / 2, y - h / 2, x + w / 2, y + h / 2, 0, p["confidence"]])
            tmp.unlink(missing_ok=True)
    return nms(out)


def run_tiled():
    res = json.load(open(ROOT / "detections.json"))
    res.setdefault("roboflow_tiled", {})
    print("\n=== roboflow tiled 2x2 @conf .25 ===")
    for f in sorted(FRAMES.glob("*.jpg")):
        b = tiled_rf(f)
        preds = [{"x": (d[0] + d[2]) / 2, "y": (d[1] + d[3]) / 2, "width": d[2] - d[0],
                  "height": d[3] - d[1], "confidence": d[5], "class": "veh"} for d in b]
        draw(f, preds, ROOT / "annotated" / "roboflow_tiled" / f.name, "roboflow tiled 2x2")
        res["roboflow_tiled"][f.stem] = {"count": len(b), "by_class": {}, "confs": []}
        print(f"  {f.stem:46} {len(b):3}")
    json.dump(res, open(ROOT / "detections.json", "w"), indent=1)
