"""Score each model against my counts. Overall and split by source type.

The split is the decision-relevant cut: "works on video frames, fails on recompressed
snapshots" would change what ships first, so it is never averaged away.
"""
import json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
det = json.load(open(ROOT / "detections.json"))
rows = json.load(open(ROOT / "manifest.json"))
BUCKETS = ["light", "moderate", "heavy"]


def bucket(n):
    return "light" if n <= 5 else ("moderate" if n <= 15 else "heavy")


def stats(model, subset):
    ae, signed, hits, recall = [], [], 0, []
    for r in subset:
        g, p = r["gt_count"], det[model][r["file"][:-4]]["count"]
        ae.append(abs(p - g))
        signed.append(p - g)
        hits += bucket(p) == r["gt_bucket"]
        if g:
            recall.append(min(p, g) / g)      # generous: assumes every hit is a true hit
    n = len(subset)
    return dict(n=n, mae=sum(ae) / n, bias=sum(signed) / n,
                bucket_acc=100 * hits / n,
                recall=100 * statistics.mean(recall) if recall else float("nan"),
                total_gt=sum(r["gt_count"] for r in subset),
                total_pred=sum(det[model][r["file"][:-4]]["count"] for r in subset))


def table(model):
    vid = [r for r in rows if r["source_type"] == "video"]
    snap = [r for r in rows if r["source_type"] == "snapshot"]
    return {"overall": stats(model, rows), "video": stats(model, vid), "snapshot": stats(model, snap)}


if __name__ == "__main__":
    out = {}
    for m in det:
        out[m] = table(m)
        print(f"\n===== {m} =====")
        print(f"{'subset':10} {'n':>3} {'MAE':>6} {'bias':>7} {'bucket':>8} {'recall':>8} {'found/actual':>14}")
        for k, s in out[m].items():
            print(f"{k:10} {s['n']:3} {s['mae']:6.1f} {s['bias']:+7.1f} "
                  f"{s['bucket_acc']:7.0f}% {s['recall']:7.0f}% {s['total_pred']:6}/{s['total_gt']:<6}")

    print("\n\n===== per-frame (sorted by worst miss, yolov8m) =====")
    print(f"{'frame':46} {'src':4} {'GT':>3} {'8n':>3} {'8m':>3} {'8m err':>7}  bucket 8m")
    for r in sorted(rows, key=lambda r: det["yolov8m"][r["file"][:-4]]["count"] - r["gt_count"]):
        k = r["file"][:-4]
        n, m = det["yolov8n"][k]["count"], det["yolov8m"][k]["count"]
        ok = "OK " if bucket(m) == r["gt_bucket"] else "MISS"
        print(f"{k:46} {r['source_type'][:4]:4} {r['gt_count']:3} {n:3} {m:3} "
              f"{m - r['gt_count']:+7} {ok} {r['gt_bucket']}->{bucket(m)}")

    print("\n\n===== bucket confusion (yolov8m) =====")
    for b in BUCKETS:
        sub = [r for r in rows if r["gt_bucket"] == b]
        got = {x: 0 for x in BUCKETS}
        for r in sub:
            got[bucket(det["yolov8m"][r["file"][:-4]]["count"])] += 1
        print(f"  actual {b:9} (n={len(sub):2}) -> predicted {got}")

    json.dump(out, open(ROOT / "scores.json", "w"), indent=1)
