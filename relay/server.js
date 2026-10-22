#!/usr/bin/env node
// The stream relay. Node 20, no dependencies. See relay.js for the path shape.
//
//   PORT=8791 ALLOWED_ORIGINS=https://warner-wvez.github.io,http://localhost:* node server.js
//
// GET /healthz                                      -> {ok, cameras cached, session age}
// GET /<state>/<imageId>/<seN>/<chan>/<file>        -> the upstream file, token added, playlist rewritten
// GET /nj/<w|t>/<upstream path>                     -> the upstream file, 511nj.org's headers added
//
// Three states, one shape. Each locks the stream behind a per-camera token minted through
// the agency's site, and all are on the same vendor platform, so the token dance is the same
// two calls. Florida needs a session in front of them; Pennsylvania and North Carolina do not.
//
// Florida, the same steps fl511.com's own page performs, anonymously:
//   1. GET https://fl511.com/cctv once: a session cookie and an anti-forgery token.
//   2. GET https://fl511.com/Camera/GetVideoUrl?imageId=N with that cookie and header:
//      {token: <system guid>, sourceId, systemSourceId}.
//   3. POST that JSON to https://divas.cloud/VDS-API/SecureTokenUri/GetSecureTokenUriBySourceId:
//      "?token=<64 hex>".
//
// Pennsylvania, traced 2026-09-22, and simpler: no cookie and no anti-forgery token at all.
//   1. GET https://www.511pa.com/Camera/GetVideoUrl?imageId=N, plain: the same JSON shape.
//   2. POST it to https://pa.arcadis-ivds.com/api/SecureTokenUri/GetSecureTokenUriBySourceId.
// Note the different host and path from Florida's, and that PennDOT's sourceId is a name
// ("mp10-5e-fortcherryroad"), not a number, so the JSON is passed through untouched.
//
// North Carolina, traced 2026-10-20, is Pennsylvania's two calls on its own hosts:
//   1. GET https://www.drivenc.gov/Camera/GetVideoUrl?imageId=N, plain.
//   2. POST it to https://vds.nc.insight-atms.com/api/SecureTokenUri/GetSecureTokenUriBySourceId,
//      which answers CORS only to www.drivenc.gov. That is why a browser cannot mint it.
// Its stream hosts (cf?seNN.services.ncdot.gov:8887) do not check the Referer at all, so
// the token is the whole lock; the relay sends drivenc's Referer anyway, like a browser would.
//
// Tokens are per camera and were stable across repeated mints in testing, so each is cached
// and re-minted only when the stream answers 401. Neither token is IP-bound: one minted on a
// laptop plays from the VPS. Both sites rate-limit step 2 with a 429 after a handful of quick
// calls, so minting is lazy and a 429 is passed back as 503 with Retry-After, never retried
// in a loop. Never warm a whole state.

const http = require('node:http');
const { Readable } = require('node:stream');
const { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed, PASS, parsePassPath, passUrl, rewritePassPlaylist } = require('./relay');

const PORT = Number(process.env.PORT || 8791);
const ALLOWED = (process.env.ALLOWED_ORIGINS || 'https://warner-wvez.github.io,http://localhost:*').split(',').map((s) => s.trim()).filter(Boolean);
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const FL = 'https://fl511.com';
const PA = 'https://www.511pa.com';
const TOKEN_API = 'https://divas.cloud/VDS-API/SecureTokenUri/GetSecureTokenUriBySourceId';
const PA_TOKEN_API = 'https://pa.arcadis-ivds.com/api/SecureTokenUri/GetSecureTokenUriBySourceId';
const NC = 'https://www.drivenc.gov';
const NC_TOKEN_API = 'https://vds.nc.insight-atms.com/api/SecureTokenUri/GetSecureTokenUriBySourceId';
// The site whose Referer each state's stream host demands. Sending the wrong one is a 401,
// so fl511's Referer does not open a Pennsylvania stream and the reverse is also true.
const SITE = { fl: FL, pa: PA, nc: NC };
const SESSION_MAX_AGE_MS = 6 * 3600 * 1000;
const TOKEN_MAX_AGE_MS = 12 * 3600 * 1000;
const UPSTREAM_TIMEOUT_MS = 15000;

const session = { cookie: '', antiForgery: '', at: 0, refreshing: null };
const tokens = new Map();          // "<state>:<imageId>" -> {token, at}
const inflight = new Map();        // "<state>:<imageId>" -> Promise<string>
const rateLimited = { fl: 0, pa: 0, nc: 0 };   // per state: one agency's 429 must not stall another
function rateGuard(state) {
  const until = rateLimited[state];
  if (Date.now() >= until) return;
  const e = new Error('rate limited'); e.status = 503; e.retryAfter = Math.ceil((until - Date.now()) / 1000); throw e;
}

