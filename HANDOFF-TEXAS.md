# Ora — Texas handoff (resume here)

Goal of the next session: **add Texas traffic cameras to Ora.** Texas has real,
CORS-open live video, but its site blocks bulk data extraction. The one missing
piece is **camera coordinates**. Warner is doing manual hunting for a coordinate
source; once we have it, wiring Texas is ~30 min.

---

## Project snapshot (so a cold session has context)

- **Repo:** https://github.com/warner-wvez/Ora (public). Local: `~/Desktop/il-traffic-cams`
- **Run locally:** `cd ~/Desktop/il-traffic-cams && python3 -m http.server 8934` → http://localhost:8934/
- **Coverage today:** 24 states, ~28,300 cameras. Live HLS video in 10: FL, PA, NC, NV, WI, LA, MN, CO, IA, KS.
- **How states load:** `states/index.json` is read at page load and drives the sidebar list + coverage markers. Each state is `states/<CODE>.json`. To add a state you only need to write `states/TX.json` and add a `TX` entry to `index.json`; the UI picks it up automatically.

### Data formats
`states/<CODE>.json` (one FeatureCollection):
```json
{"type":"FeatureCollection","features":[
  {"type":"Feature","geometry":{"type":"Point","coordinates":[LNG,LAT]},
   "properties":{"name":"...", "kind":"live",
     "directions":[{"snapshot":"https://...jpg","video":"https://...m3u8 or null","label":""}],
     "roadway":"", "county":""}}
]}
```
`states/index.json` entry:
```json
"TX":{"name":"Texas","file":"states/TX.json","count":N,"center":[-99.3,31.3],"zoom":5.4,"video":true}
```
- `video:true` in index → the LIVE tag + the app tries HLS (via `canPlayVideo` in index.html, which gates on `dir.video && cfg.hasVideo`). Only set true if the stream host is CORS-open (Texas is — see below).
- Build scripts already exist per platform: `build-states.py` (13 DataTables states), `build-states-graphql.py` (7), `build-states-ca.py`, `build-states-or.py`, `build-states-va.py`, `build-states-oh.py` (reads `OHGO_API_KEY` env). Texas will get `build-states-tx.py`.

---

## Texas: everything already discovered (from drivetexas.org HAR)

### Live video — CONFIRMED WORKING, CORS-open
- HLS from SkyVDN. Example: `https://s76.us-east-1.skyvdn.com/rtplive/TX_WAC_091/playlist.m3u8`
- CORS-checked: `Access-Control-Allow-Origin: *` → **plays in the browser**. So Texas would be `video:true`.
- The server number (`s75`/`s76`) is **baked into the `httpsurl` field per camera — do not guess it.**

### Camera data — MapLarge (the blocker lives here)
- Resolve the table id (changes over time, resolve fresh):
  `GET https://dtx-e-cdn.maplarge.com/Remote/GetActiveTableID?shortTableId=appgeo%2FcameraPoint`
  → `{ ..., "table":"appgeo/cameraPoint/<ID>" }`
- Query (small areas only):
  `GET https://dtx-e-cdn.maplarge.com/Api/ProcessDirect?request=<urlencoded JSON>`
  with JSON:
  ```json
  {"action":"table/query","query":{
    "sqlselect":["route","jurisdiction","description","name","clspsurl","httpsurl","imageurl"],
    "start":0,"table":"<TID>","take":1000,
    "where":[{"col":"XY","test":"DWithin:333","value":"WKT(POLYGON(LNG LAT, LNG LAT, ...))"}]}}
  ```
  (single-paren WKT: `POLYGON(x y, x y, ...)`, NOT double). Send `Referer: https://drivetexas.org/`.
- Returns per camera: `name` (TX_WAC_091), `description` ("IH35 @ East Loop 121"), `route`, `jurisdiction`, `httpsurl` (the HLS playlist), `clspsurl`. `imageurl` is a useless `https://localhost/thumbs/...` placeholder — **there is no real snapshot**, so Texas is video-only.

### The three blockers (all verified)
1. **Statewide/large-area queries return HTTP 500.** Only small (map-click-sized, few-km) polygons work.
2. **No coordinates in the response.** `allGeo` comes back empty; positions live only in the rendered map tiles (`{0-5}dtx-e-cdn.maplarge.com/Api/ProcessRequest?...action:tile/gettile` → `{"index":[record indices per pixel]}`).
3. **No open fallback.** TxDOT ArcGIS org `services.arcgis.com/KTcxiTD9dsQw4r7Z` (684 services) has NO live-camera-location layer (only a fiber/planning "CCTV_Priorites" set).

---

## THE UNBLOCK: what we need = coordinates keyed by camera name/ID

If we get a list of `{ camera name or id (TX_WAC_xxx), lat, lng }`, we're done — join it
to the stream URLs (query MapLarge by name, or the name→httpsurl is derivable) and build `states/TX.json` with `video:true`.

### Manual sources for Warner to try (best first)
1. **A "camera list" / paginated view on drivetexas.org** — if the site has a list page that
   enumerates all cameras, HAR it; it may carry coords. (The map view does not.)
2. **City open-data portals (cover the metros, have coords + often camera IDs):**
   - Austin: https://data.austintexas.gov/Transportation-and-Mobility/Traffic-Cameras/b4k4-adkb
   - Houston, Dallas, San Antonio, Fort Worth open data portals (search "<city> traffic cameras open data").
3. **TxDOT district ITS feeds** — some districts publish a DATEX/XML or JSON with camera lat/lng.
   The `name` prefix = district: WAC=Waco, AUS=Austin, HOU=Houston, DAL=Dallas, SAT=San Antonio,
   FTW=Fort Worth, ELP=El Paso, etc.
4. **A community GeoJSON** — search "TX_WAC camera geojson", "drivetexas cameras coordinates".
5. **Geocode from descriptions** — every camera has a cross-street ("IH35 @ East Loop 121");
   these are geocodable (batch geocoder) if all else fails. Lower precision.

### If no coord list is findable (fallback, not recommended)
- Grid-crawl MapLarge: fire many small `DWithin` queries across a Texas grid, use the cell center
  as an approximate coordinate. Imprecise (multiple cams per cell collapse) and hammers their API.
- Tile-decode: fetch `gettile` across Texas, decode `index` arrays → record indices, but you still
  need MapLarge's internal index→lat/lng mapping. Hard. Skip unless desperate.

---

## When resuming with coordinates in hand
1. Write `build-states-tx.py`: for each camera → feature with `coordinates` from the coord source,
   `directions:[{"snapshot":null,"video":"<httpsurl>","label":""}]`. Match coords↔stream by camera name.
2. Set `index.json` `TX` entry `video:true` (CORS confirmed).
3. **Code note — video-only cameras:** Texas has no snapshots, so `mediaHTML`/`playDir` in `index.html`
   currently expect `cfg.snap(dir)` for the poster. Add a graceful path for `dir.snapshot==null`
   (skip the poster `<img>`, show the video on a plain dark background; keep the "offline" fallback).
   This is a small edit and the ONLY code change Texas needs.
4. Verify: enable Texas, click a camera, confirm HLS plays.

## Environment notes
- Disk was ~95% full (≈900MB free); the Playwright test browser was removed to free space.
  Reinstall (`npx playwright install chromium`, ~100MB) if a browser visual test is needed.
- macOS. `curl` in the sandbox sometimes drops PATH mid-loop — prefer Python `urllib` for probes.
