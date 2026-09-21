---
type: adr
---
# 0003. A CORS check alone proves nothing: refuse DRM and Referer locks too

Date: 2026-07-12. Status: Accepted.

## Context

After [decision 0002](0002-no-expiring-tokens.md) the video flag was decided by whether a
sampled playlist answered `Access-Control-Allow-Origin: *`. Two states passed that test
and could not play. Alabama's Wowza CDN answers CORS `*` but every chunklist carries
`#EXT-X-KEY:METHOD=SAMPLE-AES` (FairPlay via ezdrm), which hls.js cannot decrypt. Rhode
Island's Wowza Cloud CDN answers CORS open but 403s any request without `Referer:
dot.ri.gov`, a header a browser will not send from a static page. New Jersey's Turnpike
CDN does both.

## Decision

Newer builders read the chunklist and refuse any stream that names a key. A host that
demands a Referer is documented as unplayable and its video URLs are not stored. One
sampled stream never decides a state: `video_plays_any()` samples up to eight, because New
York's first camera happened to be dead and would have discarded 1,553 live feeds.

## Consequences

- Alabama and Rhode Island ship as honest snapshot states with `video: null` written on
  purpose, so a future naive CORS check cannot resurrect the URLs.
- New Jersey has no playable feed at all ([decision 0004](0004-new-jersey-skipped.md)).
- Distilled from commits 5522455, 24ca6f8, dc21899.
