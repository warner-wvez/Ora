#!/usr/bin/env python3
"""Crop the Regular Show character art into one avatar sprite (WebP) for Ora's officer shifts. Run once,
locally (the art lives on Warner's Mac): uv run --no-project --with pillow python scripts/build-officer-sprite.py SRC
SRC holds avatars/character-order.json and avatars/img/*.png (160x200 full-body art)."""
import json, os, re, sys
from PIL import Image

CELL, COLS = 80, 20
src = sys.argv[1]
order = json.load(open(os.path.join(src, "avatars/character-order.json")))
img_dir = os.path.join(src, "avatars/img")
slug = lambda name: re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
have = {f[:-4]: f for f in os.listdir(img_dir) if f.endswith(".png")}
chars = [c["character"] for c in order if slug(c["character"]) in have]
rows = (len(chars) + COLS - 1) // COLS
sheet = Image.new("RGBA", (COLS * CELL, rows * CELL), (0, 0, 0, 0))
out = []
for s, name in enumerate(chars):
    im = Image.open(os.path.join(img_dir, have[slug(name)])).convert("RGBA").resize((160, 200))
    face = im.crop((34, 9, 126, 101)).resize((CELL, CELL), Image.LANCZOS)
    sheet.paste(face, ((s % COLS) * CELL, (s // COLS) * CELL), face)
    out.append({"character": name, "s": s})
os.makedirs("chicago-officers", exist_ok=True)
sheet.save("chicago-officers/avatars.webp", "WEBP", quality=80, method=6)   # about 600 KB; the PNG was 3.5 MB
json.dump(out, open("chicago-officers/characters.json", "w"), indent=0)
print(f"{len(out)} characters, sprite {sheet.size[0]}x{sheet.size[1]}, missing art: {len(order) - len(out)}")
