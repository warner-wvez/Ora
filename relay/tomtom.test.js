const test = require('node:test');
const assert = require('node:assert/strict');
const t = require('./tomtom');

test('parseLatLon reads lat,lon and refuses anything out of range or malformed', () => {
  assert.deepEqual(t.parseLatLon('47.6062,-122.3321'), { lat: 47.6062, lon: -122.3321 });
  assert.equal(t.parseLatLon('91,0'), null);
  assert.equal(t.parseLatLon('0,181'), null);
  assert.equal(t.parseLatLon('47.6;-122'), null);
  assert.equal(t.parseLatLon(''), null);
});

test('searchUrl biases to the map and keeps the search in the US', () => {
  const u = new URL(t.searchUrl('K', 'pike place', { lat: 47.6, lon: -122.3 }));
  assert.equal(u.pathname, '/search/2/search/pike%20place.json');
  assert.equal(u.searchParams.get('countrySet'), 'US');
  assert.equal(u.searchParams.get('lat'), '47.6');
  assert.equal(u.searchParams.get('typeahead'), 'true');
});

test('routeUrl asks for traffic and alternatives and never for turn instructions', () => {
  const u = new URL(t.routeUrl('K', { lat: 47.6, lon: -122.3 }, { lat: 45.5, lon: -122.7 }));
  assert.equal(u.pathname, '/routing/1/calculateRoute/47.6,-122.3:45.5,-122.7/json');
  assert.equal(u.searchParams.get('traffic'), 'true');
  assert.equal(u.searchParams.get('maxAlternatives'), '2');
  assert.equal(u.searchParams.get('instructionsType'), null);
  assert.deepEqual(u.searchParams.getAll('sectionType'), ['traffic', 'importantRoadStretch', 'toll']);
});

test('parseTile accepts real tile coordinates only', () => {
  assert.deepEqual(t.parseTile('/traffic/12/655/1430.png'), { z: 12, x: 655, y: 1430 });
  assert.equal(t.parseTile('/traffic/2/4/1.png'), null);           // x past the edge at z2
  assert.equal(t.parseTile('/traffic/12/655/1430.png/../x'), null);
  assert.match(t.tileUrl('K', { z: 12, x: 655, y: 1430 }), /\/flow\/relative0\/12\/655\/1430\.png\?key=K/);
});

test('shapePlaces names a POI by its name and an address by its address line', () => {
  const places = t.shapePlaces({ results: [
    { type: 'POI', poi: { name: 'Pike Place Market' }, address: { freeformAddress: '85 Pike St, Seattle, WA 98101', municipality: 'Seattle' },
      position: { lat: 47.609, lon: -122.341 }, viewport: { topLeftPoint: { lat: 47.61, lon: -122.343 }, btmRightPoint: { lat: 47.608, lon: -122.339 } } },
    { type: 'Point Address', address: { freeformAddress: '400 Broad St, Seattle, WA 98109', municipality: 'Seattle', countrySubdivision: 'WA' },
      position: { lat: 47.6205, lon: -122.3493 } },
    { type: 'POI', poi: { name: 'No position' } },
  ] });
  assert.equal(places.length, 2);
  assert.deepEqual(places[0], { name: 'Pike Place Market', address: '85 Pike St, Seattle, WA 98101', type: 'POI', lat: 47.609, lon: -122.341, dist: null, detour: null, bbox: [-122.343, 47.608, -122.339, 47.61] });
  assert.equal(places[1].name, '400 Broad St, Seattle, WA 98109');
  assert.equal(places[1].address, 'Seattle, WA');
});

test('shapeRoutes joins every leg into one [lon, lat] line with its time and delay', () => {
  const routes = t.shapeRoutes({ routes: [{
    summary: { travelTimeInSeconds: 1500, trafficDelayInSeconds: 360, noTrafficTravelTimeInSeconds: 1140, lengthInMeters: 29000 },
    legs: [{ points: [{ latitude: 47.6, longitude: -122.3 }, { latitude: 47.5, longitude: -122.31 }] }, { points: [{ latitude: 47.4, longitude: -122.32 }] }],
  }] });
  assert.deepEqual(routes, [{ seconds: 1500, delaySeconds: 360, noTrafficSeconds: 1140, historicSeconds: null, meters: 29000, departTime: null, arriveTime: null, coords: [[-122.3, 47.6], [-122.31, 47.5], [-122.32, 47.4]], legs: [{ seconds: 0, meters: 0, delaySeconds: 0, historicSeconds: null }, { seconds: 0, meters: 0, delaySeconds: 0, historicSeconds: null }], traffic: [], via: [], tolls: false }]);
});

