# Ora

**Live at [warner-wvez.github.io/Ora](https://warner-wvez.github.io/Ora/)**

A live map of public traffic cameras across the US, styled like Apple Maps. **~33,200 cameras across 26 states** — and where the state DOT exposes it, the popup plays **actual live video**, not just a refreshing snapshot.

A layer panel lets you toggle states on and off independently and **stack them**. Turn on any combination — states, NYC, and the Chicago ticket-enforcement layer — on one map.

## Coverage

**~33,200 cameras across 26 states**, from state DOT "511" systems that run on a handful of shared vendor platforms:

- **Older DataTables platform (13 states)**: Florida, Georgia, Utah, Pennsylvania, North Carolina, Nevada, Arizona, Wisconsin, Idaho, New England (ME/NH/VT), Connecticut, Louisiana, Alaska. Built by `build-states.py`.
- **Newer GraphQL platform (7 states)**: Minnesota, Colorado, Iowa, Nebraska, Indiana, Kansas, Massachusetts. Built by `build-states-graphql.py` (one `listCameraViewsQuery` per state returns every camera with a bbox, snapshot URL, and HLS sources).
- **MapLarge platform (Texas)**: 3,430 cameras from TxDOT's drivetexas.org. Built by `build-states-tx.py`. Texas is the one **video-only** state — it publishes no snapshot at all, so its popups play the HLS stream over a dark backdrop instead of a poster image.
- **WSDOT REST API (Washington)**: 1,516 cameras. Built by `build-states-wa.py` against WSDOT's Traveler Information API (free key, `WSDOT_API_KEY`). Snapshot-only, and the one state that also carries **which way each camera looks** and **how often its image really changes**. See below.

**Eleven of these states play CORS-open HLS live video right in the browser**: FL, PA, NC, NV, WI, LA, MN, CO, IA, KS, TX. The rest are snapshot-only (their stream host either lacks CORS or requires auth — Georgia, for example, returns 401). Each build script CORS-checks a sample stream and sets the flag.

- **Illinois** — 1,328 cameras (IDOT / Travel Midwest), snapshot only.
- **New York City** — 957 cameras (NYC DOT), snapshot refreshing every 2 seconds.

Both `build-states*.py` scripts write `states/<code>.json` and merge into `states/index.json`, which the app reads at load to populate the state list and coverage markers.

## Direction and refresh rate (Washington)

Most DOTs publish a camera's name and a URL. WSDOT publishes more, so Washington's popups say more.

**Which way the camera looks.** `CameraLocation.Direction` is a single letter (`N`, `S`, `E`, `W`, `B`, `O`). WSDOT's own road-alert feed spells the identical vocabulary out in full — "Northbound", "Both Directions" — so the expansion is theirs, not a guess. The popup shows it as a chip with an arrow. It is the direction of travel the camera covers, not a compass bearing.

**How often the image actually changes.** WSDOT publishes this *nowhere*: not in the REST API, not in the map's `appconfig.json`, not on the cameras page. But every JPEG carries a `Last-Modified` header. `measure-refresh-wa.py` polls `HEAD` on a cadence, watches that timestamp move, and writes `states/WA-refresh.json`, which the build folds in. Ages are computed against the server's own `Date` header, so a skewed clock (a couple of these images live on a ski lodge and a Park Service host) cannot corrupt anything but itself.

Two estimators, because either alone fails predictably. `window / changes` is right for cameras slower than the polling cadence and overestimates faster ones, since refreshes slip between passes. `max(observed age)` cannot be fooled by that aliasing, because an image's age at a random moment is roughly uniform on `[0, T]`. Both err upward, so the build takes the smaller. A camera has to be caught refreshing **twice** to get a number: one refresh only tells you the interval is somewhere between "the oldest age we saw" and "forever".

As measured on 2026-07-09: median **2 minutes**, 232 cameras at about a minute, the slowest rated one at 7 minutes. 143 cameras refresh slower than the 14-minute run could pin down and simply fall back to the generic wording. The popup polls at the measured rate instead of a flat 30s, which stops it re-fetching an identical JPEG twenty times.

**Cameras that are not actually live.** 11 Washington cameras return `IsActive: true` from the API while serving an image that has not changed in over a day. Four ferry cameras have served the same bytes since **September 2003**. Those get an amber "no new image since ..." instead of a refresh rate, and stop being polled every 30 seconds.

Washington also aims several cameras at one spot: 188 cameras sit on 47 shared coordinates, and stacked map pins are unclickable, so the build collapses each coordinate into one feature with a tabbed row of views. Both fields above therefore hang off each view, not off the location, and the chip updates as you switch tabs.

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
