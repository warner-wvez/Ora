---
type: adr
---
# 0015. The view decides which states load

Date: 2026-10-21. Status: Accepted. Supersedes [0009](0009-coverage-pins-are-informational.md).

## Context

Decision 0009 kept layer state in the sidebar only, so the first screen was a 49-row state
checklist and the map showed no cameras until a state was ticked. That is how the data is
stored, not how a map is used: most visits are "cameras near here", and a list of 49
choices stands between the visitor and any value. The 2026-10-20 UX review (Tesler's law,
Hick's law, Pareto) put this first on the list.

## Decision

States load for whatever the map shows. On every move, once the zoom is 6 or closer, the
page loads the states whose box overlaps the view, at most four per move, nearest the
middle of the view first. A state's box is the bounding box of its outline padded by 0.2
degrees, because the outline is coarse (decision 0011); the box only decides what to fetch
and never hides a camera. Loaded data stays cached and is never refetched.

The state list moves into a collapsed Sources section. Unticking a state there holds it off
for the session: the view does not load it again until it is asked for (its box, its
bubble, a search pick). The Chicago ticket map is a different kind of data and stays an
opt-in toggle in its own section.

The share link carries only the opt-in layers. Position and zoom bring the states back on
their own, and an older link that names states (`#l=st-WA`) still loads them, so it opens
on the view it was copied from.

## Consequences

- A link or reload at city zoom shows pins with no clicks.
- Each state's bubble hides once its cameras load, so a zoomed-out map mixes clusters for
  loaded states with one bubble for every other state.
- A wide view at zoom 6 can leave some states in view unloaded; their bubbles stay up and a
  tap loads them.
