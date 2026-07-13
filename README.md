# Ora

**Live at [warner-wvez.github.io/Ora](https://warner-wvez.github.io/Ora/)**

A live map of public traffic cameras across the US, styled like Apple Maps. **~46,100 cameras across 49 states — every state but New Jersey** (whose feed is provably locked; see SKIPPED) — and where the state DOT exposes it, the popup plays **actual live video**, not just a refreshing snapshot.

A layer panel lets you toggle states on and off independently and **stack them**. Turn on any combination — states, NYC, and the Chicago ticket-enforcement layer — on one map.

## Coverage

**~46,100 cameras across 49 states** (48 in `states/index.json`, plus Illinois as the original standalone layer), from state DOT "511" systems that run on a handful of shared vendor platforms:

- **Older DataTables platform (16 states)**: Florida, Georgia, Utah, Pennsylvania, North Carolina, Nevada, Arizona, Wisconsin, Idaho, Maine, New Hampshire, Vermont, Connecticut, Louisiana, Alaska, New York. Built by `build-states.py` (`python3 build-states.py NY` rebuilds one state; it merges into the index rather than overwriting it). Maine, New Hampshire and Vermont all come from newengland511.org, one feed whose rows each carry their own `state` label — they used to ship as one "New England" bundle and are now three states filtered by that label. Maine additionally gets the Maine Turnpike Authority's 17 camera sites appended by `build-states-me-turnpike.py`, scraped from the turnpike map's hardcoded JS (live snapshots, no video).
- **Newer GraphQL platform (7 states)**: Minnesota, Colorado, Iowa, Nebraska, Indiana, Kansas, Massachusetts. Built by `build-states-graphql.py` (one `listCameraViewsQuery` per state returns every camera with a bbox, snapshot URL, and HLS sources).
- **MapLarge platform (Texas)**: 3,430 cameras from TxDOT's drivetexas.org. Built by `build-states-tx.py`. Texas was the first **video-only** state — it publishes no snapshot at all, so its popups play the HLS stream over a dark backdrop instead of a poster image. Delaware, West Virginia, Missouri and Maryland turned out the same way, so five states now share that path.
- **WSDOT REST API (Washington)**: 1,516 cameras. Built by `build-states-wa.py` against WSDOT's Traveler Information API (free key, `WSDOT_API_KEY`). Snapshot-only, and the one state that also carries **which way each camera looks** and **how often its image really changes**. See below.

**Twenty of these states play CORS-open HLS live video right in the browser**: FL, PA, NC, NV, WI, LA, MN, CO, IA, TX, NY, DE, TN, OK, WV, MO, SC, MS, HI, MD. The rest are snapshot-only (their stream host either lacks CORS or requires auth — Georgia, for example, returns 401). Each build script CORS-checks sampled streams and sets the flag.

The 2026-07-12 session closed the map's remaining gaps — every state that had previously failed or been skipped, each dead for its own reason:

- **South Carolina** — 763 cameras, all live video (Iteris ATIS like South Dakota, but SC's skyvdn.com Wowza streams are token-free and CORS-open). `build-states-sc.py`.
- **Mississippi** — 411 camera sites / 956 views, live video. The map's markers come from an ASP.NET page-method (`default.aspx/LoadCameraData`), each site's views from its map-bubble page, snapshots from Wowza's own `/thumbnail` endpoint. The trap: streaming hosts are regional (`streamingjxn*` for Jackson, `streaminglym*`, `streamingshvn*`, `streaminggpt*` elsewhere), and a host pattern that only knew Jackson silently dropped 254 of 411 sites while looking exactly like a rate limit. `build-states-ms.py`.
- **Maryland** — 553 cameras, live video. CHART's export service (`getCameraMapDataJSON.do`) is simply open; the strmrN.sha.maryland.gov Wowza hosts are token-free and CORS-open. Video-only like Texas: no still endpoint exists anywhere. `build-states-md.py`.
- **Hawaii** — 361 cameras, live video. The long-standing blocker was coordinates: the camera-tour API has none and bare `/cameras` answers 403. The site's own config names `/cameras?format=mapPage`, which answers when the request carries the constant `x-icx-copyright` vendor header — with lat/lon on every camera. `build-states-hi.py`.
- **Alabama** — 629 cameras, snapshot-only, and a new failure mode: **DRM behind a green CORS check**. ALGO Traffic's API is open and its Wowza playlists answer `Access-Control-Allow-Origin: *`, but every chunklist carries `#EXT-X-KEY:METHOD=SAMPLE-AES` (FairPlay via ezdrm) — undecryptable by hls.js or any static page. The CORS probe alone would have shipped a LIVE badge over 629 dead players, so `video_plays()` in the newer builders reads the chunklist and refuses any stream that names a key. Snapshots refresh ~10 min. `build-states-al.py`.
- **Kentucky** — 241 cameras, snapshot-only. Both of KY's surfaces (maps.kytc.ky.gov and GoKY) read the same open ArcGIS FeatureServer; images live on trimarc.org and refresh within the minute. Nine Indiana-side rows whose images are dead from every door are dropped — Ora's Indiana layer carries those cameras live. `build-states-ky.py`.
- **Rhode Island** — 135 cameras, snapshot-only. RIDOT publishes no API and no coordinates: six PHP pages inline the cameras, the Wowza video is Referer-locked to dot.ri.gov (a header a static page cannot send — CORS is open, which again is exactly why a CORS probe alone proves nothing), but the page "thumbnails" turn out to be the live snapshots. Coordinates were derived offline: RI renumbered its exits to mileposts in 2021, so OSM junction refs anchor each filename's milemarker along the route; named intersections come from OSM way-pair closest approach; every pin was validated inside the RI boundary polygon and reverse-geocoded. `build-states-ri.py` carries the full gazetteer with per-entry provenance.

New York deserves its own line: **1,907 cameras, 1,553 with live video**, the largest live-video state after Florida and Texas. When it was built, 511ny also served 324 Connecticut and 66 New Jersey cameras on shared roads, which a bounding box cannot separate, since Connecticut sits inside any New York bbox and Ora already carries Connecticut from ctroads.org. The feed labeled every row with its own `state`, so the build believes that instead and uses the bbox only to catch three null-island rows and one camera whose longitude lost its minus sign. (As of 2026-07-12 the feed labels rows only "New York" or blank — the neighbor-state rows are gone, which also closed the one honest-partial door into New Jersey; see SKIPPED.) Roughly a fifth of the 354 video-less cameras currently serve NYSDOT's "No live camera feed at this time" placeholder: a real outage, not a parsing failure, and it explains itself to the reader.

Deciding that flag is subtler than it looks. It has been wrong twice, and two more traps were caught at the door: Alabama's FairPlay DRM behind a green CORS header, and Rhode Island/New Jersey's Referer-locked CDNs (CORS wide open, yet no static page can play them, because a browser will not spoof the Referer header).

**One camera cannot speak for a state.** `video_plays_any()` samples eight streams and accepts the state if any plays. It used to test exactly the first camera, which is a coin flip: about 5% of DOT cameras are down at any moment (measured, 19 of 20 New York streams alive). New York's first camera, `R5_007`, happens to be one of the dead ones, so the old check marked the whole state snapshot-only and silently discarded 1,553 working live feeds. Nothing errored.

**A CORS check alone is not enough.** Kansas and Massachusetts hand out stream URLs carrying a signed JWT with a **300 second** lifetime, which passes the check at build time and is dead five minutes after the file is written. Kansas shipped a red LIVE badge over 184 permanently-401 cameras until 2026-07-09. `video_plays()` now refuses any URL with a `token=` parameter, because a short-lived credential cannot live in a static JSON file. Both states are honest snapshot states instead, and their snapshots are fine.

- **Illinois** — 1,328 cameras (IDOT / Travel Midwest), snapshot only.
- **New York City** — 957 cameras (NYC DOT), snapshot refreshing every 2 seconds.

Both `build-states*.py` scripts write `states/<code>.json` and merge into `states/index.json`, which the app reads at load to populate the state list and coverage markers.

## SKIPPED

The record of states with no static-compatible public feed, so nobody re-litigates them. Every door tried is listed; if a door here reopens, that is the place to start.

**New Jersey** (verdict 2026-07-12): the only unreachable state. Its entire camera inventory — 666 entries with coordinates, readable from 511nj.org's API — is Video/HLS with **zero image mode**, and both stream families are locked in ways a static page cannot satisfy:

1. `nj-511.wink.co` (379 cameras): playlists 403 without an `?otp=` one-time token from `getHlsToken`, valid **300 seconds**. An expiring credential cannot live in a static JSON file (the Kansas rule).
2. `njtpk-wink.xcmdata.org` (102 Turnpike cameras): playlists require `Referer: 511nj.org` — a forbidden header a browser page cannot set — and even then answer `Access-Control-Allow-Origin: https://511nj.org` only, so another origin cannot read the bytes either. Two independent locks.
3. The remaining 185 entries point at a literal `Camera-Unavailable.png`.
4. No snapshot/thumbnail endpoint exists on either CDN (`poster/preview/thumbnail/snapshot.jpg` all 403), unlike Mississippi's Wowza.
5. The API itself sits behind a Keycloak anonymous-login flow (encrypted request bodies, ~6-minute JWTs) — scriptable, but pointless while the streams stay locked.
6. 511NY's feed used to carry 66 labeled New Jersey cameras on shared roads; as of 2026-07-12 its rows are labeled only "New York" or blank, so that honest-partial door is gone too.
7. NJDOT's site (nj.gov/transportation) and the Turnpike Authority's (njta.gov) are JS shells over the same locked backends.

## Direction and refresh rate

Most DOTs publish a camera's name and a URL. WSDOT and NYSDOT publish more, so their popups say more.

New York's feed carries a `direction` column ("Northbound", "Both Directions", and 623 rows of "Unknown"), so 1,291 of its cameras get the same compass chip Washington introduced — as do the other DataTables states (including Maine/New Hampshire/Vermont), Alabama, South Carolina, and Rhode Island, whose feeds or filenames carry the same vocabulary. Everything else below is Washington-only, because refresh rate had to be measured and only WSDOT's images expose the timestamps to measure it with.

**Which way the camera looks.** `CameraLocation.Direction` is a single letter (`N`, `S`, `E`, `W`, `B`, `O`). WSDOT's own road-alert feed spells the identical vocabulary out in full — "Northbound", "Both Directions" — so the expansion is theirs, not a guess. The popup shows it as a chip with an arrow. It is the direction of travel the camera covers, not a compass bearing.

**How often the image actually changes.** WSDOT publishes this *nowhere*: not in the REST API, not in the map's `appconfig.json`, not on the cameras page. But every JPEG carries a `Last-Modified` header. `measure-refresh-wa.py` polls `HEAD` on a cadence, watches that timestamp move, and writes `states/WA-refresh.json`, which the build folds in. Ages are computed against the server's own `Date` header, so a skewed clock (a couple of these images live on a ski lodge and a Park Service host) cannot corrupt anything but itself.

Two estimators, because either alone fails predictably. `window / changes` is right for cameras slower than the polling cadence and overestimates faster ones, since refreshes slip between passes. `max(observed age)` cannot be fooled by that aliasing, because an image's age at a random moment is roughly uniform on `[0, T]`. Both err upward, so the build takes the smaller. A camera has to be caught refreshing **twice** to get a number: one refresh only tells you the interval is somewhere between "the oldest age we saw" and "forever".

As measured on 2026-07-09: median **2 minutes**, 232 cameras at about a minute, the slowest rated one at 7 minutes. 143 cameras refresh slower than the 14-minute run could pin down and simply fall back to the generic wording. The popup polls at the measured rate instead of a flat 30s, which stops it re-fetching an identical JPEG twenty times.

**Cameras that are not actually live.** 11 Washington cameras return `IsActive: true` from the API while serving an image that has not changed in over a day. Four ferry cameras have served the same bytes since **September 2003**. Those get an amber "no new image since ..." instead of a refresh rate, and stop being polled every 30 seconds.

Washington also aims several cameras at one spot: 188 cameras sit on 47 shared coordinates, and stacked map pins are unclickable, so the build collapses each coordinate into one feature with a tabbed row of views. Both fields above therefore hang off each view, not off the location, and the chip updates as you switch tabs.

## Is this camera actually showing me anything?

Roughly one in ten of Ora's snapshot cameras is not showing a live view, and every map of these feeds, including this one until now, presented those identically to the ones that work. A camera can fail three ways, and the source is no help. Hawaii's API reports `status: "OK"` on all 52 cameras serving its "Image Temporarily Unavailable" card. WSDOT reports `IsActive: true` on ferry cameras frozen since 2003. Kansas served a red LIVE badge over 184 streams that answer 401.

Two failures, two different solutions, because of one browser rule.

**A snapshot that is not a camera.** `probe-health.py` sweeps every camera and classifies it `offline` (the image will not load), `placeholder` (a "camera unavailable" card), or `frozen` (a real image, unchanged for over a day).

Detecting a placeholder needs no per-state list of what placeholders look like. Two cameras cannot see the same scene byte for byte, so **any image served by three or more cameras at once is not a camera view**. The rule calibrates itself, and it found Hawaii's card without being told Hawaii exists. Clusters are confirmed by pulling two full bodies and checking they really are identical, and confirmed fingerprints are remembered in `known-placeholders.json`, which is what catches the same card later when only one camera is down.

It is cheap, too. `Range: bytes=0-1023` returns the first 1KB *and* the true total size in `Content-Range`, so a camera fingerprints as `(total_size, sha256(first 1KB))` for about 1.2KB of traffic. Every DOT host honours it. That matters: pulling ~41,000 whole JPEGs four times a day would be 1.6GB per run off the servers of 44 state governments. This is ~49MB. Do not "optimise" it into a `HEAD` request, because Georgia and North Carolina answer `HEAD` with `Content-Length: 0`.

A [GitHub Actions workflow](.github/workflows/camera-health.yml) re-runs the sweep every 6 hours and commits the verdicts, because feeds recover: a camera dead this week is fine next week, and a one-off sweep would rot into a different kind of lie than the one it fixed. Dead cameras get a grey pin, so you learn before you spend the click, and the popup says which way it failed and when that was last checked.

**A video stream that is not moving.** This one the browser can settle by itself, at runtime, with no data files. hls.js feeds video through MSE from a `blob:` URL, which is same-origin, so unlike a cross-origin `<img>` the canvas is **not** tainted and the pixels are readable. Ora samples the picture every 3.5s and asks two questions: is `currentTime` advancing, and is the picture actually changing? A real sensor is never perfectly still, so two consecutive identical frames mean a synthetic one. Either failure and the red LIVE badge turns grey and reads NOT LIVE, keeping the poster snapshot, since a recent still beats a lie.

That covers the case where you click a camera expecting live video and get a still: a dead stream behind a poster used to look exactly like a live camera on an empty road.

Snapshots cannot get the same treatment. A cross-origin `<img>` throws `SecurityError` on `getImageData`, and DOT image hosts send no CORS header, so only its dimensions survive. That is the whole reason the snapshot half has to be precomputed by a script and shipped.

## Routes

Group the cameras on your commute into a saved **route** and scroll through all their live feeds at once, instead of clicking pins one at a time. Make a route, tap cameras on the map to add them, then open the route to see the whole drive as a vertical stack of live video/snapshots. Routes are saved locally (no account, no sign-in). Inspired by the [511 Wisconsin app](https://apps.apple.com/us/app/511-wisconsin-traffic-cameras/id6446508226) whose users called this feature "gold."

## Chicago tickets (enforcement analysis)

- **Chicago tickets** — 396 automated enforcement cameras (183 red light intersections + 213 speed cameras), plotted as graduated circles sized by violations in the last 90 days. This is a static, data-driven layer, not live video. Two color modes:
  - **Safety verdict** (default) — each camera is cross-referenced against nearby injury crashes to answer "is this camera on real danger, or just ticketing?" See below.
  - **Camera type** — red for red light, orange for speed.

  Click a pin for its verdict and the exact statistics behind it: recent + all-time ticket volume, injury crashes within 150 m since 2023, people hurt/killed, and how many of those crashes were caused by the specific behavior the camera targets. Speed cameras also show approach directions and go-live date. In the sidebar, the Chicago ticket map is nested under Illinois.

### The safety-vs-revenue verdict

For every enforcement camera, injury crashes within 150 m (2023–present) are counted and compared against the camera's ticket volume. Each camera is median-split into a quadrant:

- **On real danger** (green) — above-median tickets AND above-median injury crashes. The camera sits where the risk actually is.
- **Ticket-heavy, low crash** (red) — among the busiest ticketing cameras, but few injury crashes nearby. Volume outruns the safety need. (Example: 3358 S Ashland, 32,533 tickets in 90 days but only 4 injury crashes nearby.)
- **Crashes, light enforcement** (orange) — high injury-crash count but below-median ticketing. (Example: Jeffery & 95th, 57 injury crashes but 831 tickets.)
- **Quiet on both** (gray) — below-median on both.

This is the one insight the whole stack uniquely enables: enforcement cameras and crashes sit on the same intersections, so they can be joined directly. Note it is a **cross-sectional** correlation (does the danger match the ticketing right now), not a causal before/after claim.

## Navigation & interaction

- **Search** — an instant, client-side search over every loaded camera name, intersection, and address (no API/key). Type a place, pick a suggestion, and the map flies there and selects it. Searches only the layers you have turned on.
- **Base map toggle** — switch between the clean light style and satellite imagery (Esri World Imagery). Satellite is especially useful here: you can see the actual road and intersection each camera watches. Pin outlines thicken on satellite so they stay visible.
- **Hover + selection feedback** — hovering a pin shows a ring and a name tooltip (a preview of what you'll get). The selected pin stays ringed even as you pan/zoom away, and a "Back to selection" button flies you back to it.
- **In-layer filters** (Chicago tickets) — filter the enforcement layer by verdict (e.g. show only the 115 "ticket-heavy, low crash" cameras) and by camera type (red light / speed), so the layer works as an investigative tool, not just a picture.
- **Shareable links** — the URL always reflects exactly what you're looking at (active layers, map position, color mode, base map, filters, and the selected camera). "Copy link" grabs it; opening someone's link restores that precise view, popup and all.
- **Coverage overview** — the app opens zoomed out on a map of the whole US with a labeled, clickable marker for every covered state. Click a marker (or a checkbox) to load that state and fly in; "Show all states" returns to the overview and "Clear" turns everything off. So a first-time visitor immediately sees which states have footage and can pick one.
- **Instant feed loading** — video cameras show their snapshot as a poster the moment you click, then the live video fades in over it, so there's never a blank loading box. (Texas publishes no snapshot, so its video fades in over a dark backdrop; a stream that never starts falls back to the offline state after 12s.) Ora also preconnects to each state's media hosts when you load the state, warming the connection before your first click. (Preloading every stream up front would overload both the browser and the DOT servers — poster + preconnect gets the perceived speed without the cost.)

These follow the map-UI principles in [Eleken's](https://www.eleken.co/blog-posts/map-ui-design) and [Dura Digital's](https://www.duradigital.com/post/the-pathway-to-great-user-interface-design-for-maps) map UI design guides: working search, a neutral base map, distinct/clickable markers, style options for different backgrounds, clear hover/selection states, and a reset-view ("Show all states") helper so users never get lost.

## Data sources

### Live cameras

- **Illinois**: [IDOT's public Illinois Gateway Traffic Cameras dataset](https://gis-idot.opendata.arcgis.com/datasets/illinois-gateway-traffic-cameras) (open ArcGIS data, no API key required). Snapshots are served from `cctv.travelmidwest.com`, the public feed IDOT and its partner agencies already use for traveler information. Source images there only update every ~1–10 minutes depending on the agency, so the map can't be more "live" than that.
- **NYC**: [NYC DOT's public camera GraphQL API](https://webcams.nyctmc.org/) (`webcams.nyctmc.org/cameras/graphql`, no API key required — also backs 511ny.org). Snapshots come from `webcams.nyctmc.org/api/cameras/{id}/image`, which the site itself polls every 2 seconds.

Neither live city is true video (no RTSP/HLS/codec) — both are just repeatedly-polled JPEG stills. The difference in how "live" each feels comes entirely from how often each backend is willing to serve a fresh frame, not from the protocol.

### Chicago enforcement (Chicago Data Portal, all open, no API key)

- [Red Light Camera Violations](https://data.cityofchicago.org/d/spqx-js37) — daily violation counts per camera since 2014; aggregated here to the intersection level.
- [Speed Camera Locations](https://data.cityofchicago.org/d/4i42-qv3h) — addresses, approach directions, and go-live dates.
- [Speed Camera Violations](https://data.cityofchicago.org/d/hhkd-xvj4) — daily violation counts per speed camera since 2014; joined to the locations by camera ID.
- [Traffic Crashes - Crashes](https://data.cityofchicago.org/d/85ca-t3if) — 1M+ geolocated crash records, each tagged with injuries, fatalities, and primary cause. Injury crashes since 2023 are spatially joined to each camera (150 m radius) to produce the safety verdict.

These are ticketing/enforcement cameras, not traffic-viewing cameras — they have no public live image, only violation history.

`build-chicago-enforcement.py` regenerates `cameras-chicago-enforcement.json` end to end from these four datasets (fetch, aggregate, spatial-join, classify). Run `python3 build-chicago-enforcement.py` to refresh it.

## Stack

- [MapLibre GL JS](https://maplibre.org/) for the map rendering
- [OpenFreeMap](https://openfreemap.org/) for free, no-key vector tiles (light "Positron"-style basemap)
- No build step — static HTML, loads everything from CDN

## Running locally

```
python3 -m http.server 8934
```

Then open `http://localhost:8934/`.

## Notes

- `cameras.json` (Illinois) is a preprocessed version of the raw IDOT dataset: rows are collapsed from one-per-direction to one pin per physical camera location, with all directions/snapshot URLs nested under each pin.
- `cameras-nyc.json` (NYC) is a preprocessed version of NYC DOT's GraphQL camera list.
- `cameras-chicago-enforcement.json` is a precomputed snapshot: red light violations aggregated to the intersection level and speed violations joined to their locations, each with a 90-day and all-time violation total. Because it's a snapshot of a slow-changing dataset (violations are published with a ~2-week lag), it's committed as static data rather than fetched live. The 90-day windows are measured from each dataset's most recent date at build time.
- The page sets `<meta name="referrer" content="no-referrer">` because `travelmidwest.com` blocks image requests that carry a referrer header (hotlink protection) — without it, every Illinois snapshot would fail to load. NYC's endpoint doesn't have this restriction.
