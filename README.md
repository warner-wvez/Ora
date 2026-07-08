# Ora

A live map of Illinois traffic cameras, styled like Apple Maps.

Plots all 1,328 public traffic camera locations from the Illinois Gateway network (IDOT, Lake County, DuPage County, Kane County, and the Illinois Tollway) on a clean, clustered map. Click any camera to see its current live snapshot.

## Data source

Camera locations come from [IDOT's public Illinois Gateway Traffic Cameras dataset](https://gis-idot.opendata.arcgis.com/datasets/illinois-gateway-traffic-cameras) (open ArcGIS data, no API key required). Live snapshots are served directly from `cctv.travelmidwest.com`, the public feed IDOT and its partner agencies already use for traveler information.

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

- `cameras.json` is a preprocessed version of the raw IDOT dataset: rows are collapsed from one-per-direction to one pin per physical camera location, with all directions/snapshot URLs nested under each pin.
- The page sets `<meta name="referrer" content="no-referrer">` because `travelmidwest.com` blocks image requests that carry a referrer header (hotlink protection) — without it, every snapshot would fail to load.
