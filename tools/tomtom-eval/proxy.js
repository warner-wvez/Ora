// Local TomTom evaluation proxy. Node 20+, no dependencies. See tomtom.js for why it exists.
//
//   node tools/tomtom-eval/proxy.js        # listens on http://127.0.0.1:8792
//
// The key is read from ~/.config/ora/tomtom.key (or the file named by TOMTOM_KEY_FILE) at
// start, never from the page and never printed. Usage counts per month go to
// ~/.config/ora/tomtom-usage.json so the free allowance is visible at a glance.
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const t = require('./tomtom');

const PORT = +process.env.PORT || 8792;
const DIR = path.join(os.homedir(), '.config', 'ora');
const KEY_FILE = process.env.TOMTOM_KEY_FILE || path.join(DIR, 'tomtom.key');
const USAGE_FILE = path.join(DIR, 'tomtom-usage.json');

let key = '';
try { key = fs.readFileSync(KEY_FILE, 'utf8').trim(); } catch (e) {}
let usage = null;
try { usage = JSON.parse(fs.readFileSync(USAGE_FILE, 'utf8')); } catch (e) {}

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
function use(kind) {
  const r = t.countUse(usage, kind);
  usage = r.usage;
  try { fs.mkdirSync(DIR, { recursive: true }); fs.writeFileSync(USAGE_FILE, JSON.stringify(usage)); } catch (e) {}
  return r.allowed;
}
function send(res, status, body, type = 'application/json') {
  res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store' });
  res.end(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body));
}
// TomTom's place search now and then takes 20 s or more to answer; past 10 s the page is
// better told so than left waiting
async function upstream(url) {
  let r;
  try { r = await fetch(url, { headers: { accept: '*/*' }, signal: AbortSignal.timeout(10000) }); }
  catch (e) { if (e.name === 'TimeoutError') { const err = new Error('TomTom did not answer within 10 s'); err.status = 504; throw err; } throw e; }
  return { status: r.status, type: r.headers.get('content-type') || '', body: Buffer.from(await r.arrayBuffer()) };
}

const server = http.createServer(async (req, res) => {
  const origin = req.headers.origin;
  if (!t.originAllowed(origin)) return send(res, 403, { error: 'origin not allowed' });
  if (origin) { res.setHeader('Access-Control-Allow-Origin', origin); res.setHeader('Vary', 'Origin'); }
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  if (req.method !== 'GET') return send(res, 405, { error: 'GET only' });
  const url = new URL(req.url, 'http://127.0.0.1');

  if (url.pathname === '/healthz') return send(res, 200, { ok: !!key, key: !!key, usage, free: t.FREE });
  if (!key) return send(res, 503, { error: `no TomTom key in ${KEY_FILE}` });

  try {
    if (url.pathname === '/search') {
      const q = (url.searchParams.get('q') || '').trim().slice(0, 120);
      if (q.length < 3) return send(res, 400, { error: 'query too short' });
      if (!use('search')) return send(res, 429, { error: 'monthly free search allowance used up' });
      const r = await upstream(t.searchUrl(key, q, t.parseLatLon(url.searchParams.get('near'))));
      log('search', r.status, JSON.stringify(q));
      if (r.status !== 200) return send(res, 502, { error: t.scrub(`search ${r.status}: ${r.body.toString().slice(0, 300)}`, key) });
      return send(res, 200, { places: t.shapePlaces(JSON.parse(r.body)) });
    }
    if (url.pathname === '/route') {
      const from = t.parseLatLon(url.searchParams.get('from')), to = t.parseLatLon(url.searchParams.get('to'));
      if (!from || !to) return send(res, 400, { error: 'from and to must be lat,lon' });
      if (!use('route')) return send(res, 429, { error: 'monthly free route allowance used up' });
      const r = await upstream(t.routeUrl(key, from, to));
      log('route', r.status, `${from.lat},${from.lon} -> ${to.lat},${to.lon}`);
      if (r.status !== 200) return send(res, 502, { error: t.scrub(`route ${r.status}: ${r.body.toString().slice(0, 300)}`, key) });
      return send(res, 200, { routes: t.shapeRoutes(JSON.parse(r.body)) });
    }
    const tile = t.parseTile(url.pathname);
    if (tile) {
      if (!use('tile')) return send(res, 429, { error: 'monthly free tile allowance used up' });
      const r = await upstream(t.tileUrl(key, tile));
      if (r.status !== 200) return send(res, r.status === 404 ? 404 : 502, { error: t.scrub(`tile ${r.status}`, key) });
      // per-client caching only (Portal terms 11.4): this browser may reuse a tile for a minute
      res.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'private, max-age=60' });
      return res.end(r.body);
    }
    return send(res, 404, { error: 'not found' });
  } catch (e) {
    log('error', t.scrub(e.message, key));
    return send(res, e.status || 502, { error: t.scrub(e.message, key) });
  }
});

server.listen(PORT, '127.0.0.1', () => log(`tomtom eval proxy on http://127.0.0.1:${PORT}, key ${key ? 'loaded' : 'MISSING: ' + KEY_FILE}`));
