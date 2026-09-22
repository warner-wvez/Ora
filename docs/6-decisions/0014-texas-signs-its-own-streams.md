---
type: adr
---
# 0014. Texas signs its own streams in the browser instead of using the relay

Date: 2026-09-22. Status: Accepted. Narrows [0013](0013-relay-for-locked-streams.md).

## Context

Decision 0013 put Texas next in line for the relay, on the assumption that its lock was
Florida's: a header a page on another origin cannot set. Tracing drivetexas.org showed it
is not. Texas asks for a JWT in the query string and nothing else. No cookie, no `Referer`,
no anti-forgery header, and the stream returns `Access-Control-Allow-Origin: *`. The token
comes from the same MapLarge table the builder already reads, which is also `*`.

Everything the relay exists to do, a browser can do here. Routing 3,426 Texas streams
through a 256 MB container on a VPS with about 600 MB free would have bought nothing and
added the project's largest state to its one running dependency.

The token has an awkward shape, measured rather than assumed:

- It is not minted on demand. It is a stored column, regenerated when TxDOT rebuilds the
  table about every 300 seconds, and it lives 300 seconds.
- One token opens every camera, across cities and stream hosts.
- Token age falls monotonically down the table, so the last row holds the freshest.
- The active table keeps serving its token past `exp`, so for roughly 19 seconds in every
  300 nothing plays. An expired token is a hard 401, and a playing stream dies with it,
  measured 18 seconds past `exp`. drivetexas.org has the same gap.

## Decision

A state may be flagged `"sign": "<recipe>"` on its index entry instead of `"relay"`. The
map mints the credential itself at play time and plays the agency's host direct. The rules
from 0013 carry over unchanged: the stored URL stays the agency's own, the rewrite happens
only at play time, nothing is stored, and a state is signed only once its lock is
understood and written on its source page. Decision 0002 still holds: the token is never
written to `states/TX.json`, only added in memory when a camera is opened.

The relay stays the answer for a lock a browser genuinely cannot reproduce, which is still
Florida, Pennsylvania and North Carolina.

Because the credential expires mid-playback, a signed player rewrites the token on every
hls.js request rather than only at load, and treats a network failure as the known gap for
70 seconds before calling the camera dead.

## Consequences

- Texas plays, on the map's own bandwidth. No VPS cost, no new dependency, and the
  relay's blast radius does not grow to include the largest video state.
- Texas is dark for about 19 seconds in every 300, which cannot be fixed from this side.
  The player waits it out instead of reporting 3,426 cameras dead every five minutes.
- How a locked state is played is a decision, not something the feed reports, so a rebuild
  would drop it. `build-states-tx.py` now writes `sign` on every run and `build-states.py`
  carries `relay` and `sign` across a rebuild. This was already a live bug for Florida:
  `python3 builders/build-states.py FL` would have dropped its `relay` and taken Florida
  dark with no error.
- Pennsylvania and North Carolina should be traced before assuming they need the relay.
  Texas was assumed to be Florida-shaped and was not.
