#!/usr/bin/env node
// The Florida stream relay. Node 20, no dependencies. See relay.js for the path shape.
//
//   PORT=8791 ALLOWED_ORIGINS=https://warner-wvez.github.io,http://localhost:* node server.js
//
// GET /healthz                              -> {ok, cameras cached, session age}
// GET /fl/<imageId>/<seN>/<chan>/<file>     -> the upstream file, token added, playlist rewritten
//
// How a token is minted, the same three steps fl511.com's own page performs, anonymously:
//   1. GET https://fl511.com/cctv once: a session cookie and an anti-forgery token.
//   2. GET https://fl511.com/Camera/GetVideoUrl?imageId=N with that cookie and header:
//      {token: <system guid>, sourceId, systemSourceId}.
//   3. POST that JSON to https://divas.cloud/VDS-API/SecureTokenUri/GetSecureTokenUriBySourceId:
//      "?token=<64 hex>". Tokens are per camera and were stable for hours in testing, so
//      each is cached and re-minted only when the stream answers 401.
// fl511 rate-limits step 2 (429 after a handful of quick calls), so minting is lazy and a
// 429 is passed back as 503 with Retry-After rather than retried in a loop.

const http = require('node:http');
const { Readable } = require('node:stream');
const { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed } = require('./relay');

const PORT = Number(process.env.PORT || 8791);
const ALLOWED = (process.env.ALLOWED_ORIGINS || 'https://warner-wvez.github.io,http://localhost:*').split(',').map((s) => s.trim()).filter(Boolean);
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const FL = 'https://fl511.com';
const TOKEN_API = 'https://divas.cloud/VDS-API/SecureTokenUri/GetSecureTokenUriBySourceId';
const SESSION_MAX_AGE_MS = 6 * 3600 * 1000;
const TOKEN_MAX_AGE_MS = 12 * 3600 * 1000;
const UPSTREAM_TIMEOUT_MS = 15000;

const session = { cookie: '', antiForgery: '', at: 0, refreshing: null };
const tokens = new Map();          // imageId -> {token, at}
const inflight = new Map();        // imageId -> Promise<string>
let rateLimitedUntil = 0;

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

async function mintToken(imageId) {
  if (Date.now() < rateLimitedUntil) { const e = new Error('rate limited'); e.status = 503; e.retryAfter = Math.ceil((rateLimitedUntil - Date.now()) / 1000); throw e; }
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
  if (r.status === 429) { rateLimitedUntil = Date.now() + 15000; const e = new Error('fl511 rate limit'); e.status = 503; e.retryAfter = 15; throw e; }
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
  tokens.set(imageId, { token: m[1], at: Date.now() });
  return m[1];
}

function tokenFor(imageId, force) {
  const c = tokens.get(imageId);
  if (!force && c && Date.now() - c.at < TOKEN_MAX_AGE_MS) return Promise.resolve(c.token);
  if (inflight.has(imageId)) return inflight.get(imageId);
  const p = mintToken(imageId).finally(() => inflight.delete(imageId));
  inflight.set(imageId, p);
  return p;
}

function cors(res, origin) {
  res.setHeader('Access-Control-Allow-Origin', origin || '*');
  res.setHeader('Access-Control-Allow-Headers', 'Range');
  res.setHeader('Access-Control-Expose-Headers', 'Content-Length, Content-Range');
  res.setHeader('Vary', 'Origin');
}

async function fetchUpstream(p, token) {
  return fetch(upstreamUrl(p, token), {
    headers: { 'User-Agent': UA, 'Referer': `${FL}/`, 'Origin': FL },
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });
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
  const p = parsePath(url.pathname);
  if (!p) { res.writeHead(404); return res.end('not found'); }
  if (req.method !== 'GET' && req.method !== 'HEAD') { res.writeHead(405); return res.end(); }

  let token = await tokenFor(p.imageId);
  let up = await fetchUpstream(p, token);
  if (up.status === 401) {                                  // token rotated upstream: mint once more
    token = await tokenFor(p.imageId, true);
    up = await fetchUpstream(p, token);
  }
  if (!up.ok) { res.writeHead(up.status === 404 ? 404 : 502, { 'Cache-Control': 'no-store' }); return res.end(`upstream ${up.status}`); }

  if (isPlaylist(p.file)) {
    const text = rewritePlaylist(await up.text(), p);
    res.writeHead(200, { 'Content-Type': 'application/vnd.apple.mpegurl', 'Cache-Control': 'no-store' });
    return res.end(req.method === 'HEAD' ? undefined : text);
  }
  const headers = { 'Content-Type': up.headers.get('content-type') || 'video/mp4', 'Cache-Control': 'public, max-age=30' };
  const len = up.headers.get('content-length'); if (len) headers['Content-Length'] = len;
  res.writeHead(200, headers);
  if (req.method === 'HEAD' || !up.body) return res.end();
  Readable.fromWeb(up.body).on('error', () => res.destroy()).pipe(res);
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
