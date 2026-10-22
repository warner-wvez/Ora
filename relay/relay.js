// Pure logic for the stream relay: no network, no state, fully unit-tested.
//
// Since September 2026 some 511 sites' stream hosts answer only requests that carry the
// agency's own Referer plus a per-camera token minted through the agency's site. A browser
// page on any other origin cannot send that Referer, so the map asks this relay instead:
// the relay fetches upstream wearing the agency's headers and passes the bytes on.
//
// Relay path:   /<state>/<imageId>/<seN>/<chan>/<file>
// Upstream URL: https://<host built from seN>/<chan>/<file>?token=<token>
//
// <imageId> is the agency's camera id (the number in .../map/Cctv/<imageId>), which is what
// its own token endpoint takes. <seN> names one of the regional stream hosts; <chan> is the
// channel folder, e.g. chan-3936_h.
//
// A state belongs here only once a browser genuinely cannot reproduce its lock. Texas looked
// like Florida and was not: a query-string token and nothing else, so it plays direct and has
// no entry below. See docs/6-decisions/0014-texas-signs-its-own-streams.md.

// Each state maps its short host name to the real upstream origin. Adding a state is a line
// here plus a mintToken in server.js.
const STATES = {
  fl: { short: /^se\d{1,3}$/, origin: (h) => `https://dis-${h}.divas.cloud:8200` },
  pa: { short: /^se\d{1,2}$/, origin: (h) => `https://pa-${h}.arcadis-ivds.com:8200` },
  // North Carolina's hosts are named by region and site, e.g. cfmse01, cfese04, cftse12
  nc: { short: /^cf[a-z]se\d{1,2}$/, origin: (h) => `https://${h}.services.ncdot.gov:8887` },
};

const PATH = /^\/([a-z]{2})\/(\d{1,7})\/([a-z0-9-]{1,12})\/(chan-[A-Za-z0-9_]{1,40})\/([A-Za-z0-9_.-]{1,80})$/;

function parsePath(pathname) {
  const m = PATH.exec(pathname);
  if (!m) return null;
  const [, state, imageId, host, chan, file] = m;
  const cfg = STATES[state];
  if (!cfg || !cfg.short.test(host)) return null;
  if (file.includes('..')) return null;
  return { state, imageId, host, chan, file };
}

function upstreamUrl({ state, host, chan, file }, token) {
  const q = token ? `?token=${token}` : '';
  return `${STATES[state].origin(host)}/${chan}/${file}${q}`;
}

// Upstream playlists reference their segments with the token in the query string, and
// sometimes with the absolute host. Both must come back to the relay: the token is the
// relay's business, and every path stays under the same /<state>/<imageId>/<seN>/<chan>/.
function rewritePlaylist(text, { state, imageId, host, chan }) {
  const prefix = `/${state}/${imageId}/${host}/${chan}/`;
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const absolute = new RegExp(`${esc(STATES[state].origin(host))}/${chan}/`, 'g');
  return text
    .split('\n')
    .map((line) => {
      if (line.startsWith('#') || line.trim() === '') return line.replace(/URI="([^"]+)"/, (_, u) => `URI="${relayUri(u)}"`);
      return relayUri(line.trim());
    })
    .join('\n');

  function relayUri(u) {
    let out = u.replace(absolute, prefix);
    out = out.replace(/([?&])token=[A-Fa-f0-9]+&?/, (m, sep) => (m.endsWith('&') ? sep : ''));
    out = out.replace(/[?&]$/, '');
    return out;
  }
}

// New Jersey, traced 2026-10-22, needs no token at all: its two stream hosts serve anyone
// whose request says it came from 511nj.org, and answer CORS to 511nj.org alone. A page on
// another origin can do neither, so the relay says it instead. The path after the host key
// is the upstream path unchanged, which keeps every relative link in a playlist pointing
// back here. See docs/6-decisions/0016-new-jersey-through-the-relay.md.
//
// Relay path:   /nj/<w|t>/<upstream path>
// Upstream URL: https://nj-511.wink.co/<upstream path>, or the Turnpike's host for t
const PASS = {
  nj: {
    site: 'https://511nj.org',
    hosts: {
      w: { origin: 'https://nj-511.wink.co', path: /^hls\/public\/\d{1,3}\/[A-Za-z0-9_-]{1,40}\/[A-Za-z0-9_.-]{1,80}$/ },
      t: { origin: 'https://njtpk-wink.xcmdata.org', path: /^njta\/\d{1,4}\/(?:media\/)?public\/hls\/[A-Za-z0-9_.-]{1,80}$/ },
    },
  },
};

const PASS_PATH = /^\/([a-z]{2})\/([a-z])\/(.+)$/;

function parsePassPath(pathname) {
  const m = PASS_PATH.exec(pathname);
  if (!m) return null;
  const [, state, key, path] = m;
  const host = PASS[state] && PASS[state].hosts[key];
  if (!host || path.includes('..') || !host.path.test(path)) return null;
  return { state, key, path, file: path.slice(path.lastIndexOf('/') + 1) };
}

function passUrl({ state, key, path }) {
  return `${PASS[state].hosts[key].origin}/${path}`;
}

// wink.co serves low-latency HLS, a quarter-second part per request. A traffic camera gains
// nothing from that and the relay would carry eight times the requests, so the part tags go
// and the player falls back to plain two-second segments. An otp, should one ever be handed
// out again, is stripped like the other states' tokens.
const LOW_LATENCY = /^#EXT-X-(?:SERVER-CONTROL|PART-INF|PART|PRELOAD-HINT|RENDITION-REPORT|SKIP):/;

function rewritePassPlaylist(text, { state, key }) {
  const { origin } = PASS[state].hosts[key];
  const prefix = `/${state}/${key}/`;
  return text
    .split('\n')
    .filter((line) => !LOW_LATENCY.test(line))
    .map((line) => {
      if (line.startsWith('#') || line.trim() === '') return line.replace(/URI="([^"]+)"/, (_, u) => `URI="${relayUri(u)}"`);
      return relayUri(line.trim());
    })
    .join('\n');

  function relayUri(u) {
    let out = u.startsWith(`${origin}/`) ? prefix + u.slice(origin.length + 1) : u;
    out = out.replace(/([?&])otp=[0-9A-Za-z%]+&?/, (m, sep) => (m.endsWith('&') ? sep : ''));
    return out.replace(/[?&]$/, '');
  }
}

function isPlaylist(file) {
  return file.endsWith('.m3u8');
}

function originAllowed(origin, allowed) {
  if (!origin) return true;                       // a plain <video src> or curl sends none
  return allowed.some((a) => (a.endsWith('*') ? origin.startsWith(a.slice(0, -1)) : origin === a));
}

module.exports = { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed, STATES, PASS, parsePassPath, passUrl, rewritePassPlaylist };
