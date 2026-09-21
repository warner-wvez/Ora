---
type: adr
---
# 0011. The state outline is never the primary in-or-out filter

Date: 2026-07-11. Status: Accepted.

## Context

`states-outline.json` draws crisp state boundaries on the coverage overview. It is coarse.
Used as a point-in-polygon filter it puts Washington's Whidbey, Vashon, and Anacortes
ferry cameras and the whole Vancouver riverbank outside the state (67 real cameras
silently deleted) and nicks Arkansas's Mississippi-bridge cameras.

## Decision

A builder rejects rows by a loose bounding box that catches bad coordinates, or by the
feed's own state label, never by the outline as the primary test. The one exception is
scoped: Missouri drops Kansas-side Kansas City cameras by a point-in-Missouri test against
the outline restricted to longitude below -94, where the border is a straight line, because
Platte County makes a bounding box impossible there.

## Consequences

- Coastal and river-border states keep their ferry and bridge cameras.
- A future builder that needs a geographic cut says in its docstring why the box is loose
  and what the label filter is.
- Distilled from commits 150fbe6 and 267e25c.
