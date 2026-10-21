# TomTom evaluation proxy

Lets the map, served from this machine, try a route preview on TomTom's APIs: search a place
or address, open its card, and compare two or three routes by trip time, traffic delay and the
cameras on each, with traffic colours on the roads. It is for testing on this machine only,
under the Evaluation Use terms of TomTom's Portal agreement: the page turns these features on
only when it is served from localhost and this proxy answers, so the live site never calls
TomTom. Production will use another provider. The user-facing behaviour is in
[docs/2.3-route-preview.md](../../docs/2.3-route-preview.md).

Node 20+, no dependencies.

    node --test tools/tomtom-eval/tomtom.test.js     # ten unit tests
    node tools/tomtom-eval/proxy.js                  # http://127.0.0.1:8792
    curl http://127.0.0.1:8792/healthz               # key loaded? usage this month

## The key

Make a free key at developer.tomtom.com (no card). Copy it, then save it where only the proxy
reads it:

    mkdir -p ~/.config/ora && pbpaste | tr -d '\n' > ~/.config/ora/tomtom.key && chmod 600 ~/.config/ora/tomtom.key

The key never reaches the page, the repo or a log. `TOMTOM_KEY_FILE` points the proxy at a
different file.

## What it calls

| Proxy path | TomTom API | Free each month |
|---|---|---|
| `/search?q=&near=lat,lon` | Search API, fuzzy search, US only | 2,500 |
| `/route?from=lat,lon&to=lat,lon` | Routing API, traffic on, 2 alternatives, traffic and important-road sections, no turn instructions | 20,000 |
| `/traffic/{z}/{x}/{y}.png` | Raster flow tiles, `relative0` style | 200,000 |

TomTom blocks requests at the free limit instead of billing. The proxy counts each call in
`~/.config/ora/tomtom-usage.json` and stops at 98% of each allowance with a plain error, so the
page can say why. Only pages served from `localhost` or `127.0.0.1` may call it, it listens on
`127.0.0.1` only, and tiles carry a one-minute private cache header, the per-client caching
the terms allow (11.4).