test('shapeRoutes grades traffic sections and names the roads by importance', () => {
  const [r] = t.shapeRoutes({ routes: [{ summary: {}, legs: [], sections: [
    { sectionType: 'TRAFFIC', startPointIndex: 10, endPointIndex: 40, simpleCategory: 'JAM', magnitudeOfDelay: 1 },
    { sectionType: 'TRAFFIC', startPointIndex: 50, endPointIndex: 60, simpleCategory: 'JAM', magnitudeOfDelay: 3 },
    { sectionType: 'TRAFFIC', startPointIndex: 70, endPointIndex: 90, simpleCategory: 'ROAD_CLOSURE', magnitudeOfDelay: 4 },
    { sectionType: 'IMPORTANT_ROAD_STRETCH', importantRoadStretchIndex: 1, streetName: { text: 'Valley Fwy' }, roadNumbers: [{ text: 'WA-167' }] },
    { sectionType: 'IMPORTANT_ROAD_STRETCH', importantRoadStretchIndex: 0, roadNumbers: [{ text: 'I-405' }] },
    { sectionType: 'IMPORTANT_ROAD_STRETCH', importantRoadStretchIndex: 0, roadNumbers: [{ text: 'I-405' }] },
    { sectionType: 'IMPORTANT_ROAD_STRETCH', importantRoadStretchIndex: 2, streetName: { text: 'E D St' } },
  ] }] });
  assert.deepEqual(r.traffic, [{ from: 10, to: 40, level: 'slow', cat: 'JAM', delay: 0 }, { from: 50, to: 60, level: 'jam', cat: 'JAM', delay: 0 }, { from: 70, to: 90, level: 'closed', cat: 'ROAD_CLOSURE', delay: 0 }]);
  assert.deepEqual(r.via, ['I-405', 'WA-167']);
});

test('scrub removes the key from anything headed to the page', () => {
  assert.equal(t.scrub('bad request for key=SECRET123&q=x', 'SECRET123'), 'bad request for key=<key>&q=x');
});

test('originAllowed admits this machine only', () => {
  assert.ok(t.originAllowed('http://localhost:8934'));
  assert.ok(t.originAllowed('http://127.0.0.1:8934'));
  assert.ok(t.originAllowed(undefined));                       // curl on this machine
  assert.ok(!t.originAllowed('https://warner-wvez.github.io'));
  assert.ok(!t.originAllowed('http://localhost.evil.com'));
});

test('countUse counts per month and stops just short of the free allowance', () => {
  const oct = new Date('2026-10-21T12:00:00Z'), nov = new Date('2026-11-01T00:00:00Z');
  let r = t.countUse(null, 'route', oct);
  assert.deepEqual(r, { usage: { month: '2026-10', search: 0, route: 1, tile: 0 }, allowed: true });
  r = t.countUse({ month: '2026-10', search: 2450, route: 0, tile: 0 }, 'search', oct);
  assert.equal(r.allowed, false);
  r = t.countUse({ month: '2026-10', search: 2450, route: 0, tile: 0 }, 'search', nov);
  assert.deepEqual(r.usage, { month: '2026-11', search: 1, route: 0, tile: 0 });
});

test('countUse stops at a smaller share when the relay asks for one', () => {
  const now = new Date('2026-11-09T12:00:00Z');
  const cap = Math.floor(t.FREE.search * 0.9);
  assert.equal(t.countUse({ month: '2026-11', search: cap - 1, route: 0, tile: 0 }, 'search', now, 0.9).allowed, true);
  assert.equal(t.countUse({ month: '2026-11', search: cap, route: 0, tile: 0 }, 'search', now, 0.9).allowed, false);
});

test('clientIp takes the address Traefik added, not one the caller wrote', () => {
  assert.equal(t.clientIp({ 'x-forwarded-for': '6.6.6.6, 203.0.113.9' }, '10.0.1.5'), '203.0.113.9');
  assert.equal(t.clientIp({ 'x-forwarded-for': '203.0.113.9' }, '10.0.1.5'), '203.0.113.9');
  assert.equal(t.clientIp({}, '10.0.1.5'), '10.0.1.5');
});

