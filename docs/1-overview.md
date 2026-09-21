---
type: page
---
# Overview

Ora is a live map of every public traffic camera in the United States. Pick a state, click
a pin, and see what that camera sees right now: real live video where the state
transportation department allows it, a refreshing snapshot everywhere else, and an honest
grey pin when the camera is not actually showing a road. There is no account, no build
step, and no server: one HTML file, one JSON file per state, and a sweep every six hours
that checks whether each camera is still telling the truth.

<!-- numbers:start -->
| States | Cameras | States with live video | Cameras down at the last sweep | Last sweep |
|---|---|---|---|---|
| 49 of 50 | 46,107 | 20 | 6,188 | 2026-09-19 17:14 UTC |
<!-- numbers:end -->

The one missing state is New Jersey, whose feeds cannot be played from a static page.
[New Jersey](3.31-new-jersey.md) records every door tried so nobody re-litigates it.

## I want to...

| I want to... | Go to |
|---|---|
| Use the map: layers, search, routes, sharing a view | [The map](2-map.md) |
| Save the cameras on my commute and scroll through them | [Routes](2.1-routes.md) |
| See whether Chicago's ticket cameras sit on real danger | [Chicago tickets](2.2-chicago-tickets.md) |
| Know where a state's cameras come from and what they give | [Sources](3-sources.md) |
| Understand how dead cameras are found | [Camera health](4-camera-health.md) |
| Run it or rebuild a state on my machine | [Run locally](1.3-run-locally.md) |
| Read the shape of a state file | [Data format](1.2-data-format.md) |
| See why a decision was made | [Decisions](6-decisions.md) |
| Add a state | [Contributing](7-contributing.md) |

## Key features

- **[Live video in 20 states.](3-sources.md)** Where the stream host is open to the browser
  and carries no expiring token or DRM, the popup plays the real HLS stream. Everywhere else
  it shows the snapshot the agency publishes and says so.
- **[Every camera location is a pin.](6-decisions/0001-location-first.md)** A pin means a
  camera exists there, feed or no feed. Only a bad coordinate or a test feed drops a row.
- **[Cameras that lie are caught.](4-camera-health.md)** About one in ten snapshot cameras
  serves a placeholder card, a frozen frame, or nothing. A six-hour sweep fingerprints every
  image with a 1 KB range request and greys the dead pins; video is judged live in the
  browser by whether the picture actually moves.
- **[Routes.](2.1-routes.md)** Group the cameras on a drive and scroll through all of
  their feeds at once, saved in the browser, no sign-in.
- **[Chicago's enforcement cameras, joined to crashes.](2.2-chicago-tickets.md)** 396
  red-light and speed cameras against injury crashes within 150 m, so each one gets a
  verdict: on real danger, ticket-heavy with few crashes, under-enforced, or quiet.
- **[Shareable views.](2-map.md)** The URL carries the active layers, position, basemap,
  filters, and selected camera, so a link restores exactly what you were looking at.

## Tech stack

| Layer | What |
|---|---|
| Map | [MapLibre GL JS](https://maplibre.org/) 4.7 with [MapTiler](https://www.maptiler.com/) streets-v2 tiles, Esri World Imagery for satellite, supercluster for clustering |
| Video | [hls.js](https://github.com/video-dev/hls.js) 1.5 playing agencies' HLS streams straight from the browser |
| Data | One GeoJSON file per state in `states/`, an index, and a health verdict file per snapshot state |
| Builders | Python 3.12, standard library only, one script per feed under `builders/` |
| Checks | GitHub Actions: the camera health sweep every six hours, the docs check on every push |
| Hosting | GitHub Pages, served from the root of `main` |

## Repository map

```
Ora/
├── index.html          # The whole app: map, sidebar, popups, routes, health badges
├── states/             # One GeoJSON per state, index.json, health/ verdicts, WA-refresh.json
├── cameras.json        # Illinois layer (IDOT), the original layer
├── cameras-nyc.json    # New York City layer (NYC DOT)
├── cameras-chicago-enforcement.json   # Chicago ticket cameras with their safety verdicts
├── states-outline.json # State boundaries for the coverage overview
├── builders/           # One Python script per feed; each writes states/<CODE>.json
├── scripts/            # The health sweep, the refresh-rate measurement, the docs check, the numbers refresh
├── research/           # The vehicle-detection spike: scripts, report, evidence frames
├── docs/               # These pages, numbered
└── .github/workflows/  # camera-health.yml (every 6 h) and docs.yml (every push)
```
