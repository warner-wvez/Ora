# Ora map handoff — re-scoped for camera curation

**Goal: pick ~18 training cameras as fast and cleanly as possible.** Everything on the original
21-item list that doesn't serve that is deferred to the bottom.

The workflow being optimised:
> browse a state → hide the dead ones → click a camera → judge scene + vehicle scale →
> arrow to the next → collect the keepers → hand the list off

Six changes make that fast. **Two of them aren't on the original list, and they're the two
highest-value changes in this document.**

Every claim below cites `index.html:line` and was checked against the code, not guessed.

---

# THE CURATION PATH

| | change | effort | why it matters for picking cameras |
|---|---|---|---|
| **C1** | Show delivered resolution | **~8 lines** | The ≥640px bar is the ONE hard filter, and the map can't tell you today. Kills bad cameras before you even look. |
| **C2** | "Copy list" export on a route | **~10 lines** | Closes the loop: curate → Copy → paste. No spreadsheet. |
| **C3** | Uniform fullscreen size | **CSS, ~6 lines** | Every camera opens the same size, so scenes are comparable. |
| **C5** | Fix the false "NOT LIVE" | **2 numbers** | Stops the map lying and making you reject good cameras. |
| **#18** | Fullscreen ✕ | **CSS** | It's clipped off-screen today. |
| C6 | Live-only filter | medium | Hides dead snapshot cams. Partly blocked by #21. |
| **C4** | **Arrow cycling** | **the real build** | Nice, but the slowest to build and the least value per hour. |

**C1 + C2 + C3 + C5 + #18 is roughly an afternoon and gets you most of the value.**
**Defer C4 if you want to start picking sooner** — C1 saves more of your time than C4 would,
because it eliminates the cameras that can't work *before* you open them, and that's most of the
rejects.

---

## ★ C1 (NEW) — Show the delivered resolution in the popup and fullscreen

**Do this one first. It is ~8 lines and it changes everything else.**

The single hard filter in the camera spec is **≥640px wide** — below that the detector is blind
and no model fixes it. And right now **the map cannot tell you what any camera delivers.**
There are **zero** references to `videoWidth` or `naturalWidth` in all 1,518 lines.

But the browser already knows, for free, the moment the media loads:

```js
// video  (playDir:636, buildEnlarge:732)
vid.addEventListener('loadedmetadata', () => show(`${vid.videoWidth}×${vid.videoHeight}`));
// snapshot
img.addEventListener('load', () => show(`${img.naturalWidth}×${img.naturalHeight}`));
```

Render it next to the camera name, and colour it: **green ≥640px, red <640px.** Curation stops
being guesswork and becomes a readout.

**Bonus:** this is also the per-camera resolution census the detection spike asked for — you'd be
collecting it passively as you browse, instead of running a separate 46,100-camera sweep.

## ★ C2 (NEW) — Export a route as a camera list

**The routes feature is already the curation tool.** `addCameraToRoute:1172` already stores
exactly what's needed:

```js
r.cams.push({ k, name: props.name, coords, snapshot, video, camId });
```

All that's missing is a way to get it out. Add a **"Copy list"** button to the route header
(`renderRouteHeader:1234`) that writes the route's cams to the clipboard as JSON or TSV.
**~10 lines.**

Then the whole curation loop closes: make a route called `training-set`, add cameras as you find
them, hit Copy, paste. No spreadsheet, no re-typing camera names, no transcription errors.

## C3 — Uniform fullscreen size (was #11) ⚠️ **one trap, read this**

**Today:** `.enlarge-media:164` is `width:auto; height:auto; max-width:96vw; max-height:84vh`.
The media renders at its **native size**, capped. So a 320x240 camera opens as a postage stamp
and a 1920x1080 one fills the screen — you can't compare two cameras at all.

**Fix:** give `.enlarge-box` a fixed size (e.g. 16:9 at `min(1600px, 92vw)`), and let the media
fill it.

**The trap.** You said "stretch the feed to the size." `object-fit: fill` *literally* stretches:
a 4:3 camera in a 16:9 box makes **every vehicle 33% too wide**. That would corrupt the exact
judgment you're trying to make — vehicle shape and scale.

**Recommendation:** `object-fit: contain`. Same on-screen size for every camera, letterboxed,
**no distortion.** You still see the full upscaling blur, which is the quality loss you actually
want to evaluate.

Ship both behind a one-key toggle (`contain` ↔ `fill`) so you can flip and decide for yourself —
that's what you asked for, and it costs one line.

```css
.enlarge-box   { width: min(1600px, 92vw); aspect-ratio: 16/9; }
.enlarge-media { width: 100%; height: 100%; object-fit: contain; }  /* 'fill' = stretched */
```

## C4 — Arrow-cycle between cameras (was #9)

The biggest build on the curation path, and worth it: it's the difference between
*click → back to map → hunt → click* and *click → → → →*.

