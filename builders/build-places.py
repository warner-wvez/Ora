#!/usr/bin/env python3
"""
Build the place details the map shows when a landmark is tapped, from Overture Maps Places.

Overture publishes about 81 million places (names, categories, addresses, phones, websites)
as GeoParquet on S3, mostly under CDLA Permissive 2.0, with Foursquare's share under
Apache 2.0 and AllThePlaces' under CC0. DuckDB reads only the rows inside the bounding box,
so a region comes down in seconds to minutes with no bulk download (downtown Seattle,
16,721 places, took 2.9 s).

The output is static: one small JSON file per web-map tile at zoom 15 (about 800 m across at
Seattle's latitude), so a tap fetches one or two files and needs no server. Places under the
confidence cutoff are dropped (Overture's own estimate that the place exists; "Pike Place
Pigs" scored 0.05), and so are permanently closed ones.

Usage:  uv run --no-project --with duckdb python builders/build-places.py [--bbox W,S,E,N] [--release R]
Writes: places/index.json and places/15/<x>/<y>.json (not committed; see .gitignore)
Needs:  DuckDB (fetched by uv), network access to s3://overturemaps-us-west-2
"""
import argparse, json, math, os, shutil, time
from collections import defaultdict

import duckdb

RELEASE = "2026-10-21.0"                       # docs.overturemaps.org release calendar
WA = (-124.85, 45.54, -116.91, 49.01)          # Washington state, loose box
Z = 15
MIN_CONFIDENCE = 0.5
FIELDS = ["name", "category", "street", "city", "region", "zip", "phone", "website", "brand", "confidence", "lon", "lat"]


def tile_of(lon, lat, z=Z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    r = math.radians(lat)
    y = int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)
    return x, y


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bbox", default=",".join(map(str, WA)), help="W,S,E,N in degrees")
    ap.add_argument("--release", default=RELEASE)
    ap.add_argument("--out", default="places")
    a = ap.parse_args()
    w, s, e, n = map(float, a.bbox.split(","))

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    src = f"s3://overturemaps-us-west-2/release/{a.release}/theme=places/type=place/*"
    t = time.time()
    rows = con.execute(f"""
        SELECT names.primary, coalesce(basic_category, taxonomy.primary),
               addresses[1].freeform, addresses[1].locality, addresses[1].region, addresses[1].postcode,
               phones[1], websites[1], brand.names.primary, round(confidence, 2),
               round(ST_X(geometry), 6), round(ST_Y(geometry), 6)
        FROM read_parquet('{src}', hive_partitioning=1)
        WHERE bbox.xmin BETWEEN {w} AND {e} AND bbox.ymin BETWEEN {s} AND {n}   -- points: the min corner is the point
          AND confidence >= {MIN_CONFIDENCE}
          AND coalesce(operating_status, 'open') <> 'permanently_closed'
          AND names.primary IS NOT NULL
    """).fetchall()
    print(f"{len(rows):,} places in {time.time() - t:.0f}s from release {a.release}")

    tiles = defaultdict(list)
    for r in rows:
        tiles[tile_of(r[10], r[11])].append([v if v != "" else None for v in r])

    if os.path.isdir(a.out):
        shutil.rmtree(a.out)
    for (x, y), items in tiles.items():
        d = os.path.join(a.out, str(Z), str(x))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{y}.json"), "w") as f:
            json.dump(items, f, separators=(",", ":"), ensure_ascii=False)
    index = {
        "release": a.release, "z": Z, "bbox": [w, s, e, n], "count": len(rows), "tiles": len(tiles),
        "fields": FIELDS, "min_confidence": MIN_CONFIDENCE, "built": time.strftime("%Y-%m-%d"),
        "attribution": "Overture Maps Foundation (Meta, Microsoft, Foursquare, AllThePlaces and others)",
        "attribution_url": "https://docs.overturemaps.org/attribution/",
    }
    with open(os.path.join(a.out, "index.json"), "w") as f:
        json.dump(index, f, indent=1)
    size = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fns in os.walk(a.out) for fn in fns)
    print(f"{len(tiles):,} tile files, {size / 1e6:.0f} MB in {a.out}/")


if __name__ == "__main__":
    main()
