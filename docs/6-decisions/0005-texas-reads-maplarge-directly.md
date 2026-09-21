---
type: adr
---
# 0005. Texas is read from MapLarge directly, correcting the first investigation

Date: 2026-07-09. Status: Accepted.

## Context

The first look at TxDOT's drivetexas.org reported three verified blockers: statewide
queries return HTTP 500 so only small polygons work, the response carries no coordinates,
and a separate coordinate source or tile decode would be needed. All three were false.
The MapLarge API answers any malformed or unrecognised query with a bare HTTP 500 and a
generic HTML page, so an unknown key, a bad `where` clause, and a real server fault are
indistinguishable, and the investigation had tested a `where` clause that never parsed.

## Decision

Drop the `where` clause entirely: the full table pages cleanly with `start` and `take`.
Name `XY` in `sqlselect`: every row then returns `POINT (lng lat)` as WKT. Resolve the
table id fresh on every run because it rotates. Nothing is scraped, geocoded, or
approximated.

## Consequences

- Texas shipped with about 3,430 live-video cameras the same day.
- The working rule for this API: change one variable at a time, because a bad request is
  indistinguishable from a server fault.
- Distilled from commit 9f1e07f and the correction note that replaced the first handoff.
