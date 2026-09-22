---
type: adr
---
# 0013. A locked stream is relayed through the VPS rather than dropped

Date: 2026-09-21. Status: Accepted. Extends [0003](0003-cors-alone-proves-nothing.md).

## Context

In September 2026 four states' stream hosts began refusing any browser that is not on the
agency's own site: Florida (4,325 streams), Pennsylvania (1,304), North Carolina (1,046),
and Texas (3,426). Florida's lock was traced in full: the host demands a per-camera token
minted through fl511.com and a `Referer` of fl511.com. The token is easy and stable; the
Referer is a header a browser page cannot set, and fl511 also refuses to be framed. Under
decision 0003 the honest static answer was to flip all four to snapshot-only. The product
direction is live video for trucking and commuter use, and a map that says LIVE on 10,101
cameras it cannot play is worse than either choice.

## Decision

Live video is worth one server. A relay on the existing VPS fetches a locked stream
wearing the agency's own headers and passes it to the map. The rules that still hold:

- The stored URL stays the agency's own; the rewrite to the relay happens at play time,
  keyed by a `relay` field on the state's index entry, so data and docs never lie about
  where a stream lives.
- The relay reproduces exactly the anonymous, no-login flow the agency's page performs,
  caches tokens, and backs off on the agency's rate limit. It stores no credential.
- A state is relayed only after its lock is understood and written up on its source page.
- Cloudflare Workers are not an option for these hosts: they cannot reach port 8200.

Decision 0002 is unchanged: a URL carrying an expiring token is still never stored.

## Consequences

- Florida plays again. The other three stay honest (snapshot or location-only) until each
  has its recipe; Texas is the priority by size.
- Ora now has one running dependency, `relay.wvez.org`, next to n8n on the VPS. If it is
  down, Florida degrades to NOT LIVE and snapshots, the same as a dead stream today. The
  health sweep does not yet watch it.
- Bandwidth for every relayed view flows through the VPS: about 1 Mbps per viewer, inside
  the plan's allowance by two orders of magnitude at portfolio traffic.
- The relay automates a public site's own page flow to get around a control it added on
  purpose. An email to FDOT asking for proper feed access is the right parallel step.
