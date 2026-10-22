# Changelog

All notable changes to Ora. The format follows keepachangelog.com; dates are the month the
change landed on main, and each line ends with its commit. The six-hourly health-sweep
commits are not listed.

## 2026-10

### Added
- New Jersey is on the map, the last state: 808 cameras, 794 with live video played through
  the relay. Its streams no longer need the five-minute code they did in July, only
  511nj.org's headers, which a page elsewhere cannot send and the relay can.
- Tap a landmark, shop or restaurant on the map and its card opens with its name, kind and
  the cameras within a mile; tap empty map to close it.
- A route preview for testing on your own machine: search a place or an address, compare two
  or three routes by trip time, traffic delay and the cameras on each, with traffic colours,
  a time bubble on each route and a 3D preview ride. It runs on TomTom's APIs through a local
  proxy that holds the key, under their evaluation terms, and the live site never calls it.
  On that machine a card also gets the address, phone and website from Overture Maps Places,
  built per region by `builders/build-places.py`.
- A locate button under the zoom buttons shows where you are as a blue dot with an accuracy
  ring and flies there at city zoom. It asks for location only when tapped, and says so in
  one line if location is off. Opening the bare address returns to the last view.
- North Carolina video plays again, 1,046 streams through the relay. Its token is
  Pennsylvania's two calls on drivenc.gov's own hosts, and a browser cannot make the first
  one, so the relay mints it.
- Indiana video plays again, 748 streams. Its stream ids carry a random suffix that had
  changed since July, so every stored link was 404 and Indiana was a snapshot state.
- Every state now rebuilds on a schedule: Montana every hour, all others on Mondays. A
  safety check holds back any state the rebuild made worse, and Montana's 425 images work
  again. When a whole state goes dark, the health sweep opens a GitHub issue.

### Changed
- Search results list inside the panel, two lines a row, instead of a dropdown the panel cut
  off. The panel is wider, 340 px.
- The map moves more smoothly. A wheel or pinch zoom no longer rebuilds the camera pins on
  every frame (40 rebuilds in one level of wheel zoom, now 1), the panel is solid white
  instead of a blur over the moving map, phones draw the map at 2x instead of 3x, and a flick
  glides on at the finger's speed, about 3.6 times farther than before.
- Cameras load for whatever the map shows. At zoom 6 or closer the states in view load on
  their own, up to four per move, so the first screen no longer asks you to tick a state.
  The state list moved into a collapsed Sources section, the Chicago ticket map got its own
  opt-in section, and the tagline is gone. The link now carries only the ticket map; older
  links that name states still open on the same view.
- New York builds from 511NY's new CARS 511x map, `builders/build-states-511x.py`: 1,742
  NYSDOT cameras, all with live video, and a live preview image for each. Compass chips
  carry forward from the old feed by stream name. Colorado moved to the same platform and
  the same builder.
- The GraphQL builder sends the exact queries the sites' own pages send, the only text the
  servers now accept, and pages Minnesota's list so its gateway does not time out.

### Fixed
- A state's name no longer lands on a neighbour's bubble on the zoomed-out map. On a
  phone, "Oklahoma" had sat on Texas.
- Every New York snapshot had been dark since about 2026-09-30, when 511ny.org left the
  DataTables platform and its old image path began returning a web page.
- Alabama showed a "No camera" card on 626 of 629 cameras after ALGO renumbered them all;
  rebuilt to 645.
- Oklahoma's 494 stored streams were all 404 after its stream ids rotated; rebuilt to 552
  views that play.
- Florida and Pennsylvania video was down for about 19 hours on 2026-10-20 because the VPS
  disk filled with another service's error log, which failed every container health check.

## 2026-09

### Added
- Pennsylvania video plays again, 1,303 streams through the relay. Its lock is Florida's,
  a per-camera token plus the agency's own `Referer`, so the relay grew a second state:
  a path keyed by state, a per-state token cache and rate-limit backoff, and a simpler
  mint with no session to warm.
- Texas video plays again. TxDOT's lock turned out to be a token in the query string, not
  a header, so the map mints it in the browser and plays drivetexas.org's host direct:
  3,426 cameras, no relay, no VPS bandwidth. The token expires mid-playback, so a signed
  player restamps every request and waits out the ~19s per 300s when TxDOT has no valid
  token at all.
