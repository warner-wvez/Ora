---
type: adr
---
# 0002. A stream URL carrying an expiring token is never marked video

Date: 2026-07-09. Status: Accepted.

## Context

Kansas and Massachusetts hand out stream URLs carrying a signed JWT with a 300-second
lifetime. The stream plays at build time, so the CORS probe passed and the state was
flagged `video: true`, and five minutes after the file was written every stream was dead.
Kansas shipped a red LIVE badge over 184 permanently-401 cameras.

## Decision

`video_plays()` refuses any URL with a `token=` parameter, because a short-lived credential
cannot live in a static JSON file. Such a state is an honest snapshot state. Following a
redirect that mints a token at play time is allowed (Missouri): the stored URL carries no
credential, and the browser re-follows it on every open.

## Consequences

- Kansas and Massachusetts are snapshot-only; their snapshots are fine.
- Arkansas's video (token plus origin lock) and New Jersey's wink.co streams (`?otp=`
  tokens) are refused by the same rule.
- Distilled from commit 4fef6d0 and the Missouri builder.
