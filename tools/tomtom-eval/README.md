# Local TomTom proxy

Lets the map, served from this machine, use the route preview on TomTom's APIs: search a place
or address, open its card, and compare two or three routes by trip time, traffic delay and the
cameras on each, with traffic colours on the roads. The live site gets the same features from
the relay ([docs/1.4-stream-relay.md](../../docs/1.4-stream-relay.md#tomtom)); this proxy is
for working on them locally, and both run the same code, `relay/tomtom-serve.js`. A page served
from `localhost` calls this proxy, never the relay. The user-facing behaviour is in
[docs/2.3-route-preview.md](../../docs/2.3-route-preview.md).

Node 20+, no dependencies.

    node --test relay/tomtom.test.js                 # unit tests
    node tools/tomtom-eval/proxy.js                  # http://127.0.0.1:8792
    curl http://127.0.0.1:8792/healthz               # key loaded? usage this month

## The key

Make a free key at developer.tomtom.com (no card). Copy it, then save it where only the proxy
reads it:

    mkdir -p ~/.config/ora && pbpaste | tr -d '\n' > ~/.config/ora/tomtom.key && chmod 600 ~/.config/ora/tomtom.key

The key never reaches the page, the repo or a log. `TOMTOM_KEY_FILE` points the proxy at a
different file. The relay on the VPS reads its own copy of the same key.

## What it calls

| Proxy path | TomTom API | Free each month |
|---|---|---|
| `/search?q=&near=lat,lon` | Search API, fuzzy search, US only | 2,500 |
| `/route?from=lat,lon&to=lat,lon` | Routing API, traffic on, 2 alternatives, traffic and important-road sections, no turn instructions | 20,000 |
| `/traffic/{z}/{x}/{y}.png` | Raster flow tiles, `relative0` style | 200,000 |

TomTom blocks requests at the free limit instead of billing. The relay and this proxy share one
key but count separately, so they split each allowance: the relay stops at 90% and this proxy
at 10% (`TOMTOM_SHARE`), each with a plain error the page can show. The counts are in
`~/.config/ora/tomtom-usage.json`. Only pages served from `localhost` or `127.0.0.1` may call
it, it listens on `127.0.0.1` only, and tiles carry a one-minute private cache header, the
per-client caching the terms allow (11.4).
