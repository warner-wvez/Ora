---
type: adr
---
# 0001. Every camera location is a pin, feed or no feed

Date: 2026-07-10. Status: Accepted.

## Context

The first builders were honesty-first: a camera with no working image or stream was
dropped so the map never shipped a broken pin. That rule made the map smaller than the
world. California showed 2,047 cameras when Caltrans lists 3,197; Montana's 118 sites had
no way on at all. The product direction is trucking, commuter, and travel data, where the
question "is there a camera at this spot" matters on its own.

## Decision

A pin means a camera exists here. Builders drop a row only for validity: no or bad
coordinate, outside the state, a test feed, a camera another layer already carries, an
airport webcam. A camera with no feed emits one location-only view with `snapshot` and
`video` both `null`; the popup says "No live image at this camera", distinct from "Live
video unsupported here". The health sweep greys dead pins, and that greying is the
feature, not a bug. Every new state defaults to this rule.

## Consequences

- All 32 builders of the day were relaxed: California 2,047 to 3,197, Oklahoma 135 to
  193, Pennsylvania 1,414 to 1,522, Washington 1,516 to 1,524, Montana added. Each
  rebuild was compared against the committed count; a relaxed filter may only add, so a
  drop (New York 1,907 to 1,864) is read as feed drift, not a bug.
- The map carries about 46,100 locations instead of about 38,000.
- Distilled from commits a2ec692, 8a19bc0, c9ef56c, c021a29.
