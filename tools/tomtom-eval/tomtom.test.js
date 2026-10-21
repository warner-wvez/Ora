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
  assert.deepEqual(u.searchParams.getAll('sectionType'), ['traffic', 'importantRoadStretch']);
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
  assert.deepEqual(places[0], { name: 'Pike Place Market', address: '85 Pike St, Seattle, WA 98101', type: 'POI', lat: 47.609, lon: -122.341, bbox: [-122.343, 47.608, -122.339, 47.61] });
  assert.equal(places[1].name, '400 Broad St, Seattle, WA 98109');
  assert.equal(places[1].address, 'Seattle, WA');
});

test('shapeRoutes joins every leg into one [lon, lat] line with its time and delay', () => {
  const routes = t.shapeRoutes({ routes: [{
    summary: { travelTimeInSeconds: 1500, trafficDelayInSeconds: 360, noTrafficTravelTimeInSeconds: 1140, lengthInMeters: 29000 },
    legs: [{ points: [{ latitude: 47.6, longitude: -122.3 }, { latitude: 47.5, longitude: -122.31 }] }, { points: [{ latitude: 47.4, longitude: -122.32 }] }],
  }] });
  assert.deepEqual(routes, [{ seconds: 1500, delaySeconds: 360, noTrafficSeconds: 1140, meters: 29000, coords: [[-122.3, 47.6], [-122.31, 47.5], [-122.32, 47.4]], traffic: [], via: [] }]);
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
  assert.deepEqual(r.traffic, [{ from: 10, to: 40, level: 'slow' }, { from: 50, to: 60, level: 'jam' }, { from: 70, to: 90, level: 'closed' }]);
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
