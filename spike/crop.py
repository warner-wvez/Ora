"""Crop a fractional region of a frame and blow it up, for close counting.

usage: crop.py <frame.jpg> <x0> <y0> <x1> <y1>   (fractions of width/height, 0-1)
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "zoom"
OUT.mkdir(exist_ok=True)

name, x0, y0, x1, y1 = sys.argv[1], *map(float, sys.argv[2:6])
im = Image.open(ROOT / "frames" / name).convert("RGB")
w, h = im.size
box = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
c = im.crop(box)
s = min(1500 / c.width, 1100 / c.height)
c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
tag = f"{Path(name).stem}_crop_{x0}_{y0}_{x1}_{y1}.jpg"
c.save(OUT / tag, quality=95)
print(OUT / tag, c.size)