test('rateAllow gives each address an hourly budget per kind of call', () => {
  const b = new Map(), now = 1_000_000;
  for (let i = 0; i < t.PER_HOUR.search; i++) assert.equal(t.rateAllow(b, '1.2.3.4', 'search', now).ok, true);
  const over = t.rateAllow(b, '1.2.3.4', 'search', now + 1000);
  assert.equal(over.ok, false);
  assert.equal(over.retryAfter, 3599);
  assert.equal(t.rateAllow(b, '1.2.3.4', 'route', now).ok, true);       // another kind
  assert.equal(t.rateAllow(b, '5.6.7.8', 'search', now).ok, true);      // another address
  assert.equal(t.rateAllow(b, '1.2.3.4', 'search', now + 3600 * 1000).ok, true);  // next hour
});

test('the shared handler never lets the key out, even in an upstream error', async () => {
  const { makeHandler } = require('./tomtom-serve');
  const KEY = 'SECRET-KEY-123';
  const real = global.fetch;
  global.fetch = async (url) => new Response(`bad request for ${url}`, { status: 400 });
  try {
    const handle = makeHandler({ key: KEY, use: () => true });
    for (const [p, q] of [['/search', 'q=pike+place'], ['/route', 'from=47.6,-122.3&to=47.2,-122.4'], ['/traffic/10/163/357.png', '']]) {
      const r = await handle(p, new URLSearchParams(q));
      assert.ok(r.status >= 400, p);
      assert.ok(!String(r.body).includes(KEY), `${p} leaked the key`);
    }
  } finally { global.fetch = real; }
});

test('the shared handler refuses to call TomTom once the month is used up', async () => {
  const { makeHandler } = require('./tomtom-serve');
  let called = 0;
  const real = global.fetch;
  global.fetch = async () => { called++; return new Response('{}'); };
  try {
    const r = await makeHandler({ key: 'K', use: () => false })('/search', new URLSearchParams('q=pike+place'));
    assert.equal(r.status, 429);
    assert.equal(called, 0);
  } finally { global.fetch = real; }
});

test('parseAvoid keeps only tolls and highways, once each', () => {
  assert.deepEqual(t.parseAvoid('tolls,highways'), ['tolls', 'highways']);
  assert.deepEqual(t.parseAvoid('highways,tolls,tolls,ferries,<x>'), ['highways', 'tolls']);
  assert.deepEqual(t.parseAvoid(''), []);
  assert.deepEqual(t.parseAvoid(null), []);
});

test('routeUrl passes avoid on to TomTom and asks where the tolls are', () => {
  const u = new URL(t.routeUrl('K', { lat: 47.6, lon: -122.3 }, { lat: 45.5, lon: -122.7 }, { avoid: ['tolls', 'highways'] }));
  assert.deepEqual(u.searchParams.getAll('avoid'), ['tollRoads', 'motorways']);
  assert.ok(u.searchParams.getAll('sectionType').includes('toll'));
  assert.ok(!u.searchParams.getAll('sectionType').includes('tollRoad'));   // deprecated by TomTom, withdrawal planned 2025-03-15
  const plain = new URL(t.routeUrl('K', { lat: 47.6, lon: -122.3 }, { lat: 45.5, lon: -122.7 }));
  assert.deepEqual(plain.searchParams.getAll('avoid'), []);
});

test('shapeRoutes marks a route that uses a toll road', () => {
  const route = (sections) => ({ routes: [{ summary: { travelTimeInSeconds: 60, lengthInMeters: 1000 }, legs: [{ points: [] }], sections }] });
  assert.equal(t.shapeRoutes(route([{ sectionType: 'TOLL', startPointIndex: 0, endPointIndex: 3 }]))[0].tolls, true);
  assert.equal(t.shapeRoutes(route([]))[0].tolls, false);
});

test('nearbyUrl searches one Find Nearby category around a point, US only', () => {
  const u = new URL(t.nearbyUrl('K', 'coffee', { lat: 47.6, lon: -122.3 }));
  assert.equal(u.pathname, '/search/2/nearbySearch/.json');
  assert.equal(u.searchParams.get('categorySet'), '9376002,9376006');
  assert.equal(u.searchParams.get('lat'), '47.6');
  assert.equal(u.searchParams.get('countrySet'), 'US');
  assert.equal(t.nearbyUrl('K', 'casino', { lat: 47.6, lon: -122.3 }), null);
  assert.deepEqual(Object.keys(t.NEARBY), ['gas', 'ev', 'food', 'coffee', 'rest', 'parking', 'grocery', 'pharmacy']);
});

