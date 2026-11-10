// Local TomTom proxy, for trying the route preview on this machine. Node 20+, no dependencies.
// The live site goes through the relay instead (relay/server.js, /tt); both share
// relay/tomtom-serve.js, so the two answer the same way.
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
const t = require('../../relay/tomtom');
const { makeHandler } = require('../../relay/tomtom-serve');

const PORT = +process.env.PORT || 8792;
const DIR = path.join(os.homedir(), '.config', 'ora');
const KEY_FILE = process.env.TOMTOM_KEY_FILE || path.join(DIR, 'tomtom.key');
const USAGE_FILE = path.join(DIR, 'tomtom-usage.json');
// the relay spends up to 90% of each free allowance on the same key, so this machine keeps to
// the other 10% and the two together never pass the free month
const SHARE = Number(process.env.TOMTOM_SHARE || 0.1);

let key = '';
try { key = fs.readFileSync(KEY_FILE, 'utf8').trim(); } catch (e) {}
let usage = null;
try { usage = JSON.parse(fs.readFileSync(USAGE_FILE, 'utf8')); } catch (e) {}

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
function use(kind) {
  const r = t.countUse(usage, kind, new Date(), SHARE);
  usage = r.usage;
  try { fs.mkdirSync(DIR, { recursive: true }); fs.writeFileSync(USAGE_FILE, JSON.stringify(usage)); } catch (e) {}
  return r.allowed;
}
const handle = makeHandler({ key, use, log });
function send(res, r) {
  res.writeHead(r.status, { 'Content-Type': r.type, 'Cache-Control': r.cache });
  res.end(r.body);
}

const server = http.createServer(async (req, res) => {
  const origin = req.headers.origin;
  if (!t.originAllowed(origin)) return send(res, { status: 403, type: 'application/json', cache: 'no-store', body: '{"error":"origin not allowed"}' });
  if (origin) { res.setHeader('Access-Control-Allow-Origin', origin); res.setHeader('Vary', 'Origin'); }
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  if (req.method !== 'GET') return send(res, { status: 405, type: 'application/json', cache: 'no-store', body: '{"error":"GET only"}' });
  const url = new URL(req.url, 'http://127.0.0.1');
  if (url.pathname === '/healthz') {
    return send(res, { status: 200, type: 'application/json', cache: 'no-store', body: JSON.stringify({ ok: !!key, key: !!key, usage, free: t.FREE }) });
  }
  if (!key) return send(res, { status: 503, type: 'application/json', cache: 'no-store', body: JSON.stringify({ error: `no TomTom key in ${KEY_FILE}` }) });
  return send(res, await handle(url.pathname, url.searchParams));
});

server.listen(PORT, '127.0.0.1', () => log(`tomtom proxy on http://127.0.0.1:${PORT}, key ${key ? 'loaded' : 'MISSING: ' + KEY_FILE}`));
