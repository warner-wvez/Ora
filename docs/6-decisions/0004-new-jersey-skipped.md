---
type: adr
---
# 0004. New Jersey is skipped, with every door tried on record

Date: 2026-07-12. Status: Accepted.

## Context

Every other state had a public feed a static page could read. New Jersey's 666 cameras are
HLS with zero image mode, behind a Keycloak anonymous login, on two CDNs: wink.co, which
needs a 300-second one-time token, and the Turnpike's xcmdata.org, which needs a Referer
and origin-locks CORS to 511nj.org. No thumbnail endpoint exists on either. 511NY's feed
carried 66 labelled New Jersey cameras on shared roads until it stopped labelling them the
same day.

## Decision

New Jersey is not on the map, and the record of every door tried lives on its
[source page](../3.31-new-jersey.md) so nobody re-litigates it. If a door reopens, that
page is where to start.

## Consequences

- Coverage is 49 of 50 states and the README says so plainly.
- The only thing that would change the verdict is a thumbnail endpoint or a token-free
  stream; neither exists today.
- Distilled from commit 557c621.