- The stream relay: Florida's host began refusing any browser not on fl511.com, so a
  150-line Node service on the VPS fetches those streams with fl511's headers and the map
  plays them through it. Florida is live again; the 4,325 stored URLs are unchanged
  (96d5cc3, d0772a8, 0d87c54).
- A license (PolyForm Noncommercial 1.0.0), a security policy that explains the two
  public keys, a code of conduct, and an environment example (c8daada, 2fc6815, 8455d96).
- Numbered docs with one page per state feed, twelve decision records, and a checker that
  runs in CI (9575d6b).

### Changed
- Builders moved to `builders/`, the health sweep and tooling to `scripts/`, the
  vehicle-detection spike to `research/vehicle-detection/`. Scripts run from the repo root
  (d6d3c56).
- Commit history rewritten once: AI co-author trailers removed from 78 commits and the two
  handoff files removed from every commit. Planning notes stay local (578ade9).
- The health bot's commit message follows the same shape as every other commit (d6d3c56).

### Fixed
- Rebuilding a state no longer drops how its video is played. `build-states.py` rewrote an
  index entry wholesale, so `python3 builders/build-states.py FL` would have silently
  removed Florida's `relay` and taken it dark with no error.

## 2026-07

### Added
- Ora itself: a live Apple-Maps-style dashboard of Illinois traffic cameras, then New York
  City, then Chicago's enforcement cameras with a safety-versus-revenue verdict joining
  crashes to every camera (65d9abf, 3576ee3, 77aeab8, 0ae3437).
- A stackable layer panel, search, satellite basemap, hover and selection feedback,
  in-layer filters, and shareable URLs (6510223, 43bb8e6).
- Fifteen states from Castle Rock's 511 DataTables platform, then seven from its GraphQL
  platform, with live video and saved Routes (0cba2a2, a3f83f3).
- Bespoke builders for California, Oregon, Virginia, Ohio, Texas, Washington, New York,
  Delaware, New Mexico, Tennessee, Oklahoma, Michigan, North Dakota, South Dakota,
  Arkansas, Wyoming, West Virginia, Missouri, Alabama, Kentucky, South Carolina, Rhode
  Island, Hawaii, Maryland, Mississippi, and the Maine Turnpike (829964c, f1cc32c,
  b0f064d, ca83ec6, 9f1e07f, 150fbe6, dc21899, 26e4187, b8f7c5c, 85b6f08, c413a85,
  2eab462, 41a57d3, 5f1a36b, 3ba36c1, 22fa678, 267e25c, 5522455, 4713c54, ada9757,
  24ca6f8, ff09495, c1aa867, 557c621, fa4bc03).
- The camera health sweep: placeholder, frozen, and offline verdicts from 1 KB range
  requests, rerun every six hours, with dead pins greyed on the map (dc7e804, 7587c9f).
- Measured per-camera refresh rates for Washington and a compass chip for the direction
  each camera covers (150fbe6).
- Full-screen enlarge, arrow-key cycling in spatial order, a delivered-resolution chip,
  route export, and a jump-to-camera box (b8f7c5c, 1fa2ffe, e18022f, 1ed317f).
- A mobile bottom sheet, a state store with explicit modes, and an interaction physics
  pass (c899235, 51cc4d6, 980e075, 31a1ec1).
- The vehicle-detection transfer spike, with its verdict that camera resolution, not the
  model, is the limit (1fa2ffe, b07359b).

### Changed
- Location first: every camera location is a pin, feed or no feed, across all builders
  (a2ec692, 8a19bc0, c9ef56c, c021a29).
- Basemap moved from OpenFreeMap to MapTiler with an origin-locked key; one supercluster
  pipeline with animated cluster morphing replaced per-state sources (4bd5393, 62f9b42,
  21ede3c).
- New England split into Maine, New Hampshire, and Vermont by the feed's own state label
  (fa4bc03).
- New York City folded into New York's sidebar row and arrow order (0a9c4fc).

### Fixed
- Kansas no longer claims live video over 184 dead token-gated streams; one dead camera
  no longer decides a whole state (4fef6d0, dc21899).
- The shared 511 builder merges into the index instead of overwriting it (dc21899).
- New York City popups said "No live image" for all 957 cameras (6be24a8).
- Sideways scroll past the map's right edge (9c3e050).

### Removed
- New Jersey, documented as skipped with every door tried (557c621).
