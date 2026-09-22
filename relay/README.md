# Stream relay

Plays Florida's live video for the map. fl511's stream host answers only requests that
carry fl511.com's own Referer plus a per-camera token, which a page on another origin
cannot send; this service fetches the stream wearing those headers and passes it on.
Node 20, no dependencies. Full explanation: [docs/1.4-stream-relay.md](../docs/1.4-stream-relay.md).

    node --test relay.test.js                       # five unit tests
    PORT=8791 node server.js                        # local, allows http://localhost:* origins
    curl http://127.0.0.1:8791/healthz
    curl http://127.0.0.1:8791/fl/691/se7/chan-3936_h/index.m3u8

Deployed as a Docker container on the VPS behind the Coolify Traefik proxy at
relay.wvez.org; the exact `docker run` is in the docs page.
