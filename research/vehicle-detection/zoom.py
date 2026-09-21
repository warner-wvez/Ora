"""Magnify frames so vehicle counting is done on what is actually resolvable.

Ora frames run 320x240 to 1920x1080. Counting a 6-pixel car on a 320x240 Texas frame at
native size invents errors that belong to the viewer, not the model, so every frame is
resampled to a common working width, and dense scenes are additionally split into
overlapping halves.
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "zoom"
OUT.mkdir(exist_ok=True)
WORK = 1400  # vision downsamples past ~1568px; anything wider is wasted pixels


def fit(im, width=WORK):
    w, h = im.size
    s = width / w
    return im.resize((int(w * s), int(h * s)), Image.LANCZOS)


def run(name, split=False):
    src = ROOT / "frames" / name
    im = Image.open(src).convert("RGB")
    stem = src.stem
    p = OUT / f"{stem}_full.jpg"
    fit(im).save(p, quality=95)
    print(p.name, im.size, "->", fit(im).size)
    if split:
        w, h = im.size
        ov = int(h * 0.10)
        for tag, box in [("top", (0, 0, w, h // 2 + ov)), ("bot", (0, h // 2 - ov, w, h))]:
            q = OUT / f"{stem}_{tag}.jpg"
            fit(im.crop(box)).save(q, quality=95)
            print(q.name)


if __name__ == "__main__":
    args = sys.argv[1:]
    split = "split" in args
    names = [a for a in args if a != "split"]
    if not names:
        names = sorted(p.name for p in (ROOT / "frames").glob("*.jpg"))
    for n in names:
        run(n, split)
