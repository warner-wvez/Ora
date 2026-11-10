// The three TomTom calls behind Ora's place search and route preview, shared by the relay
// (relay.wvez.org/tt, for the live site) and the local proxy (tools/tomtom-eval, this machine).
// Node 20+, no dependencies. The URL shapes and the reshaping live in tomtom.js.
//
// The key is handed in by the server that read it from its file. It goes into the upstream
// URL and nowhere else: every error is scrubbed of it before it is logged or sent, and the log
// says which call and its status, never what someone searched for or where they drive.
const t = require('./tomtom');

// TomTom's place search now and then takes 20 s or more to answer; past 10 s the page is
// better told so than left waiting
async function upstream(url) {
  let r;
  try { r = await fetch(url, { headers: { accept: '*/*' }, signal: AbortSignal.timeout(10000) }); }
  catch (e) { if (e.name === 'TimeoutError') { const err = new Error('TomTom did not answer within 10 s'); err.status = 504; throw err; } throw e; }
  return { status: r.status, body: Buffer.from(await r.arrayBuffer()) };
}

const json = (status, body) => ({ status, type: 'application/json', cache: 'no-store', body: JSON.stringify(body) });

// use(kind) counts one call against the month and says whether it is allowed.
// Returns handle(pathname, searchParams) -> {status, type, cache, body}, pathname being one of
// /search, /route or /traffic/{z}/{x}/{y}.png.
function makeHandler({ key, use, log = () => {} }) {
  return async function handle(pathname, params) {
    if (!key) return json(503, { error: 'no TomTom key' });
    try {
      if (pathname === '/search') {
        const q = (params.get('q') || '').trim().slice(0, 120);
        if (q.length < 3) return json(400, { error: 'query too short' });
        if (!use('search')) return json(429, { error: 'monthly free search allowance used up' });
        const r = await upstream(t.searchUrl(key, q, t.parseLatLon(params.get('near'))));
        log('search', r.status);
        if (r.status !== 200) return json(502, { error: t.scrub(`search ${r.status}: ${r.body.toString().slice(0, 300)}`, key) });
        return json(200, { places: t.shapePlaces(JSON.parse(r.body)) });
      }
      if (pathname === '/route') {
        const from = t.parseLatLon(params.get('from')), to = t.parseLatLon(params.get('to'));
        if (!from || !to) return json(400, { error: 'from and to must be lat,lon' });
        if (!use('route')) return json(429, { error: 'monthly free route allowance used up' });
        const r = await upstream(t.routeUrl(key, from, to));
        log('route', r.status);
        if (r.status !== 200) return json(502, { error: t.scrub(`route ${r.status}: ${r.body.toString().slice(0, 300)}`, key) });
        return json(200, { routes: t.shapeRoutes(JSON.parse(r.body)) });
      }
      const tile = t.parseTile(pathname);
      if (tile) {
        if (!use('tile')) return json(429, { error: 'monthly free tile allowance used up' });
        const r = await upstream(t.tileUrl(key, tile));
        if (r.status !== 200) return json(r.status === 404 ? 404 : 502, { error: t.scrub(`tile ${r.status}`, key) });
        // per-client caching only (Portal terms 11.4): this browser may reuse a tile for a
        // minute, and no shared cache may keep it for anyone else
        return { status: 200, type: 'image/png', cache: 'private, max-age=60', body: r.body };
      }
      return json(404, { error: 'not found' });
    } catch (e) {
      log('error', t.scrub(e.message, key));
      return json(e.status || 502, { error: t.scrub(e.message, key) });
    }
  };
}

module.exports = { makeHandler };
