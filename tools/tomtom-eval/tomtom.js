// Pure logic for the local TomTom evaluation proxy: no network, no state, unit-tested.
//
// This is for Warner's own testing of a route preview on his laptop, which TomTom's Portal
// terms call Evaluation Use. It never runs on the live site: the proxy listens on 127.0.0.1
// only, the page turns these features on only when it is itself served from localhost, and
// the branch that carries them is not merged to main. Production will use another provider,
// which is why the page sees Ora's own small shapes below and never TomTom's.
//
// Three upstream calls, nothing else:
//   place search   https://api.tomtom.com/search/2/search/<q>.json
//   routes         https://api.tomtom.com/routing/1/calculateRoute/<from>:<to>/json
//   traffic tiles  https://api.tomtom.com/traffic/map/4/tile/flow/relative0/<z>/<x>/<y>.png
// No guidance or turn instructions are ever requested: a route here is a preview, not
// "Navigation Functionality" (live turn-by-turn from the user's position), which the terms
// exclude.

const API = 'https://api.tomtom.com';

// Free monthly allowances on the pay-as-you-grow plan (developer pricing page, 2026-10-21).
// TomTom blocks at the limit rather than billing; the proxy stops a little earlier so the
// page can say why instead of showing a bare error.
const FREE = { search: 2500, route: 20000, tile: 200000 };

const LATLON = /^(-?\d{1,2}(?:\.\d{1,7})?),(-?\d{1,3}(?:\.\d{1,7})?)$/;
function parseLatLon(s) {
  const m = LATLON.exec(String(s || ''));
  if (!m) return null;
  const lat = +m[1], lon = +m[2];
  return (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) ? { lat, lon } : null;
}

function searchUrl(key, q, near) {
  const p = new URLSearchParams({ key, typeahead: 'true', limit: '6', countrySet: 'US' });
  if (near) { p.set('lat', String(near.lat)); p.set('lon', String(near.lon)); }
  return `${API}/search/2/search/${encodeURIComponent(q)}.json?${p}`;
}

function routeUrl(key, from, to) {
  const p = new URLSearchParams({
    key, traffic: 'true', maxAlternatives: '2', routeRepresentation: 'polyline',
    computeTravelTimeFor: 'all', travelMode: 'car', departAt: 'now',
  });
  return `${API}/routing/1/calculateRoute/${from.lat},${from.lon}:${to.lat},${to.lon}/json?${p}`;
}

const TILE = /^\/traffic\/(\d{1,2})\/(\d{1,7})\/(\d{1,7})\.png$/;
function parseTile(pathname) {
  const m = TILE.exec(pathname);
  if (!m) return null;
  const z = +m[1], x = +m[2], y = +m[3], n = 2 ** z;
  return (z <= 22 && x < n && y < n) ? { z, x, y } : null;
}
function tileUrl(key, { z, x, y }) {
  return `${API}/traffic/map/4/tile/flow/relative0/${z}/${x}/${y}.png?key=${encodeURIComponent(key)}&tileSize=256`;
}

// A place is what the search box needs and nothing more: a name, the line under it, and where.
// POIs carry a business name; addresses and areas use the address line as the name.
function shapePlaces(json) {
  return ((json && json.results) || []).filter((r) => r.position).map((r) => {
    const addr = (r.address && r.address.freeformAddress) || '';
    const name = (r.poi && r.poi.name) || addr || (r.address && r.address.municipality) || 'Unnamed place';
    const vp = r.viewport;
    return {
      name,
      address: name === addr ? [r.address && r.address.municipality, r.address && r.address.countrySubdivision].filter(Boolean).join(', ') : addr,
      type: r.type || '',
      lat: r.position.lat, lon: r.position.lon,
      bbox: vp ? [vp.topLeftPoint.lon, vp.btmRightPoint.lat, vp.btmRightPoint.lon, vp.topLeftPoint.lat] : null,
    };
  });
}

// A route is its time, its delay, its length and its line as [lon, lat] pairs for MapLibre.
function shapeRoutes(json) {
  return ((json && json.routes) || []).map((r) => {
    const s = r.summary || {};
    const coords = [];
    for (const leg of r.legs || []) for (const p of leg.points || []) coords.push([p.longitude, p.latitude]);
    return {
      seconds: s.travelTimeInSeconds || 0,
      delaySeconds: s.trafficDelayInSeconds || 0,
      noTrafficSeconds: s.noTrafficTravelTimeInSeconds || null,
      meters: s.lengthInMeters || 0,
      coords,
    };
  });
}

// The key must never reach the page, including inside an upstream error message.
function scrub(text, key) { return key ? String(text).split(key).join('<key>') : String(text); }

// Only pages served from this machine may call the proxy.
function originAllowed(origin) { return !origin || /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/.test(origin); }

// usage = { month: 'YYYY-MM', search, route, tile }; a new month starts the counts again
function countUse(usage, kind, now = new Date()) {
  const month = now.toISOString().slice(0, 7);
  const u = (usage && usage.month === month) ? { ...usage } : { month, search: 0, route: 0, tile: 0 };
  if (u[kind] >= Math.floor(FREE[kind] * 0.98)) return { usage: u, allowed: false };
  u[kind] += 1;
  return { usage: u, allowed: true };
}

module.exports = { FREE, parseLatLon, searchUrl, routeUrl, parseTile, tileUrl, shapePlaces, shapeRoutes, scrub, originAllowed, countUse };