test('shapePlaces carries the distance TomTom measured from the search point', () => {
  const p = t.shapePlaces({ results: [{ type: 'POI', poi: { name: 'Shell' }, address: { freeformAddress: '1 Main St' }, position: { lat: 1, lon: 2 }, dist: 812.4 }] });
  assert.equal(p[0].dist, 812);
  assert.equal(t.shapePlaces({ results: [{ position: { lat: 1, lon: 2 }, address: {} }] })[0].dist, null);
});

test('the shared handler answers Find Nearby and counts it as a search', async () => {
  const { makeHandler } = require('./tomtom-serve');
  const used = [];
  let asked = '';
  const real = global.fetch;
  global.fetch = async (url) => { asked = String(url); return new Response(JSON.stringify({ results: [{ poi: { name: 'Shell' }, address: { freeformAddress: '1 Main St' }, position: { lat: 1, lon: 2 }, dist: 100 }] })); };
  try {
    const handle = makeHandler({ key: 'K', use: (k) => { used.push(k); return true; } });
    const ok = await handle('/nearby', new URLSearchParams('cat=gas&near=47.6,-122.3'));
    assert.equal(ok.status, 200);
    assert.equal(JSON.parse(ok.body).places[0].name, 'Shell');
    assert.ok(asked.includes('categorySet=7311'));
    assert.deepEqual(used, ['search']);
    assert.equal((await handle('/nearby', new URLSearchParams('cat=casino&near=47.6,-122.3'))).status, 400);
    assert.equal((await handle('/nearby', new URLSearchParams('cat=gas'))).status, 400);
    assert.deepEqual(used, ['search']);   // refused before counting
  } finally { global.fetch = real; }
});

test('the shared handler passes avoid from the page to the route call', async () => {
  const { makeHandler } = require('./tomtom-serve');
  let asked = '';
  const real = global.fetch;
  global.fetch = async (url) => { asked = String(url); return new Response(JSON.stringify({ routes: [] })); };
  try {
    await makeHandler({ key: 'K', use: () => true })('/route', new URLSearchParams('from=47.6,-122.3&to=47.2,-122.4&avoid=tolls'));
    assert.ok(asked.includes('avoid=tollRoads'));
    assert.ok(!asked.includes('motorways'));
  } finally { global.fetch = real; }
});

test('parseVia reads up to three stops and refuses anything malformed', () => {
  assert.deepEqual(t.parseVia('40.7,-74.0;40.8,-74.1'), [{ lat: 40.7, lon: -74 }, { lat: 40.8, lon: -74.1 }]);
  assert.deepEqual(t.parseVia(''), []);
  assert.equal(t.parseVia('40.7,-74.0;bad'), null);
  assert.equal(t.parseVia('1,1;2,2;3,3;4,4'), null);
});

test('routeUrl routes through the stops, and Optimize asks TomTom for the best order once', () => {
  const a = { lat: 40.7, lon: -74 }, b = { lat: 40.8, lon: -74.1 }, c = { lat: 40.9, lon: -74.2 }, d = { lat: 41, lon: -74.3 };
  const u = new URL(t.routeUrl('K', a, d, { via: [b, c] }));
  assert.equal(u.pathname, '/routing/1/calculateRoute/40.7,-74:40.8,-74.1:40.9,-74.2:41,-74.3/json');
  assert.equal(u.searchParams.get('maxAlternatives'), '2');
  assert.equal(u.searchParams.get('computeBestOrder'), null);
  const o = new URL(t.routeUrl('K', a, d, { via: [b, c], optimize: true }));
  assert.equal(o.searchParams.get('computeBestOrder'), 'true');
  assert.equal(o.searchParams.get('maxAlternatives'), '0');      // TomTom refuses alternatives with computeBestOrder
  const one = new URL(t.routeUrl('K', a, d, { via: [b], optimize: true }));
  assert.equal(one.searchParams.get('computeBestOrder'), null);  // one stop has only one order
});

