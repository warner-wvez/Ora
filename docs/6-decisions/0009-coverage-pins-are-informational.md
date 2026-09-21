---
type: adr
---
# 0009. Coverage pins are informational and never toggle a layer

Date: 2026-07-10. Status: Accepted.

## Context

The map opens on the whole country with a counted pin per covered state. Early versions
let a map click toggle a layer, which made panning accidentally turn states on and off and
made the sidebar and the map disagree about what was active.

## Decision

Layer state changes only in the sidebar. Map clicks never toggle filters. Coverage pins
show the state and its count; tapping one loads the state and flies in, but the checkbox
is the source of truth. If users ever expect the pin itself to act, the agreed fallback is
that a tap scrolls to and flashes the sidebar row, still not a toggle.

## Consequences

- The three-way "All states" box, "Show all states", and "Clear" are the only bulk controls,
  and none of them moves the map except "Show all states".
- Route-view taps move the map to the camera only and never fly to the state.
- Distilled from commits 4bd5393 and 3b1cbe9.
