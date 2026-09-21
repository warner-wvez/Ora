---
type: page
---
# Camera health

Roughly one in ten of Ora's snapshot cameras is not showing a live view, and every source
lies about it. Hawaii reports `status: OK` on all 52 cameras serving its "Image
Temporarily Unavailable" card. WSDOT reports `IsActive: true` on ferry cameras frozen
since 2003. Kansas served a red LIVE badge over 184 streams that answer 401. So Ora checks
for itself, in two different ways, because of one browser rule.

## Snapshots: the sweep

`scripts/probe-health.py` visits every snapshot camera and classifies it:

| Verdict | Meaning |
|---|---|
| `offline` | The image does not load at all |
| `placeholder` | A "camera unavailable" card, not a road |
| `frozen` | A real image, unchanged for over a day |

Cameras that are fine are absent from the file. The map greys a pin with any verdict, and
the popup says which and when it was last checked.

**Placeholders need no per-state list.** Two cameras cannot see the same scene byte for
byte, so any image served by three or more cameras at once is not a camera view. The
threshold is three, not two, because a duplicate listing of one camera makes a legitimate
pair. The rule calibrates itself and found Hawaii's card without being told Hawaii exists.
Clusters are confirmed by pulling two full bodies and checking they are identical, and
confirmed fingerprints are remembered in `states/health/known-placeholders.json`, which is
what catches the same card later when only one camera is down.
[Decision 0007](6-decisions/0007-three-cameras-make-a-placeholder.md).

**It is cheap.** `Range: bytes=0-1023` returns the first kilobyte and the true total size in
`Content-Range`, so a camera fingerprints as `(total_size, sha256(first 1 KB))` for about
1.2 KB of traffic. Every DOT host honours it. Pulling about 41,000 whole JPEGs four times a
day would be 1.6 GB per run off 44 state governments' servers; this is about 49 MB. Do not
"optimise" it into a HEAD request: Georgia and North Carolina answer HEAD with
`Content-Length: 0`.

**It reruns.** `.github/workflows/camera-health.yml` runs the sweep every six hours at 17
past the hour (off the hour, because every DOT scraper on earth runs at :00) and commits
the verdicts as `health: Record the six hour camera sweep`. Feeds recover: a camera dead
this week is fine next week, and a one-off sweep would rot into a different kind of lie
than the one it fixed. The sweep takes about 40 minutes, so the bot rebases before it
pushes; it owns `states/health/` alone, so the rebase cannot conflict.

Measured bad rates when the sweep first ran: Georgia 25 percent, Alaska 27, Florida 13,
New York 9, Arizona 10, Washington 3, California, Pennsylvania, and Utah near zero.

## Video: the browser

A dead stream behind a poster used to look exactly like a live camera on an empty road.
The browser can settle this itself, at runtime, with no data file. hls.js feeds video
through Media Source Extensions from a `blob:` URL, which is same-origin, so the canvas is
not tainted and the pixels are readable. `watchLiveness()` samples every 3.5 seconds and
asks two questions: is `currentTime` advancing, and is the picture changing? A real sensor
is never perfectly still, so two identical consecutive frames mean a synthetic one. Either
failure turns the red LIVE badge grey and NOT LIVE, keeping the poster, since a recent
still beats a lie. A 12-second watchdog covers streams that never start, which matters
for the video-only states because a dead SkyVDN stream hangs without a fatal error.

## Why two methods

A cross-origin `<img>` throws `SecurityError` on `getImageData`, and DOT image hosts send
no CORS header, so only a snapshot's dimensions survive in the browser. That asymmetry is
the whole reason the snapshot half has to be precomputed by a script and shipped as data
while the video half can be judged live. Video-only states (Texas, Delaware, Maryland,
Missouri, Oklahoma, West Virginia) therefore have no health file at all.

## The health key

A health file is keyed by the snapshot URL with bare-digit cache-busters stripped and named
query parameters kept, the same `snapKey` rule the page uses. Wyoming's `?ref=` and
Mississippi's `streamname=` carry the camera's identity, so the naive `split('?')[0]`
would have collapsed 757 Wyoming views into one key. The rule was verified byte-identical
on the 4,160 snapshots of the 27 states that use bare-digit busters.

## Runbook

```bash
python3 scripts/probe-health.py           # all snapshot states, about 40 minutes
python3 scripts/probe-health.py HI WA     # just these
```

Run from the repo root. Writes `states/health/<CODE>.json`.
