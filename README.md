# Ora

A live map of every public traffic camera in the United States.

Pick a state, click a pin, and see what that camera sees right now. Where the state
transportation department allows it, the popup plays the real live stream; everywhere
else it shows the agency's refreshing snapshot and says so. A camera that is not actually
showing a road gets a grey pin, because a six-hour sweep checks every one. No account, no
server, no build step: one HTML file, one JSON file per state, and the agencies' own
feeds.

**Live at [warner-wvez.github.io/Ora](https://warner-wvez.github.io/Ora/)**. Read the
[docs](docs/1-overview.md).

## What it covers today

<!-- numbers:start -->
| States | Cameras | States with live video | Cameras down at the last sweep | Last sweep |
|---|---|---|---|---|
| 49 of 50 | 46,107 | 20 | 6,188 | 2026-09-19 17:14 UTC |
<!-- numbers:end -->

The missing state is New Jersey, whose feeds cannot be played from a static page.
[Every door tried is on record](docs/3.31-new-jersey.md).

## Quick start

1. Open the map. It starts on the whole country with a counted pin per covered state.
2. Click a state pin, or tick states in the sidebar. They stack.
3. Click a camera. Video fades in over the snapshot where it plays; the arrow keys cycle
   to the next camera in spatial order; click the picture to go full screen.
4. Make a route: name it, tap the cameras on your drive, and scroll through all of their
   feeds at once. Saved in your browser, no sign-in.
5. Copy the link. It restores exactly the view you had, camera and all.

The [map guide](docs/2-map.md) has the rest, including the
[Chicago ticket-camera layer](docs/2.2-chicago-tickets.md) that joins 396 enforcement
cameras to nearby injury crashes.

## How it stays honest

- **Every camera location is a pin**, feed or no feed. Only a bad coordinate or a test
  feed drops a row. [Why](docs/6-decisions/0001-location-first.md).
- **Video is flagged only when a stream really plays from a static page.** Expiring tokens,
  DRM behind a green CORS header, and Referer-locked hosts are all refused and documented.
  [Sources](docs/3-sources.md).
- **Cameras that lie are caught.** An image served by three or more cameras is a
  placeholder; a frame unchanged for a day is frozen. The sweep fingerprints every
  snapshot with a 1 KB range request and greys the dead pins. Video is judged in the
  browser by whether the picture moves. [Camera health](docs/4-camera-health.md).
- **No guessed numbers.** A refresh rate is stated only where it was measured; the counts
  above are rewritten from the data files by a script.

## Project structure

```
Ora/
├── index.html          # The whole app: map, sidebar, popups, routes, health badges
├── states/             # One GeoJSON per state, index.json, health/ verdicts, WA-refresh.json
├── cameras.json        # Illinois layer, the original
├── cameras-nyc.json    # New York City layer
├── cameras-chicago-enforcement.json   # Chicago ticket cameras with safety verdicts
├── states-outline.json # State boundaries for the coverage overview
├── builders/           # One Python script per feed; each writes states/<CODE>.json
├── scripts/            # Health sweep, refresh-rate measurement, docs check, numbers refresh
├── research/           # The vehicle-detection spike: scripts, report, evidence
├── docs/               # Numbered docs, one page per state feed, decision records
└── .github/workflows/  # camera-health.yml every 6 h, docs.yml on every push
```

## Tech stack

| Layer | What |
|---|---|
| Map | MapLibre GL JS with MapTiler streets-v2 tiles, Esri World Imagery for satellite, supercluster |
| Video | hls.js playing the agencies' HLS streams straight from the browser |
| Data | Static GeoJSON per state, committed; health verdicts committed by a bot every six hours |
| Builders | Python 3.12, standard library only, one script per feed |
| Hosting | GitHub Pages from the root of `main` |

## Run it locally

```bash
git clone https://github.com/warner-wvez/Ora.git && cd Ora
python3 -m http.server 8934          # then open http://localhost:8934/
python3 builders/build-states-tx.py  # rebuild one state, from the repo root
```

[Run locally](docs/1.3-run-locally.md) covers the two states that need a free key and how
to run the sweep.

## License, contributing, security

[PolyForm Noncommercial 1.0.0](LICENSE). To add a state, follow the checklist in
[CONTRIBUTING.md](CONTRIBUTING.md). To report a vulnerability, see [SECURITY.md](SECURITY.md).