function log(...a) { console.log(new Date().toISOString(), ...a); }

async function refreshSession() {
  if (session.refreshing) return session.refreshing;
  session.refreshing = (async () => {
    const r = await fetch(`${FL}/cctv`, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS) });
    const html = await r.text();
    const cookies = (r.headers.getSetCookie ? r.headers.getSetCookie() : []).map((c) => c.split(';')[0]);
    const m = /name="__RequestVerificationToken"[^>]*value="([^"]+)"/.exec(html) || /value="([^"]+)"[^>]*name="__RequestVerificationToken"/.exec(html);
    if (!r.ok || !m || !cookies.length) throw new Error(`fl511 session failed: status ${r.status}, cookies ${cookies.length}, token ${m ? 'found' : 'missing'}`);
    session.cookie = cookies.join('; ');
    session.antiForgery = m[1];
    session.at = Date.now();
    log('fl511 session refreshed');
  })().finally(() => { session.refreshing = null; });
  return session.refreshing;
}

// Pennsylvania's and North Carolina's token, the same two calls their own camera pages make
// and nothing else: no session to warm, no cookie, no anti-forgery header.
const PLAIN = { pa: { site: PA, api: PA_TOKEN_API }, nc: { site: NC, api: NC_TOKEN_API } };
async function mintTokenPlain(state, imageId) {
  rateGuard(state);
  const { site, api } = PLAIN[state];
  const r = await fetch(`${site}/Camera/GetVideoUrl?imageId=${imageId}`, {
    headers: { 'User-Agent': UA, 'X-Requested-With': 'XMLHttpRequest', 'Referer': `${site}/cctv` },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });
  if (r.status === 429) { rateLimited[state] = Date.now() + 15000; const e = new Error(`${state} rate limit`); e.status = 503; e.retryAfter = 15; throw e; }
  if (!r.ok) { const e = new Error(`${state} GetVideoUrl ${r.status}`); e.status = 502; throw e; }
  // a camera with no video answers 200 with an empty body, which JSON.parse would throw on
  const body = (await r.text()).trim();
  if (!body || body[0] !== '{') { const e = new Error('camera has no video source'); e.status = 404; throw e; }
  const src = JSON.parse(body);
  if (!src || !src.sourceId) { const e = new Error('camera has no video source'); e.status = 404; throw e; }
  const t = await fetch(api, {
    method: 'POST', body: JSON.stringify(src),
    headers: { 'User-Agent': UA, 'Content-Type': 'application/json', 'Origin': site, 'Referer': `${site}/` },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });
  if (!t.ok) { const e = new Error(`${state} token api ${t.status}`); e.status = 502; throw e; }
  const m = /token=([A-Fa-f0-9]+)/.exec(String(await t.json()));
  if (!m) { const e = new Error('token api returned no token'); e.status = 502; throw e; }
  return m[1];
}

