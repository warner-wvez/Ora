# Ora

A live map of public traffic cameras, styled like Apple Maps.

A layer panel lets you toggle data sets on and off independently and **stack them** — e.g. see the live Illinois traffic cameras and the Chicago ticket-enforcement data on the same map at once. Layers are grouped by region (collapsible), and each remembers its own state:

**Illinois**
- **Traffic cameras** (live) — 1,328 camera locations statewide (IDOT, Lake County, DuPage County, Kane County, and the Illinois Tollway). Click a pin for its current live snapshot.
- **Chicago tickets** (enforcement) — 396 automated enforcement cameras (183 red light intersections + 213 speed cameras), plotted as graduated circles sized by violations in the last 90 days. This is a static, data-driven layer, not live video. Two color modes:
  - **Safety verdict** (default) — each camera is cross-referenced against nearby injury crashes to answer "is this camera on real danger, or just ticketing?" See below.
  - **Camera type** — red for red light, orange for speed.

  Click a pin for its verdict and the exact statistics behind it: recent + all-time ticket volume, injury crashes within 150 m since 2023, people hurt/killed, and how many of those crashes were caused by the specific behavior the camera targets. Speed cameras also show approach directions and go-live date.

**New York City**
- **Traffic cameras** (live) — 957 camera locations citywide (NYC DOT), refreshing every 2 seconds — genuinely live-feeling, unlike Illinois's much slower source cadence.

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

These follow the map-UI principles in [Eleken's map UI design guide](https://www.eleken.co/blog-posts/map-ui-design): working search, style options for different backgrounds, clear hover/selection states with a return-to-selection helper, and filters to focus on just what matters.

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
