"""Overlay a labelled grid on a magnified frame, so counting is systematic.

Counting a busy freeway by eye invites double counting and misses. A grid lets each cell
be enumerated once, in order, and the totals add up.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "zoom"
OUT.mkdir(exist_ok=True)

name = sys.argv[1]
cols = int(sys.argv[2]) if len(sys.argv) > 2 else 6
rows = int(sys.argv[3]) if len(sys.argv) > 3 else 4

im = Image.open(ROOT / "frames" / name).convert("RGB")
s = 1450 / im.width
im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
d = ImageDraw.Draw(im)
W, H = im.size
for c in range(1, cols):
    d.line([(W * c / cols, 0), (W * c / cols, H)], fill=(0, 255, 255), width=1)
for r in range(1, rows):
    d.line([(0, H * r / rows), (W, H * r / rows)], fill=(0, 255, 255), width=1)
for r in range(rows):
    for c in range(cols):
        d.text((W * c / cols + 4, H * r / rows + 2), f"{chr(65+r)}{c+1}", fill=(0, 255, 255))
p = OUT / f"{Path(name).stem}_grid.jpg"
im.save(p, quality=95)
print(p.name, im.size)