async function mintToken(imageId) {
  rateGuard('fl');
  if (!session.at || Date.now() - session.at > SESSION_MAX_AGE_MS) await refreshSession();
  let r = await fetch(`${FL}/Camera/GetVideoUrl?imageId=${imageId}`, {
    headers: { 'User-Agent': UA, 'Cookie': session.cookie, '__RequestVerificationToken': session.antiForgery, 'X-Requested-With': 'XMLHttpRequest', 'Referer': `${FL}/cctv` },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });
  if (r.status === 401 || r.status === 403) {            // session expired server side: one refresh, one retry
    await refreshSession();
    r = await fetch(`${FL}/Camera/GetVideoUrl?imageId=${imageId}`, {
      headers: { 'User-Agent': UA, 'Cookie': session.cookie, '__RequestVerificationToken': session.antiForgery, 'X-Requested-With': 'XMLHttpRequest', 'Referer': `${FL}/cctv` },
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  }
  if (r.status === 429) { rateLimited.fl = Date.now() + 15000; const e = new Error('fl511 rate limit'); e.status = 503; e.retryAfter = 15; throw e; }
  if (!r.ok) { const e = new Error(`fl511 GetVideoUrl ${r.status}`); e.status = 502; throw e; }
  const src = await r.json();
  if (!src || !src.sourceId) { const e = new Error('camera has no video source'); e.status = 404; throw e; }
  const t = await fetch(TOKEN_API, {
    method: 'POST', body: JSON.stringify(src),
    headers: { 'User-Agent': UA, 'Content-Type': 'application/json', 'Origin': FL, 'Referer': `${FL}/` },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });
  if (!t.ok) { const e = new Error(`divas token api ${t.status}`); e.status = 502; throw e; }
  const q = await t.json();                                // "?token=<hex>"
  const m = /token=([A-Fa-f0-9]+)/.exec(String(q));
  if (!m) { const e = new Error('token api returned no token'); e.status = 502; throw e; }
  return m[1];
}

const MINT = { fl: mintToken, pa: (id) => mintTokenPlain('pa', id), nc: (id) => mintTokenPlain('nc', id) };
// cached per state as well as per camera: the same imageId means a different camera in
// each state, and one state's token never opens another's stream
function tokenFor(state, imageId, force) {
  const key = `${state}:${imageId}`;
  const c = tokens.get(key);
  if (!force && c && Date.now() - c.at < TOKEN_MAX_AGE_MS) return Promise.resolve(c.token);
  if (inflight.has(key)) return inflight.get(key);
  const p = MINT[state](imageId)
    .then((tok) => { tokens.set(key, { token: tok, at: Date.now() }); return tok; })
    .finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

function cors(res, origin) {
  res.setHeader('Access-Control-Allow-Origin', origin || '*');
  res.setHeader('Access-Control-Allow-Headers', 'Range');
  res.setHeader('Access-Control-Expose-Headers', 'Content-Length, Content-Range');
  res.setHeader('Vary', 'Origin');
}

async function fetchUpstream(p, token) {
  const site = SITE[p.state];
  return fetch(upstreamUrl(p, token), {
    headers: { 'User-Agent': UA, 'Referer': `${site}/`, 'Origin': site },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });
}

// New Jersey: no token, only the headers a page on 511nj.org would send. See relay.js.
async function fetchPass(p) {
  const site = PASS[p.state].site;
  return fetch(passUrl(p), {
    headers: { 'User-Agent': UA, 'Referer': `${site}/`, 'Origin': site },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });
}

// Playlists are rewritten and never cached; segments stream through and may be cached briefly,
// unless the host reuses segment names (the NJ Turnpike cycles nj0.ts to nj4.ts every ten
// seconds, so a cached segment would replay old video).
async function sendUpstream(req, res, up, file, rewrite, segmentCache = 'public, max-age=30') {
  if (!up.ok) { res.writeHead(up.status === 404 ? 404 : 502, { 'Cache-Control': 'no-store' }); return res.end(`upstream ${up.status}`); }
  if (isPlaylist(file)) {
    const text = rewrite(await up.text());
    res.writeHead(200, { 'Content-Type': 'application/vnd.apple.mpegurl', 'Cache-Control': 'no-store' });
    return res.end(req.method === 'HEAD' ? undefined : text);
  }
  const headers = { 'Content-Type': up.headers.get('content-type') || 'video/mp4', 'Cache-Control': segmentCache };
  const len = up.headers.get('content-length'); if (len) headers['Content-Length'] = len;
  res.writeHead(200, headers);
  if (req.method === 'HEAD' || !up.body) return res.end();
  Readable.fromWeb(up.body).on('error', () => res.destroy()).pipe(res);
}

async function serve(req, res) {
  const url = new URL(req.url, 'http://relay');
  const origin = req.headers.origin;
  if (!originAllowed(origin, ALLOWED)) { res.writeHead(403); return res.end('origin not allowed'); }
  cors(res, origin);
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  if (url.pathname === '/healthz') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ ok: true, cameras: tokens.size, sessionAgeMin: session.at ? Math.round((Date.now() - session.at) / 60000) : null }));
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') { res.writeHead(405); return res.end(); }
  const pass = parsePassPath(url.pathname);
  if (pass) return sendUpstream(req, res, await fetchPass(pass), pass.file, (t) => rewritePassPlaylist(t, pass), 'no-store');
  const p = parsePath(url.pathname);
  if (!p) { res.writeHead(404); return res.end('not found'); }

  let token = await tokenFor(p.state, p.imageId);
  let up = await fetchUpstream(p, token);
  if (up.status === 401) {                                  // token rotated upstream: mint once more
    token = await tokenFor(p.state, p.imageId, true);
    up = await fetchUpstream(p, token);
  }
  return sendUpstream(req, res, up, p.file, (t) => rewritePlaylist(t, p));
}

const server = http.createServer((req, res) => {
  serve(req, res).catch((e) => {
    const status = e.status || (e.name === 'TimeoutError' ? 504 : 502);
    log(`${req.method} ${req.url} -> ${status} ${e.message}`);
    if (res.headersSent) return res.destroy();
    const h = { 'Cache-Control': 'no-store' }; if (e.retryAfter) h['Retry-After'] = String(e.retryAfter);
    res.writeHead(status, h); res.end(e.message);
  });
});
server.keepAliveTimeout = 65000;
server.listen(PORT, () => log(`ora relay listening on ${PORT}, allowed origins: ${ALLOWED.join(' ')}`));
