// Pure logic for the Florida stream relay: no network, no state, fully unit-tested.
//
// Since September 2026 Florida's stream host (divas.cloud) answers only requests that
// carry fl511.com's own Referer plus a per-camera token minted through fl511.com. A
// browser page on any other origin cannot send that Referer, so the map asks this relay
// instead: the relay fetches upstream wearing fl511's headers and passes the bytes on.
//
// Relay path:   /fl/<imageId>/<seN>/<chan>/<file>
// Upstream URL: https://dis-<seN>.divas.cloud:8200/<chan>/<file>?token=<token>
//
// <imageId> is fl511's camera id (the number in https://fl511.com/map/Cctv/<imageId>),
// which is what fl511's own token endpoint takes. <seN> names one of the 26 regional
// stream hosts; <chan> is the channel folder, e.g. chan-3936_h.

const PATH = /^\/fl\/(\d{1,7})\/(se\d{1,3})\/(chan-[A-Za-z0-9_]{1,40})\/([A-Za-z0-9_.-]{1,80})$/;

function parsePath(pathname) {
  const m = PATH.exec(pathname);
  if (!m) return null;
  const [, imageId, host, chan, file] = m;
  if (file.includes('..')) return null;
  return { imageId, host, chan, file };
}

function upstreamUrl({ host, chan, file }, token) {
  const q = token ? `?token=${token}` : '';
  return `https://dis-${host}.divas.cloud:8200/${chan}/${file}${q}`;
}

// Upstream playlists reference their segments with the token in the query string, and
// sometimes with the absolute host. Both must come back to the relay: the token is the
// relay's business, and every path stays under the same /fl/<imageId>/<seN>/<chan>/.
function rewritePlaylist(text, { imageId, host, chan }) {
  const prefix = `/fl/${imageId}/${host}/${chan}/`;
  const absolute = new RegExp(`https://dis-${host}\\.divas\\.cloud:8200/${chan}/`, 'g');
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

module.exports = { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed };
