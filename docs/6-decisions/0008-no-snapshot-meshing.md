---
type: adr
---
# 0008. Snapshots are not meshed into video

Date: 2026-07-09. Status: Accepted.

## Context

EarthCam-style products poll snapshot cameras fast and play the frames as a stutter video.
The idea was to do the same for Ora's snapshot-only states.

## Decision

Not worth building. Measured on Washington, the only agency whose images expose
timestamps: the median camera replaces its JPEG every 2 minutes, the fastest every minute
or so. Snapshot-only agencies refresh every one to two minutes at best, so polling faster
re-fetches identical frames. Ora instead polls each Washington camera at its measured rate
and every other snapshot at a flat cadence, and states a refresh rate only where it was
measured over two observed refreshes.

## Consequences

- No synthesized cadence anywhere: South Dakota's single-sample `refresh_sec` was removed
  the day it shipped.
- Live video comes only from a real stream; snapshot states are labelled as such.
- Distilled from commits 150fbe6 and 0dbaace.
