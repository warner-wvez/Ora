---
type: adr
---
# 0016. New Jersey plays through the relay

Date: 2026-10-22. Status: Accepted. Supersedes [0004](0004-new-jersey-skipped.md).

## Context

Decision 0004 left New Jersey off the map because none of its streams could play from a
static page: NJDOT's wink.co host wanted a five-minute `?otp=` code with every playlist,
and the Turnpike's xcmdata.org host wanted 511nj.org's `Referer`. It named the one thing
that would change the verdict: a token-free stream.

A fresh trace on 2026-10-22, from a HAR of 511nj.org/camera and direct requests, found it.
wink.co now serves the playlist and every segment with no code at all. Both hosts still
answer CORS to 511nj.org only, and the Turnpike still checks the `Referer`. Since 0004, Ora
has also gained the relay (decision 0013), built for exactly this kind of lock: a header a
page on another origin cannot send.

## Decision

New Jersey goes on the map, with its video played through the relay at
`relay.wvez.org/nj`. The relay adds 511nj.org's `Referer` and `Origin` and nothing else:
no login, no code, no stored credential. The camera list is read weekly by
`builders/build-states-nj.py` through the same silent guest login 511nj.org's own page
performs. Cameras NJ marks stopped are location-only pins (decision 0001).

If wink.co starts checking its code again, the relay fetches one at the moment a visitor
opens a camera, from 511nj.org's `getHlsToken`, the same call 511nj.org's page makes. That
is not built yet, because nothing needs it today.

## Consequences

- Every state is on the map: 808 New Jersey cameras, 794 of them with live video.
- The relay carries a fourth state. NJ video is about 0.5 Mbit/s per viewer, half of
  Florida's. The relay strips wink.co's low-latency parts so the player asks for plain
  two-second segments, about one request every two seconds instead of four a second.
- The Turnpike reuses five segment names in a loop, so the relay never lets a browser
  cache a New Jersey segment.
- If 511nj.org changes the key that encrypts its request bodies, the builder's login fails
  and the committed New Jersey file stays as it was.
