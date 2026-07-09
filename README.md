# Ora

A live map of public traffic cameras, styled like Apple Maps.

A mode switcher offers three views:

- **Illinois** (live cameras) — 1,328 camera locations statewide (IDOT, Lake County, DuPage County, Kane County, and the Illinois Tollway). Click a pin for its current live snapshot.
- **New York City** (live cameras) — 957 camera locations citywide (NYC DOT), refreshing every 2 seconds — genuinely live-feeling, unlike Illinois's much slower source cadence.
- **Chicago Tickets** (enforcement) — 396 automated enforcement cameras (183 red light intersections + 213 speed cameras), plotted as graduated circles sized by violations in the last 90 days and colored by type. This is a static, data-driven layer, not live video: it answers "where does Chicago ticket you the most," not "what does traffic look like right now." Click a pin for its recent and all-time violation counts (plus, for speed cameras, which directions it watches and when it went live).

## Data sources

### Live cameras

- **Illinois**: [IDOT's public Illinois Gateway Traffic Cameras dataset](https://gis-idot.opendata.arcgis.com/datasets/illinois-gateway-traffic-cameras) (open ArcGIS data, no API key required). Snapshots are served from `cctv.travelmidwest.com`, the public feed IDOT and its partner agencies already use for traveler information. Source images there only update every ~1–10 minutes depending on the agency, so the map can't be more "live" than that.
- **NYC**: [NYC DOT's public camera GraphQL API](https://webcams.nyctmc.org/) (`webcams.nyctmc.org/cameras/graphql`, no API key required — also backs 511ny.org). Snapshots come from `webcams.nyctmc.org/api/cameras/{id}/image`, which the site itself polls every 2 seconds.

Neither live city is true video (no RTSP/HLS/codec) — both are just repeatedly-polled JPEG stills. The difference in how "live" each feels comes entirely from how often each backend is willing to serve a fresh frame, not from the protocol.

### Chicago enforcement (Chicago Data Portal, all open, no API key)

- [Red Light Camera Violations](https://data.cityofchicago.org/d/spqx-js37) — daily violation counts per camera since 2014; aggregated here to the intersection level.
- [Speed Camera Locations](https://data.cityofchicago.org/d/4i42-qv3h) — addresses, approach directions, and go-live dates.
- [Speed Camera Violations](https://data.cityofchicago.org/d/hhkd-xvj4) — daily violation counts per speed camera since 2014; joined to the locations by camera ID.

These are ticketing/enforcement cameras, not traffic-viewing cameras — they have no public live image, only violation history.

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
