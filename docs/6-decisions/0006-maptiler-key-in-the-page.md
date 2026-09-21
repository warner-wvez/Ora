---
type: adr
---
# 0006. The MapTiler key lives in the page, origin-locked

Date: 2026-07-10. Status: Accepted.

## Context

The first basemap, OpenFreeMap's Positron, rate-limited and silently dropped whole states'
tiles. MapTiler's streets-v2 needs a key, and a static site on GitHub Pages has nowhere to
hide one: whatever the page sends, a visitor can read. The first key committed was the
account's default key, which MapTiler does not allow to be deleted, edited, or
origin-restricted.

## Decision

The page carries a named MapTiler key ("ora-site") whose allowed HTTP origins are
`warner-wvez.github.io` and `localhost`, and nothing else. The account's default key was
replaced (rotated) and is never used in code. `SECURITY.md` explains that the key in
`index.html` is public by design.

## Consequences

- A copied key does nothing from another origin.
- If tiles ever 403, check that the named key still exists and lists both origins in the
  MapTiler dashboard; a first "ora-site" key was once revoked mid-cleanup and briefly
  broke the live map.
- MapTiler analytics lag hours and browsers cache tiles, so near-zero dashboard usage after
  heavy testing is normal. Free tier is 100,000 tile requests a month.
- Distilled from commits 21ede3c and 07ca253.
