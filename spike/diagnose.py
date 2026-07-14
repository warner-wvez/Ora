"""Why does stock YOLO miss? Two candidate causes, and they imply opposite roadmaps.

  SCALE   - vehicles are simply too few pixels once ultralytics letterboxes to imgsz=640.
            Fix is inference-side: raise imgsz, or tile the frame. Cheap, days.
  DOMAIN  - the model sees the vehicles' pixels fine but our compression / weather /
            camera angle make them not look like COCO cars. Fix needs labels. Months.

Same stock weights throughout, no fine-tuning. Only the input scale changes, so any
recovery is attributable to scale alone.

  hi   = imgsz 1536 (one pass, upscaled input)
  tile = 2x2 overlapping tiles at native resolution, each run separately, merged with NMS
         (the standard small-object trick, SAHI-style)
"""
import json
from pathlib import Path
import numpy as np
from ultralytics import YOLO
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "frames"
VEHICLE = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def nms(boxes, thr=0.55):
    """Merge duplicate detections across overlapping tiles."""
    if not boxes:
        return []
    b = sorted(boxes, key=lambda x: -x[5])
    keep = []
    while b:
        best = b.pop(0)
        keep.append(best)
        out = []
        for c in b:
            xx1, yy1 = max(best[0], c[0]), max(best[1], c[1])
            xx2, yy2 = min(best[2], c[2]), min(best[3], c[3])
            w, h = max(0, xx2 - xx1), max(0, yy2 - yy1)
            inter = w * h
            a1 = (best[2] - best[0]) * (best[3] - best[1])
            a2 = (c[2] - c[0]) * (c[3] - c[1])
            iou = inter / (a1 + a2 - inter + 1e-9)
            # tiles cut vehicles in half, so also drop a box mostly contained in a bigger one
            if iou < thr and inter / (min(a1, a2) + 1e-9) < 0.7:
                out.append(c)
        b = out
    return keep


def boxes_of(res):
    out = []
    for bx in res.boxes:
        cid = int(bx.cls)
        if cid in VEHICLE:
            x1, y1, x2, y2 = [float(v) for v in bx.xyxy[0]]
            out.append([x1, y1, x2, y2, cid, float(bx.conf)])
    return out


def tiled(model, path, rows=2, cols=2, overlap=0.2):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    tw, th = W / cols, H / rows
    ox, oy = tw * overlap, th * overlap
    all_b = []
    for r in range(rows):
        for c in range(cols):
            x0, y0 = max(0, c * tw - ox), max(0, r * th - oy)
            x1, y1 = min(W, (c + 1) * tw + ox), min(H, (r + 1) * th + oy)
            crop = im.crop((int(x0), int(y0), int(x1), int(y1)))
            # upscale the tile so a 20px car becomes a 60px car
            s = min(3.0, 1280 / max(crop.width, crop.height))
            crop = crop.resize((int(crop.width * s), int(crop.height * s)), Image.LANCZOS)
            res = model(np.array(crop)[:, :, ::-1], verbose=False)[0]
            for b in boxes_of(res):
                all_b.append([b[0] / s + x0, b[1] / s + y0, b[2] / s + x0, b[3] / s + y0, b[4], b[5]])
    return nms(all_b)


def draw(src, dets, out, tag):
    im = Image.open(src).convert("RGB")
    s = max(1, round(1100 / im.width))
    im = im.resize((im.width * s, im.height * s), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for x1, y1, x2, y2, cid, conf in dets:
        d.rectangle([x1 * s, y1 * s, x2 * s, y2 * s], outline=(0, 255, 120), width=2)
    d.rectangle([0, 0, im.width, 18], fill=(0, 0, 0))
    d.text((4, 4), f"{tag}: {len(dets)} vehicles", fill=(255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=92)


if __name__ == "__main__":
    model = YOLO("yolov8m.pt")
    res = json.load(open(ROOT / "detections.json"))
    res.setdefault("yolov8m_hi", {})
    res.setdefault("yolov8m_tiled", {})
    for f in sorted(FRAMES.glob("*.jpg")):
        hi = boxes_of(model(str(f), imgsz=1536, verbose=False)[0])
        tl = tiled(model, f)
        draw(f, hi, ROOT / "annotated" / "yolov8m_hi" / f.name, "yolov8m @1536")
        draw(f, tl, ROOT / "annotated" / "yolov8m_tiled" / f.name, "yolov8m tiled 2x2")
        res["yolov8m_hi"][f.stem] = {"count": len(hi), "by_class": {}, "confs": []}
        res["yolov8m_tiled"][f.stem] = {"count": len(tl), "by_class": {}, "confs": []}
        print(f"  {f.stem:46} hi={len(hi):3}  tiled={len(tl):3}")
    json.dump(res, open(ROOT / "detections.json", "w"), indent=1)
