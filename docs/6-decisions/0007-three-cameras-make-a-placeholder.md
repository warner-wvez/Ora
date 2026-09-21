---
type: adr
---
# 0007. An image served by three or more cameras is a placeholder

Date: 2026-07-10. Status: Accepted.

## Context

About one in ten snapshot cameras serves a "camera unavailable" card, a frozen frame, or
nothing, and every agency's status field lies about it. A per-state list of what each
agency's placeholder looks like would be endless and always behind.

## Decision

Two cameras cannot see the same scene byte for byte, so an image served by three or more
cameras at once is not a camera view. Threshold three, not two, because a duplicate listing
of one camera makes a legitimate pair. Fingerprints are `(total size, sha256 of the first
1 KB)` from a `Range: bytes=0-1023` request, never HEAD. Confirmed clusters are remembered
in `known-placeholders.json` so a lone down camera is caught later. A real image unchanged
for over a day is `frozen`. The sweep reruns every six hours because feeds recover.

## Consequences

- The rule found Hawaii's card without being told Hawaii exists.
- A full sweep costs about 49 MB against 44 states' servers instead of 1.6 GB.
- Dead pins are greyed on the map, which is a feature under
  [decision 0001](0001-location-first.md).
- Distilled from commit dc7e804.
