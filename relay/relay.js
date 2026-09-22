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

function isPlaylist(file) {
  return file.endsWith('.m3u8');
}

function originAllowed(origin, allowed) {
  if (!origin) return true;                       // a plain <video src> or curl sends none
  return allowed.some((a) => (a.endsWith('*') ? origin.startsWith(a.slice(0, -1)) : origin === a));
}

module.exports = { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed, STATES };