Needs: an ordered camera list for the current state, prev/next wiring in **both** the popup and
the fullscreen overlay (they're separate code paths — `wireCameraUI:660` and `buildEnlarge:732`),
and the cross-state handoff notice you described.

Cheapest correct source for the order: `dataCache[k].features` is already the state's camera
array, and the selection already knows `{k, i}` (`camsHitAction:917` uses `p.k` / `p.i`). So
next = `i+1`, prev = `i-1`, and running off the end tells you which state is next.

## C5 — The false "not live" (was #19) — **this will actively lie to you during curation**

Not the same bug as #21. Fix it before you curate or you'll reject good cameras.

`CCTV02-US70-446E_OLDAIRPORT` has a video URL, a snapshot, and a **clean** sweep verdict — so
`applyStatus` correctly calls it `live`. The "NOT LIVE" badge comes from a **second, independent**
runtime watchdog, `watchLiveness:615`:

```js
still = delta(f0,f) < 0.02 ? still+1 : 0;
if (still >= 2) { markNotLive(wrap); return; }   // 2 samples × 3.5s = 7 seconds
```

It samples the video into a **48×36** thumbnail and declares the stream dead if two consecutive
samples barely differ. **A genuinely live camera pointed at a quiet road has near-identical
frames.** After 7 seconds without traffic it kills itself.

**Fix (2 numbers):** `delta < 0.004` and `still >= 5` (~18s). A truly frozen synthetic frame has
delta ≈ 0, so a tight threshold still catches it. Leave the `popupWatch` 12s no-fragment timeout
and the `currentTime` stall check alone — those are sound.

## C6 — Live-only filter (was #16)

The `status` field already exists on every feature; this is a filter UI plus
`map.setFilter('cams__points', …)`.

**Caveat, and it's why this is last on the path:** it will only hide the *snapshot* cameras the
sweep caught. Because of the bug in #21 below, **every video camera is blue regardless of whether
it works**, so the filter can't hide dead video cameras. It's still worth having — it cuts the
snapshot-only dead ones — but it is not a substitute for actually looking, until #21 lands.

---

# ALSO CHEAP, AND THEY HELP (grab them while you're in here)

| item | where | effort |
|---|---|---|
| **#18** fullscreen ✕ too small | `.enlarge-close:166` is 32px at `top:-14px; right:-14px` — it **hangs outside the box corner** and gets clipped on smaller viewports. That's why it feels broken. Move inside, 40px, raise z-index. | CSS |
| **#10** collapse side panel | `#panelToggle` **already exists and is already wired** (`:206`, `:215`) — it's just CSS-gated to mobile. Un-gate it. | ~10 lines CSS |
| **#7a** always show camera counts | The `<span class="cnt" id="cnt-${k}">` elements **already exist** (`:1387`); they're only filled when a layer is on (`:1027`). Populate from `LAYERS[k].count` in `renderCamList`. | ~4 lines |
| **#20** search for a camera by name | **Already works** (`runSearch:1105` matches `f.properties.name`). It only *feels* broken because it searches active layers only. Verify, don't rebuild. | 0 |
| **#15** cursor affordances | No `cursor:pointer` on pins today. Add `map.getCanvas().style.cursor` on hover in `bindCamsHandlers:935`. | ~10 lines |
| **#13** IL off → ticket map off | `disableLayer:1058` doesn't cascade. | ~3 lines |

---

# DEFERRED — not on the curation path

## #21 / #12 — Live vs not-live accuracy ★ highest value on the *product* roadmap

Not needed to curate 18 cameras (you'll be looking at each one anyway), but it's the biggest real
bug in the app and it blocks C6 from being trustworthy.

**Root cause, proven.** `applyStatus:1005`:

```js
const playable = !!(d.video && hasVideo);      // only checks the URL EXISTS
if (d.health && !playable) { d.status = 'offline'|'frozen'; }
else d.status = playable ? 'live' : 'snapshot';
```

`playable` checks that a video URL **exists**, never that it **works** — and when it's true, the
health verdict is **discarded entirely**.

- **20,928** camera views are forced to `live` (blue) unconditionally.
- **872** of those are *already flagged dead by the sweep* and still render blue.
- **5,695** views have a video URL and **no snapshot at all** — `probe-health.py` has nothing to
  probe. They can never be marked dead by any means that exists today.

**This is deliberate, not sloppy.** The comment says *"a working stream outranks a dead
snapshot,"* and that's correct — a camera really can have a dead snapshot and a live video. **So
you cannot fix this by "respecting health."** That would wrongly grey working cameras. The only
correct fix is to actually probe the video.

**Fix:**
1. `probe-health.py`: for each video URL, HTTP `GET` the `.m3u8` and assert `200` + body contains
   `#EXTINF`. **No ffmpeg needed** — as cheap as the snapshot probe. Sizing: a 1,114-camera
   snapshot sweep ran in **1.4 min** at 16 threads, so ~21k video URLs ≈ **25–30 min**. Fine for
   the scheduled action that already runs.
2. Health JSON: add a `video` status map alongside `status`.
3. `index.html:1005`: `const playable = !!(d.video && hasVideo && d.videoHealth !== 'dead');`

One backend sweep + three frontend lines closes #12 and #21 and makes C6 trustworthy.

## #1 — All states on at launch ⚠️ not the freebie it looks like

`setAllStates(true)` is 3 lines — but `states/*.json` + `cameras.json` + `cameras-nyc.json` =
**18 MB across 52 files**, all fetched before the map is usable. Ship it naively and first paint
will feel broken.

Needs a prebuilt lightweight index (`{k, i, lon, lat, status}` only) to cluster from, hydrating
the full state file on selection.

*(Not on the curation path: you'll be working one state at a time anyway.)*

## The rest

- **#2 / #3 / #14** cluster expand + morph feel — tune Supercluster `:864`
  (`{radius:32, maxZoom:11, minPoints:3}`) and `startCamsMorph:873`. #3 (explode a 7–12 cluster
  instead of zooming) is new behaviour: `camsIndex.getLeaves()`.
- **#17** loading states — `mediaHTML:540`, `buildEnlarge:732`.
- **#6** switch views inside fullscreen — port the popup's existing `.dir-btn` logic.
- **#8** make the IL dropdown look like a dropdown — `.il-toggle:64`.
- **#5** real geocoding — new dependency, and a **decision**: does the address search merge with
  the camera-name search into one ranked box (the production pattern), or sit beside it?
- **#4** NY/NYC — *label-only* is 10 minutes; a *true merge* is data + layer surgery (`nyc-cam`
  builds its image URL from `camId` at render time, `:373`).
- **#15b** Michigan 6-day-old feed — **diagnose first.** If the DOT serves a *fresh file* with a
  *stale burnt-in timestamp*, the bytes change every fetch, the hash changes, and the frozen check
  can never see it. Catching that means OCR'ing the burnt-in clock — a project, not a fix.
  (Also: MI is in the sub-640px blind cohort. Low value to chase.)

---

# Architecture crib

`index.html` is one 1,518-line file. MapLibre GL + **Supercluster** (not MapLibre's built-in
clustering).

| system | where | notes |
|---|---|---|
| Layer catalog | `:371` `LAYERS`, hydrated from `states/index.json` at `:1503` | one entry per state + `il-cam`, `nyc-cam`, `chi-enf` |
| **One morphing camera pipeline** | `:842-913` | ALL active states feed **one** Supercluster index → **one** source → 3 layers. Config `:864`. |
| Cluster click | `camsHitAction:917` | `getClusterExpansionZoom()` → `easeTo`. Zooms; doesn't explode. |
| **Status seam** | `applyStatus:999` | THE one place status is decided. Pin colour, badges, age line, route tiles all derive from it. |
| Health data | `states/health/<CODE>.json` ← `probe-health.py` | **snapshots only. Video is never probed.** |
| Runtime liveness | `watchLiveness:615`, `markNotLive:609` | a *second, independent* liveness path |
| Side panel | `renderCamList:1384`, `syncMaster:1071`, `setAllStates:1079` | tri-state master already done |
| Search | `runSearch:1105` | matches name + roadway, **active layers only** |
| Fullscreen | `openEnlarge:714`, `buildEnlarge:732` | single `dir`; no view switching, no loading state |
| Popup | `buildLivePopup:591`, `playDir:636`, `wireCameraUI:660` | has the `.dir-btn` view switching fullscreen lacks |
| **Routes (= the curation tool)** | `addCameraToRoute:1172`, `renderRouteHeader:1234` | already stores `{k, name, coords, snapshot, video, camId}` |

## Traps

- **`applyStatus:999` is the single status seam.** Change it once, everything follows. Do not add
  a second source of truth.
- **There are TWO independent liveness paths**, and they explain different bugs: the *sweep*
  (`states/health/`, snapshots only) → #21, and the *runtime watchdog* (`watchLiveness:615`,
  pixels) → #19. **Don't conflate them.**
- **One shared Supercluster index** (`:842`). Cluster changes hit every state at once — by design,
  but it means no per-state hacks.
- **`snapKey:364` must stay byte-identical to `probe-health.py`'s `snap_key`.** Wyoming needs its
  query string kept; every other state needs it dropped. Break this and a whole state collapses to
  a single status.

---

# Order

1. **C1** (resolution readout) — 8 lines, and it makes every other decision informed.
2. **C5** (false "not live") — 2 numbers, and it stops the map lying to you mid-curation.
3. **C3** (uniform fullscreen) + **#18** (the ✕) — CSS, same file region.
4. **C2** (export a route) — closes the loop.
5. **C4** (arrow cycling) — the real build.
6. **C6** (live filter) + the cheap extras.
7. Then, when curation is done: **#21**, then **#1 + lite index**, then the rest.
