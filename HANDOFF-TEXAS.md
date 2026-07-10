# Ora — Texas: DONE

Texas shipped: **3,430 live-video cameras**, built by `build-states-tx.py` into
`states/TX.json`. No manual coordinate hunting was needed — the coordinates were
in the MapLarge API the whole time.

This file is kept as a correction, because the previous handoff sent the
investigation down a dead end. If you are re-reading old notes, ignore them and
trust this.

## What the old handoff got wrong

It listed three "verified" blockers. All three were false:

1. **"Statewide queries return HTTP 500 — only small polygons work."**
   Wrong. The `where` / `DWithin` clause was what 500'd, at *every* polygon size.
   Drop the `where` clause entirely and the full table pages cleanly with
   `start`/`take`. There is no area restriction.

2. **"No coordinates in the response — `allGeo` comes back empty."**
   Wrong. `allGeo` is always `{}`, but `XY` is a real, selectable column. Name it
   in `sqlselect` and every row returns `"POINT (lng lat)"` as WKT. The old
   `sqlselect` simply never asked for it.

3. **"Need a coordinate source / grid-crawl / tile-decode."**
   All unnecessary. Nothing was scraped, geocoded, or approximated.

The trap: **this API answers any malformed or unrecognized query with a bare
HTTP 500 and a generic HTML error page.** An unknown key, a bad `where`, and a
genuine server fault are indistinguishable. The old notes tested a bad `where`
alongside a bad `sqlselect` and concluded the *data* was missing, when only the
*request* was wrong. Change one variable at a time against this endpoint.

## What is actually true

- Table id **rotates between calls** — resolve it fresh every run:
  `GET /Remote/GetActiveTableID?shortTableId=appgeo%2FcameraPoint`
- A `table/query` with **no `sqlselect`** returns all 20 columns, and `totals.Records`
  gives the row count. That is the way to discover the schema.
- Coordinates: `sqlselect: [... , "XY"]` → `POINT (lng lat)`.
- Snapshots genuinely do not exist: `imageurl` is a `https://localhost/thumbs/...`
  placeholder. Texas is the only **video-only** state in Ora.
- Streams are SkyVDN HLS across 10 hosts (`s69`–`s78`), `Access-Control-Allow-Origin: *`
  on both playlist and segments, verified from a foreign origin. Hence `video: true`.
  The host number is baked into `httpsurl` per camera — do not guess it.

## Stream health (measured, 150-camera sample)

**~93% of cameras are healthy.** ~7% fail; about a third of those recover on retry,
so **~5% are persistently dead** (they 404 once, then hang forever). This is normal
for a DOT network this size and is handled at runtime, not at build time — a camera
that is dead today may be alive tomorrow, so `build-states-tx.py` does not prune them.

**The dead ones hang rather than error.** hls.js emits `MANIFEST_LOADING` and then
nothing at all — no `ERROR`, no fatal — even after 40s, despite
`manifestLoadingTimeOut: 10000`. Relying on the hls.js error event is therefore not
enough. `playDir()` in `index.html` carries a 12s watchdog that shows the offline
state when no fragment ever loads; it is cleared on `FRAG_LOADED` and in
`destroyPopupHls()`. Do not remove it — without it a dead Texas camera sits as a
blank dark box behind a red LIVE badge, indefinitely.

## Code notes (already done)

`index.html` handles `snapshot: null` throughout: the popup skips the poster `<img>`
and plays over a dark backdrop (`.noposter`), the route view shows a "Live video"
placeholder instead of an empty tile, and `cb()` tolerates a null URL. Snapshot
states (FL video+snapshot, GA snapshot-only) were regression-checked and unchanged.

Known gap: `canPlayVideo()` requires `Hls.isSupported()`. hls.js 1.5.17 supports
iOS 17.1+ via ManagedMediaSource, but on **older iOS Safari** every Texas camera
falls through to "Live video unsupported here", because there is no snapshot to
show. Fixing that means adding a native-HLS path (`video.canPlayType('application/
vnd.apple.mpegurl')`, set `video.src` directly) — which would also change how the
other 10 video states behave on iOS, so it was left as a deliberate decision rather
than a silent change.