test('shapeRoutes keeps each leg, the usual time, and what each slow stretch is', () => {
  const routes = t.shapeRoutes({ routes: [{
    summary: { travelTimeInSeconds: 1800, trafficDelayInSeconds: 300, lengthInMeters: 20000, historicTrafficTravelTimeInSeconds: 1500 },
    legs: [{ summary: { travelTimeInSeconds: 600, lengthInMeters: 8000, trafficDelayInSeconds: 0, historicTrafficTravelTimeInSeconds: 580 }, points: [{ latitude: 1, longitude: 2 }] },
           { summary: { travelTimeInSeconds: 1200, lengthInMeters: 12000, trafficDelayInSeconds: 300 }, points: [{ latitude: 3, longitude: 4 }] }],
    sections: [{ sectionType: 'TRAFFIC', startPointIndex: 0, endPointIndex: 1, simpleCategory: 'ROAD_WORK', magnitudeOfDelay: 2, delayInSeconds: 240 }],
  }] });
  assert.equal(routes[0].historicSeconds, 1500);
  assert.deepEqual(routes[0].legs, [{ seconds: 600, meters: 8000, delaySeconds: 0, historicSeconds: 580 }, { seconds: 1200, meters: 12000, delaySeconds: 300, historicSeconds: null }]);
  assert.deepEqual(routes[0].traffic, [{ from: 0, to: 1, level: 'slow', cat: 'ROAD_WORK', delay: 240 }]);
});

test('shapeOrder turns TomTom optimizedWaypoints into the new stop order', () => {
  assert.deepEqual(t.shapeOrder({ optimizedWaypoints: [{ providedIndex: 0, optimizedIndex: 2 }, { providedIndex: 1, optimizedIndex: 0 }, { providedIndex: 2, optimizedIndex: 1 }] }), [1, 2, 0]);
  assert.equal(t.shapeOrder({}), null);
});

test('along-route search: URL, body, and a thinned route line from the page', () => {
  const u = new URL(t.alongUrl('K', 'gas'));
  assert.equal(u.pathname, '/search/2/searchAlongRoute/.json');      // no query text: it would filter by name
  assert.equal(u.searchParams.get('categorySet'), '7311');
  assert.equal(u.searchParams.get('maxDetourTime'), '900');
  assert.equal(u.searchParams.get('spreadingMode'), 'plan');
  assert.equal(t.alongUrl('K', 'casino'), null);
  assert.deepEqual(t.parseAlongPoints('{"points":[[40.7,-74],[40.8,-74.1]]}'), [{ lat: 40.7, lon: -74 }, { lat: 40.8, lon: -74.1 }]);
  assert.equal(t.parseAlongPoints('{"points":[[40.7,-74]]}'), null);            // TomTom needs at least 2
  assert.equal(t.parseAlongPoints('{"points":[[95,0],[1,1]]}'), null);
  assert.equal(t.parseAlongPoints('not json'), null);
  assert.equal(t.parseAlongPoints(JSON.stringify({ points: Array.from({ length: 301 }, (_, i) => [40, -74 + i / 1000]) })), null);
  assert.equal(t.shapePlaces({ results: [{ poi: { name: 'Shell' }, address: {}, position: { lat: 1, lon: 2 }, detourTime: 95 }] })[0].detour, 95);
});

test('the shared handler routes with stops and returns the optimized order', async () => {
  const { makeHandler } = require('./tomtom-serve');
  let asked = '';
  const real = global.fetch;
  global.fetch = async (url) => { asked = String(url); return new Response(JSON.stringify({ routes: [], optimizedWaypoints: [{ providedIndex: 0, optimizedIndex: 1 }, { providedIndex: 1, optimizedIndex: 0 }] })); };
  try {
    const h = makeHandler({ key: 'K', use: () => true });
    const r = await h('/route', new URLSearchParams('from=40.7,-74&to=41,-74.3&via=40.8,-74.1;40.9,-74.2&optimize=1'));
    assert.ok(asked.includes('40.8,-74.1:40.9,-74.2'));
    assert.ok(asked.includes('computeBestOrder=true'));
    assert.deepEqual(JSON.parse(r.body).order, [1, 0]);
    assert.equal((await h('/route', new URLSearchParams('from=40.7,-74&to=41,-74.3&via=junk'))).status, 400);
  } finally { global.fetch = real; }
});

