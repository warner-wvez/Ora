"""My (Claude's) vehicle counts per frame, done by eye on magnified crops.

RULE, applied uniformly:
  count      = vehicles ON THE ROADWAY (carriageways, ramps, shoulders, cross streets,
               on-street parked) that I can confidently resolve as an individual vehicle
               at 4x magnification. A vehicle is a vehicle: no car/truck/bus distinction.
  uncountable= shapes too small or too blurred for me to call a vehicle with confidence
               (vanishing-point specks, background decks). Reported, never scored.
  offroad    = vehicles clearly OFF the roadway (dealership lots, equipment yards,
               parking lots). EXCLUDED from the count and tracked separately, because the
               product's question is "how much traffic is on this road", and lot inventory
               is not traffic. A detector that fires on it is failing the product task,
               which is exactly what this spike needs to surface, so it is measured, not
               hidden inside ground truth.

bucket: light 0-5, moderate 6-15, heavy 16+
"""

GT = {
    # ---------------- HLS video ----------------
    "TX_video_houston-ih45-urban-freeway": dict(
        count=23, uncountable=12, offroad=0,
        light="overcast, hazy, wet pavement, 17:48 CDT",
        note="320x240, the lowest resolution in the set; haze flattens the far half"),
    "TX_video_dallas-ih35e-downtown": dict(
        count=23, uncountable=14, offroad=0,
        light="overcast, wet pavement, 17:49 CDT",
        note="stacked viaducts; far elevated deck traffic is unresolvable"),
    "TX_video_rural-fm105-vidor": dict(
        count=0, uncountable=2, offroad=0,
        light="overcast after rain, standing water, 17:48 CDT",
        note="empty road; bright green chroma-compression blobs on the pavement"),
    "SC_video_greenville-i85-freeway": dict(
        count=14, uncountable=3, offroad=12,
        light="overcast, wet pavement, 18:48 EDT",
        note="equipment dealership along the left shoulder: ~12 parked vehicles + machinery"),
    "SC_video_charleston-surface-road": dict(
        count=1, uncountable=0, offroad=0,
        light="sunny with cloud, 18:48 EDT",
        note="near-empty surface road; one pedestrian on the shoulder"),
    "MD_video_dc-intersection": dict(
        count=7, uncountable=2, offroad=0,
        light="low sun, heavy backlight and haze, 18:49 EDT",
        note="low mount, dense pole/signal clutter, large lens smudge across the frame"),
    "MD_video_baltimore-i695-beltway": dict(
        count=11, uncountable=2, offroad=0,
        light="bright sun, hard shadows, 18:49 EDT",
        note="interchange loop plus a service road/gate area"),
    "MS_video_jackson-i20-i220": dict(
        count=18, uncountable=8, offroad=0,
        light="overcast, storm sky, wet, 17:49 CDT",
        note="tower PTZ over a full cloverleaf: vehicles are 5-10px"),
    "MS_video_rural-i55-canton": dict(
        count=4, uncountable=3, offroad=30,
        light="overcast, storm sky, 17:49 CDT",
        note="car dealership lot at frame left holds ~30 parked cars"),
    "FL_video_tampa-i75-i4": dict(
        count=13, uncountable=6, offroad=0,
        light="overcast, storm sky, 18:49 EDT",
        note="352x240; wide median, vehicles small past mid-frame"),
    "NY_video_nyc-gowanus-i278": dict(
        count=25, uncountable=15, offroad=0,
        light="low sun, strong backlight haze, 18:49 EDT",
        note="352x240; dense expressway plus an elevated deck and a surface street"),
    "HI_video_honolulu-dillingham": dict(
        count=14, uncountable=3, offroad=0,
        light="bright midday sun, clear, 12:49 HST",
        note="low mount, queued traffic, large foreground vehicles: the easiest frame here"),
    # ---------------- snapshot JPEG ----------------
    "WA_snapshot_seattle-i5-freeway": dict(
        count=15, uncountable=4, offroad=0,
        light="bright sun, hard shadow, 15:59 PDT",
        note="335x249; stacked ramp over mainline"),
    "WA_snapshot_rural-snoqualmie-pass": dict(
        count=8, uncountable=3, offroad=0,
        light="bright sun, pavement blown out white, 15:47 PDT",
        note="320x239; dark vehicles on overexposed concrete"),
    "IL_snapshot_chicago-urban": dict(
        count=35, uncountable=10, offroad=0,
        light="bright evening sun, 17:43 CDT",
        note="elevated Dan Ryan deck; heavy interlace comb artifacts on every moving car"),
    "IL_snapshot_tollway-i88-suburban": dict(
        count=13, uncountable=5, offroad=0,
        light="bright low sun, hard shadows, 17:54 CDT",
        note="360x240; the distant intersection is a compression smear"),
    "AL_snapshot_montgomery-i85-urban": dict(
        count=30, uncountable=6, offroad=8,
        light="overcast bright, 17:54 CDT",
        note="1280x720, the cleanest pixels in the set; rush-hour freeway plus two semis"),
    "AL_snapshot_rural-i65-mp206": dict(
        count=6, uncountable=3, offroad=0,
        light="overcast, hazy, 17:54 CDT",
        note="1280x720; near-empty rural interstate"),
    "KY_snapshot_louisville-i264-urban": dict(
        count=21, uncountable=5, offroad=6,
        light="golden hour, low sun into lens, 18:48 EDT",
        note="1280x720; rainbow lens-flare blobs across the right of frame"),
    "KY_snapshot_rural-i24-mp92": dict(
        count=28, uncountable=6, offroad=0,
        light="hazy low sun, 17:48 CDT (western KY is Central)",
        note="active work zone: orange barrels everywhere, queued traffic"),
    "RI_snapshot_providence-i195": dict(
        count=15, uncountable=6, offroad=0,
        light="soft evening light, 18:48 EDT",
        note="clean view down a 6-lane freeway"),
    "RI_snapshot_providence-henderson-bridge": dict(
        count=5, uncountable=1, offroad=0,
        light="soft evening light, 18:48 EDT",
        note="~60% of the frame is tree canopy; road empty, cars parked on-street"),
    "NYC_snapshot_manhattan-dense": dict(
        count=17, uncountable=4, offroad=0,
        light="evening, shaded canyon, 18:48 EDT",
        note="352x240; taxis, a fire truck, a food cart and dozens of pedestrians"),
    "NYC_snapshot_bronx-expressway": dict(
        count=13, uncountable=3, offroad=0,
        light="low sun, backlit, deep shadow under canopy, 18:48 EDT",
        note="1920x1080, the highest resolution; half the frame is dark tree canopy"),
}


def bucket(n):
    return "light" if n <= 5 else ("moderate" if n <= 15 else "heavy")


if __name__ == "__main__":
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent / "manifest.json"
    rows = json.load(open(p))
    missing = [r["file"][:-4] for r in rows if r["file"][:-4] not in GT]
    assert not missing, f"no ground truth for: {missing}"
    for r in rows:
        g = GT[r["file"][:-4]]
        r.update(gt_count=g["count"], gt_bucket=bucket(g["count"]),
                 gt_uncountable=g["uncountable"], gt_offroad=g["offroad"],
                 lighting=g["light"], note=g["note"])
    json.dump(rows, open(p, "w"), indent=1)
    import collections
    c = collections.Counter(r["gt_bucket"] for r in rows)
    tot = collections.Counter(r["source_type"] for r in rows)
    print(f"{len(rows)} frames  buckets={dict(c)}  sources={dict(tot)}")
    print(f"total vehicles counted: {sum(r['gt_count'] for r in rows)}")
