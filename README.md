# Ora

A live map of public traffic cameras, styled like Apple Maps.

Plots public traffic camera locations on a clean, clustered map. Click any camera to see its current live snapshot. Includes a city switcher:

- **Illinois** — 1,328 camera locations statewide (IDOT, Lake County, DuPage County, Kane County, and the Illinois Tollway)
- **New York City** — 957 camera locations citywide (NYC DOT), refreshing every 2 seconds — genuinely live-feeling, unlike Illinois's much slower source cadence

## Data sources

- **Illinois**: [IDOT's public Illinois Gateway Traffic Cameras dataset](https://gis-idot.opendata.arcgis.com/datasets/illinois-gateway-traffic-cameras) (open ArcGIS data, no API key required). Snapshots are served from `cctv.travelmidwest.com`, the public feed IDOT and its partner agencies already use for traveler information. Source images there only update every ~1–10 minutes depending on the agency, so the map can't be more "live" than that.
- **NYC**: [NYC DOT's public camera GraphQL API](https://webcams.nyctmc.org/) (`webcams.nyctmc.org/cameras/graphql`, no API key required — also backs 511ny.org). Snapshots come from `webcams.nyctmc.org/api/cameras/{id}/image`, which the site itself polls every 2 seconds.

Neither city is true video (no RTSP/HLS/codec) — both are just repeatedly-polled JPEG stills. The difference in how "live" each feels comes entirely from how often each backend is willing to serve a fresh frame, not from the protocol.

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
- The page sets `<meta name="referrer" content="no-referrer">` because `travelmidwest.com` blocks image requests that carry a referrer header (hotlink protection) — without it, every Illinois snapshot would fail to load. NYC's endpoint doesn't have this restriction.
