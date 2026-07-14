"""Run stock YOLO on the harvested frames. Cold: no fine-tuning, no threshold tinkering.

Everything is ultralytics' own default (conf=0.25, iou=0.7, imgsz=640). The point of the
spike is what off-the-shelf gives you on our pixels, so tuning here would answer a
different question.

A vehicle is a vehicle: COCO car / motorcycle / bus / truck are summed, classes are not
scored. Boxes are drawn to spike/annotated/<model>/ so every count can be eyeballed.
"""
import json, sys
from pathlib import Path
from ultralytics import YOLO
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "frames"
VEHICLE = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
COLORS = {2: (0, 220, 255), 3: (255, 0, 200), 5: (255, 200, 0), 7: (0, 255, 120)}


def draw(src, dets, out):
    im = Image.open(src).convert("RGB")
    s = max(1, round(1100 / im.width))          # upscale small frames so boxes are legible
    im = im.resize((im.width * s, im.height * s), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for x1, y1, x2, y2, cid, conf in dets:
        c = COLORS[cid]
        d.rectangle([x1 * s, y1 * s, x2 * s, y2 * s], outline=c, width=2)
        d.text((x1 * s + 2, max(0, y1 * s - 10)), f"{VEHICLE[cid][:3]} {conf:.2f}", fill=c)
    d.rectangle([0, 0, im.width, 18], fill=(0, 0, 0))
    d.text((4, 4), f"{out.parent.name}: {len(dets)} vehicles", fill=(255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=92)


def run(weights, tag):
    model = YOLO(weights)
    out = {}
    for f in sorted(FRAMES.glob("*.jpg")):
        r = model(str(f), verbose=False)[0]              # stock defaults, CPU
        dets = []
        for b in r.boxes:
            cid = int(b.cls)
            if cid in VEHICLE:
                x1, y1, x2, y2 = [float(v) for v in b.xyxy[0]]
                dets.append((x1, y1, x2, y2, cid, float(b.conf)))
        draw(f, dets, ROOT / "annotated" / tag / f.name)
        by_cls = {}
        for *_, cid, _c in dets:
            by_cls[VEHICLE[cid]] = by_cls.get(VEHICLE[cid], 0) + 1
        out[f.stem] = {"count": len(dets), "by_class": by_cls,
                       "confs": sorted((round(d[5], 3) for d in dets), reverse=True)}
        print(f"  {f.stem:46} {len(dets):3}  {by_cls}")
    return out


if __name__ == "__main__":
    models = [("yolov8n.pt", "yolov8n"), ("yolov8m.pt", "yolov8m")]
    if len(sys.argv) > 1:
        models = [m for m in models if m[1] == sys.argv[1]]
    res = {}
    p = ROOT / "detections.json"
    if p.exists():
        res = json.load(open(p))
    for w, tag in models:
        print(f"\n=== {tag} (stock COCO, defaults) ===")
        res[tag] = run(w, tag)
        json.dump(res, open(p, "w"), indent=1)
    print(f"\nwrote {p}")
