# Stream relay

Plays Florida's, Pennsylvania's, North Carolina's and New Jersey's live video for the map.
The first three answer only with a per-camera token minted through the agency's own site
(Florida and Pennsylvania also demand the agency's Referer); New Jersey needs no token, only
511nj.org's Referer and Origin. A page on another origin can do neither, so this service
mints the token where there is one, fetches the stream, and passes it on.
Node 20, no dependencies. Full explanation: [docs/1.4-stream-relay.md](../docs/1.4-stream-relay.md).

    node --test relay.test.js                       # twelve unit tests
    PORT=8791 node server.js                        # local, allows http://localhost:* origins
    curl http://127.0.0.1:8791/healthz
    curl http://127.0.0.1:8791/fl/691/se7/chan-3936_h/index.m3u8
    curl http://127.0.0.1:8791/nj/w/hls/public/30/WF01-6478-AAD0-D5C0-F5D7_high/index.m3u8

Deployed as a Docker container on the VPS behind the Coolify Traefik proxy at
relay.wvez.org; the exact `docker run` is in the docs page.
