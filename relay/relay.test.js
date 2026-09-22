const test = require('node:test');
const assert = require('node:assert/strict');
const { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed } = require('./relay');

test('parsePath reads the five parts and rejects anything else', () => {
  assert.deepEqual(parsePath('/fl/691/se7/chan-3936_h/index.m3u8'), { state: 'fl', imageId: '691', host: 'se7', chan: 'chan-3936_h', file: 'index.m3u8' });
  assert.deepEqual(parsePath('/fl/691/se7/chan-3936_h/3d6247524eb1_seg7547.mp4').file, '3d6247524eb1_seg7547.mp4');
  assert.equal(parsePath('/fl/691/se7/chan-3936_h/../secret'), null);
  assert.equal(parsePath('/fl/abc/se7/chan-3936_h/index.m3u8'), null);
  assert.equal(parsePath('/fl/691/se7/chan-3936_h/'), null);
  // Texas plays direct, so it must not be reachable through the relay
  assert.equal(parsePath('/tx/691/se7/chan-3936_h/index.m3u8'), null);
  assert.equal(parsePath('/zz/691/se7/chan-3936_h/index.m3u8'), null);
});

test('parsePath reads Pennsylvania and keeps the two states apart', () => {
  assert.deepEqual(parsePath('/pa/4774/se1/chan-2274/index.m3u8'), { state: 'pa', imageId: '4774', host: 'se1', chan: 'chan-2274', file: 'index.m3u8' });
  assert.equal(parsePath('/pa/4774/se1/chan-2274/36c5c856b744_seg2280.mp4').file, '36c5c856b744_seg2280.mp4');
  assert.equal(parsePath('/pa/4774/nope/chan-2274/index.m3u8'), null);
});

test('upstreamUrl builds each state host from the short name and appends the token', () => {
  const p = parsePath('/fl/691/se7/chan-3936_h/xflow.m3u8');
  assert.equal(upstreamUrl(p, 'abc123'), 'https://dis-se7.divas.cloud:8200/chan-3936_h/xflow.m3u8?token=abc123');
  assert.equal(upstreamUrl(p), 'https://dis-se7.divas.cloud:8200/chan-3936_h/xflow.m3u8');
  const q = parsePath('/pa/4774/se1/chan-2274/xflow.m3u8');
  assert.equal(upstreamUrl(q, 'abc123'), 'https://pa-se1.arcadis-ivds.com:8200/chan-2274/xflow.m3u8?token=abc123');
});

test('rewritePlaylist strips the token and pins absolute host references to the relay path', () => {
  const p = parsePath('/fl/691/se7/chan-3936_h/index.m3u8');
  const upstream = [
    '#EXTM3U',
    '#EXT-X-STREAM-INF:BANDWIDTH=800000',
    'xflow.m3u8?token=3d4fa43cedfa',
    '#EXT-X-MAP:URI="3d6247524eb1_init.mp4?token=3d4fa43cedfa"',
    '#EXTINF:2.0,',
    'https://dis-se7.divas.cloud:8200/chan-3936_h/3d6247524eb1_seg7547.mp4?token=3d4fa43cedfa',
    '',
  ].join('\n');
  assert.equal(rewritePlaylist(upstream, p), [
    '#EXTM3U',
    '#EXT-X-STREAM-INF:BANDWIDTH=800000',
    'xflow.m3u8',
    '#EXT-X-MAP:URI="3d6247524eb1_init.mp4"',
    '#EXTINF:2.0,',
    '/fl/691/se7/chan-3936_h/3d6247524eb1_seg7547.mp4',
    '',
  ].join('\n'));
});

test('rewritePlaylist leaves a token-free playlist alone', () => {
  const p = parsePath('/fl/691/se7/chan-3936_h/index.m3u8');
  const text = '#EXTM3U\nxflow.m3u8\n';
  assert.equal(rewritePlaylist(text, p), text);
});

// Pennsylvania serves fragmented MP4 behind a 64-hex token, and its host carries a dash
// the old hard-coded regex never had to escape
test('rewritePlaylist pins Pennsylvania segments back to the relay', () => {
  const p = parsePath('/pa/4774/se1/chan-2274/xflow.m3u8');
  const tok = 'b88233eb36fdccf968d5c2c569c62306a9a8a59db0d588a9235ffaa4b70d424d';
  const upstream = [
    '#EXTM3U',
    `#EXT-X-MAP:URI="36c5c856b744_init.mp4?token=${tok}"`,
    '#EXTINF:12.8,',
    `36c5c856b744_seg2280.mp4?token=${tok}`,
    `https://pa-se1.arcadis-ivds.com:8200/chan-2274/36c5c856b744_seg2281.mp4?token=${tok}`,
    '',
  ].join('\n');
  assert.equal(rewritePlaylist(upstream, p), [
    '#EXTM3U',
    '#EXT-X-MAP:URI="36c5c856b744_init.mp4"',
    '#EXTINF:12.8,',
    '36c5c856b744_seg2280.mp4',
    '/pa/4774/se1/chan-2274/36c5c856b744_seg2281.mp4',
    '',
  ].join('\n'));
});

test('isPlaylist and originAllowed', () => {
  assert.equal(isPlaylist('index.m3u8'), true);
  assert.equal(isPlaylist('seg1.mp4'), false);
  const allowed = ['https://warner-wvez.github.io', 'http://localhost:*'];
  assert.equal(originAllowed(undefined, allowed), true);
  assert.equal(originAllowed('https://warner-wvez.github.io', allowed), true);
  assert.equal(originAllowed('http://localhost:8934', allowed), true);
  assert.equal(originAllowed('https://evil.example', allowed), false);
});