test('the shared handler searches along a route posted by the page', async () => {
  const { makeHandler } = require('./tomtom-serve');
  let asked = '', sent = null;
  const used = [];
  const real = global.fetch;
  global.fetch = async (url, opts) => { asked = String(url); sent = opts; return new Response(JSON.stringify({ results: [{ poi: { name: 'Shell' }, address: {}, position: { lat: 1, lon: 2 }, detourTime: 60 }] })); };
  try {
    const h = makeHandler({ key: 'K', use: (k) => { used.push(k); return true; } });
    const r = await h('/along', new URLSearchParams('cat=gas'), '{"points":[[40.7,-74],[40.8,-74.1]]}');
    assert.equal(r.status, 200);
    assert.equal(JSON.parse(r.body).places[0].detour, 60);
    assert.equal(sent.method, 'POST');
    assert.deepEqual(JSON.parse(sent.body), { route: { points: [{ lat: 40.7, lon: -74 }, { lat: 40.8, lon: -74.1 }] } });
    assert.deepEqual(used, ['search']);
    assert.equal((await h('/along', new URLSearchParams('cat=gas'), 'nope')).status, 400);
  } finally { global.fetch = real; }
});

test('parseWhen reads one local time to leave at or arrive by, and refuses anything else', () => {
  assert.deepEqual(t.parseWhen(null, null), {});
  assert.deepEqual(t.parseWhen('2026-11-11T08:00', null), { departAt: '2026-11-11T08:00:00' });
  assert.deepEqual(t.parseWhen(null, '2026-11-11T09:30'), { arriveAt: '2026-11-11T09:30:00' });
  assert.equal(t.parseWhen('2026-11-11T08:00', '2026-11-11T09:00'), null);   // never both
  for (const bad of ['2026-02-30T08:00', '2026-11-11T24:00', '2026-11-11T08:60', '2026-11-11 08:00', 'now', '2026-11-11T08:00:00Z', '2026-11-11T08:00-05:00'])
    assert.equal(t.parseWhen(bad, null), null, bad);
});

test('routeUrl leaves now by default, or at a set time, or arrives by one, never both', () => {
  const a = { lat: 40.7, lon: -74 }, b = { lat: 40.8, lon: -73.9 };
  const now = new URL(t.routeUrl('K', a, b));
  assert.equal(now.searchParams.get('departAt'), 'now');
  assert.equal(now.searchParams.get('arriveAt'), null);
  const at = new URL(t.routeUrl('K', a, b, { when: { departAt: '2026-11-11T08:00:00' } }));
  assert.equal(at.searchParams.get('departAt'), '2026-11-11T08:00:00');
  const by = new URL(t.routeUrl('K', a, b, { when: { arriveAt: '2026-11-11T09:00:00' } }));
  assert.equal(by.searchParams.get('arriveAt'), '2026-11-11T09:00:00');
  assert.equal(by.searchParams.get('departAt'), null);
  assert.equal(by.searchParams.get('maxAlternatives'), '2');
});

test('shapeRoutes carries when the drive leaves and gets in', () => {
  const [r] = t.shapeRoutes({ routes: [{ summary: { travelTimeInSeconds: 1500, departureTime: '2026-11-11T08:35:00-05:00', arrivalTime: '2026-11-11T09:00:00-05:00' }, legs: [], sections: [] }] });
  assert.equal(r.departTime, '2026-11-11T08:35:00-05:00');
  assert.equal(r.arriveTime, '2026-11-11T09:00:00-05:00');
});

test('the shared handler passes Arrive by on to TomTom and refuses a bad time without a call', async () => {
  const { makeHandler } = require('./tomtom-serve');
  let asked = '', calls = 0;
  const real = global.fetch;
  global.fetch = async (url) => { calls++; asked = String(url); return new Response(JSON.stringify({ routes: [] })); };
  try {
    const h = makeHandler({ key: 'K', use: () => true });
    await h('/route', new URLSearchParams('from=47.6,-122.3&to=47.2,-122.4&by=2026-11-11T09:00'));
    assert.ok(asked.includes('arriveAt=2026-11-11T09%3A00%3A00'));
    assert.ok(!asked.includes('departAt'));
    const bad = await h('/route', new URLSearchParams('from=47.6,-122.3&to=47.2,-122.4&at=tomorrow'));
    assert.equal(bad.status, 400);
    assert.equal(calls, 1);
  } finally { global.fetch = real; }
});

test('Find Nearby has the errands on the way home: groceries and a pharmacy', () => {
  const g = new URL(t.nearbyUrl('K', 'grocery', { lat: 40.7, lon: -74 }));
  assert.equal(g.searchParams.get('categorySet'), '7332005,9361023');
  const p = new URL(t.alongUrl('K', 'pharmacy'));
  assert.equal(p.searchParams.get('categorySet'), '7326,9361051');
});
