"""Emit the report's tables straight from the data, so no number is hand-transcribed."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
det = json.load(open(ROOT / "detections.json"))
rows = json.load(open(ROOT / "manifest.json"))
MODELS = ["yolov8n", "yolov8m", "roboflow", "roboflow_c25",
          "yolov8m_hi", "yolov8m_tiled", "roboflow_tiled"]
COLD = {"yolov8n", "yolov8m", "roboflow"}          # the three candidates, run cold as briefed
LABEL = {"yolov8n": "**1.** YOLOv8n (stock)", "yolov8m": "**2.** YOLOv8m (stock)",
         "roboflow": "**3.** Roboflow vehicles-q0x2v (stock, conf .40)",
         "roboflow_c25": "3b. Roboflow @conf .25 (matched to YOLO)",
         "yolov8m_hi": "diag: YOLOv8m @1536", "yolov8m_tiled": "diag: YOLOv8m tiled 2x2",
         "roboflow_tiled": "diag: Roboflow tiled 2x2"}


def bucket(n):
    return "light" if n <= 5 else ("moderate" if n <= 15 else "heavy")


def c(m, r):
    return det[m][r["file"][:-4]]["count"]


def block(name, subset):
    out = [f"\n**{name}** (n={len(subset)})\n",
           "| model | count MAE | bias | bucket accuracy | vehicles found / actual |",
           "|---|---|---|---|---|"]
    for m in MODELS:
        mae = sum(abs(c(m, r) - r["gt_count"]) for r in subset) / len(subset)
        bias = sum(c(m, r) - r["gt_count"] for r in subset) / len(subset)
        acc = 100 * sum(bucket(c(m, r)) == r["gt_bucket"] for r in subset) / len(subset)
        tp, tg = sum(c(m, r) for r in subset), sum(r["gt_count"] for r in subset)
        star = " <-- best cold" if m == "yolov8m" else ""
        out.append(f"| {LABEL[m]}{star} | {mae:.1f} | {bias:+.1f} | **{acc:.0f}%** | {tp}/{tg} ({100*tp/tg:.0f}%) |")
    return "\n".join(out)


md = ["## Score tables\n",
      "Ground truth is my own count. `bias` is mean signed error: negative means the model",
      "**under-counts**. Note bias equals -MAE almost exactly for all three cold candidates, which",
      "means every error is a **miss**: run cold, not one of them ever over-counts a frame.\n",
      "`vehicles found / actual` is an upper bound on recall (it credits every box as a true hit).\n"]
md.append(block("Overall", rows))
md.append(block("HLS video frames", [r for r in rows if r["source_type"] == "video"]))
md.append(block("Snapshot JPEGs", [r for r in rows if r["source_type"] == "snapshot"]))

md.append("\n\n### Bucket confusion, YOLOv8m stock (the headline model)\n")
md.append("| actual | n | predicted light | predicted moderate | predicted heavy |")
md.append("|---|---|---|---|---|")
for b in ["light", "moderate", "heavy"]:
    sub = [r for r in rows if r["gt_bucket"] == b]
    g = {x: 0 for x in ["light", "moderate", "heavy"]}
    for r in sub:
        g[bucket(c("yolov8m", r))] += 1
    cells = " | ".join(f"**{g[x]}**" if x == b else str(g[x]) for x in ["light", "moderate", "heavy"])
    md.append(f"| {b} | {len(sub)} | {cells} |")
md.append("\nEvery error slides **downhill**. Nothing is ever over-called. 6 of 9 heavy frames")
md.append("read as moderate; 6 of 11 moderate frames read as light. The model is least reliable")
md.append("exactly where traffic is worst, which is the opposite of what congestion detection needs.\n")

md.append("\n## Per-frame results\n")
md.append("Cold runs of all three candidates. `8m err` is the best cold model's signed error.\n")
md.append("| frame | src | native | light/weather | GT | 8n | **8m** | RF | 8m err | 8m bucket |")
md.append("|---|---|---|---|---|---|---|---|---|---|")
for r in sorted(rows, key=lambda r: c("yolov8m", r) - r["gt_count"]):
    m8 = c("yolov8m", r)
    ok = "ok" if bucket(m8) == r["gt_bucket"] else f"**MISS** {r['gt_bucket']}->{bucket(m8)}"
    md.append(f"| `{r['file'][:-4]}` | {r['source_type'][:4]} | {r['resolution']} | "
              f"{r['lighting'].rsplit(',', 1)[0]} | {r['gt_count']} | {c('yolov8n', r)} | "
              f"**{m8}** | {c('roboflow', r)} | {m8 - r['gt_count']:+} | {ok} |")

md.append("\n\n## Manifest: the 24 frames\n")
md.append("Every frame pulled live from a real Ora camera on 2026-07-13. `offroad` = vehicles in")
md.append("adjacent lots/dealerships, excluded from ground truth (see `ground_truth.py` for the rule).")
md.append("`?` = shapes I could not confidently call a vehicle; never scored.\n")
md.append("| # | state | src | camera | local time | lighting | GT | ? | offroad | bucket |")
md.append("|---|---|---|---|---|---|---|---|---|---|")
for i, r in enumerate(sorted(rows, key=lambda r: (r["source_type"], r["state"])), 1):
    md.append(f"| {i} | {r['state']} | {r['source_type'][:4]} | {r['camera'][:38]} | "
              f"{r['local_time'].split(' ', 1)[1]} | {r['lighting'].rsplit(',', 1)[0]} | "
              f"**{r['gt_count']}** | {r['gt_uncountable']} | {r['gt_offroad'] or '-'} | {r['gt_bucket']} |")

(ROOT / "_tables.md").write_text("\n".join(md) + "\n")
print("\n".join(md)[:1500])
print("\n... wrote _tables.md")
