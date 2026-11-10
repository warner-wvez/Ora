// Pure logic for Ora's TomTom calls: no network, no state, unit-tested.
//
// Two servers use it, and each holds the key so the page never does: the relay
// (relay.wvez.org/tt, which the live site calls) and the local proxy in tools/tomtom-eval
// (this machine). The page sees Ora's own small shapes below and never TomTom's, so another
// provider could replace TomTom without touching the page.
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
  // traffic sections colour the line itself (slow and jammed stretches), and the important road
  // stretches name the roads that tell one route from another ("via I-5")
  p.append('sectionType', 'traffic');
  p.append('sectionType', 'importantRoadStretch');
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

// How bad a traffic section is, in the three steps the big apps colour a route line by:
// slow (orange), jam (red), closed (dark red). magnitudeOfDelay is 1 minor, 2 moderate,
// 3 major, 4 undefined (closures and other open-ended delays).
function trafficLevel(sec) {
  if (sec.simpleCategory === 'ROAD_CLOSURE' || sec.magnitudeOfDelay === 4) return 'closed';
  return sec.magnitudeOfDelay === 3 ? 'jam' : 'slow';
}
// The roads a route is known by, most important first: a road number where there is one
// ("I-5"), else the street name. Two are enough to tell routes apart.
function roadNames(sections) {
  const byIdx = new Map();
  for (const s of sections) {
    if (s.sectionType !== 'IMPORTANT_ROAD_STRETCH') continue;
    const name = (s.roadNumbers && s.roadNumbers[0] && s.roadNumbers[0].text) || (s.streetName && s.streetName.text);
    if (name && !byIdx.has(s.importantRoadStretchIndex)) byIdx.set(s.importantRoadStretchIndex, name);
  }
  return [...byIdx.entries()].sort((a, b) => a[0] - b[0]).map((e) => e[1])
    .filter((n, i, a) => a.indexOf(n) === i).slice(0, 2);
}
// A route is its time, its delay, its length, its line as [lon, lat] pairs for MapLibre, the
// slow stretches by point index, and the roads it goes by.
function shapeRoutes(json) {
  return ((json && json.routes) || []).map((r) => {
    const s = r.summary || {}, sections = r.sections || [];
    const coords = [];
    for (const leg of r.legs || []) for (const p of leg.points || []) coords.push([p.longitude, p.latitude]);
    return {
      seconds: s.travelTimeInSeconds || 0,
      delaySeconds: s.trafficDelayInSeconds || 0,
      noTrafficSeconds: s.noTrafficTravelTimeInSeconds || null,
      meters: s.lengthInMeters || 0,
      coords,
      traffic: sections.filter((x) => x.sectionType === 'TRAFFIC' && x.endPointIndex > x.startPointIndex)
        .map((x) => ({ from: x.startPointIndex, to: x.endPointIndex, level: trafficLevel(x) })),
      via: roadNames(sections),
    };
  });
}

// The key must never reach the page, including inside an upstream error message.
function scrub(text, key) { return key ? String(text).split(key).join('<key>') : String(text); }

// Only pages served from this machine may call the local proxy.
function originAllowed(origin) { return !origin || /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/.test(origin); }

// usage = { month: 'YYYY-MM', search, route, tile }; a new month starts the counts again.
// share is the part of each free allowance this server may spend: the relay takes less than
// all of it, so testing on this machine with the same key cannot push the month over.
function countUse(usage, kind, now = new Date(), share = 0.98) {
  const month = now.toISOString().slice(0, 7);
  const u = (usage && usage.month === month) ? { ...usage } : { month, search: 0, route: 0, tile: 0 };
  if (u[kind] >= Math.floor(FREE[kind] * share)) return { usage: u, allowed: false };
  u[kind] += 1;
  return { usage: u, allowed: true };
}

// The caller's address behind Traefik, which adds the address it was connected from as the
// last X-Forwarded-For entry; any earlier entry came from the caller and can say anything.
function clientIp(headers, remote) {
  const xff = String((headers && headers['x-forwarded-for']) || '').split(',').map((s) => s.trim()).filter(Boolean);
  return xff.length ? xff[xff.length - 1] : String(remote || '');
}

// Calls one address may make in an hour, so one visitor or one script cannot spend the
// month's free allowance for everyone. Planning a trip takes a few searches and a few routes;
// panning with traffic on takes a few hundred tiles an hour.
const PER_HOUR = { search: 60, route: 60, tile: 2000 };
const HOUR_MS = 3600 * 1000;
// buckets = Map("<ip>|<kind>" -> {start, n}); returns {ok, retryAfter} with retryAfter in seconds
function rateAllow(buckets, ip, kind, now = Date.now()) {
  const k = `${ip}|${kind}`, b = buckets.get(k);
  if (!b || now - b.start >= HOUR_MS) {
    if (buckets.size > 20000) for (const [key, v] of buckets) if (now - v.start >= HOUR_MS) buckets.delete(key);
    buckets.set(k, { start: now, n: 1 });
    return { ok: true, retryAfter: 0 };
  }
  if (b.n >= PER_HOUR[kind]) return { ok: false, retryAfter: Math.ceil((b.start + HOUR_MS - now) / 1000) };
  b.n += 1;
  return { ok: true, retryAfter: 0 };
}

module.exports = { FREE, PER_HOUR, parseLatLon, searchUrl, routeUrl, parseTile, tileUrl, shapePlaces, shapeRoutes, scrub, originAllowed, countUse, clientIp, rateAllow };
