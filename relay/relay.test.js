const test = require('node:test');
const assert = require('node:assert/strict');
const { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed } = require('./relay');

test('parsePath reads the four parts and rejects anything else', () => {
  assert.deepEqual(parsePath('/fl/691/se7/chan-3936_h/index.m3u8'), { imageId: '691', host: 'se7', chan: 'chan-3936_h', file: 'index.m3u8' });
  assert.deepEqual(parsePath('/fl/691/se7/chan-3936_h/3d6247524eb1_seg7547.mp4').file, '3d6247524eb1_seg7547.mp4');
  assert.equal(parsePath('/fl/691/se7/chan-3936_h/../secret'), null);
  assert.equal(parsePath('/fl/abc/se7/chan-3936_h/index.m3u8'), null);
  assert.equal(parsePath('/tx/691/se7/chan-3936_h/index.m3u8'), null);
  assert.equal(parsePath('/fl/691/se7/chan-3936_h/'), null);
});

test('upstreamUrl builds the divas host from the short name and appends the token', () => {
  const p = parsePath('/fl/691/se7/chan-3936_h/xflow.m3u8');
  assert.equal(upstreamUrl(p, 'abc123'), 'https://dis-se7.divas.cloud:8200/chan-3936_h/xflow.m3u8?token=abc123');
  assert.equal(upstreamUrl(p), 'https://dis-se7.divas.cloud:8200/chan-3936_h/xflow.m3u8');
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

test('isPlaylist and originAllowed', () => {
  assert.equal(isPlaylist('index.m3u8'), true);
  assert.equal(isPlaylist('seg1.mp4'), false);
  const allowed = ['https://warner-wvez.github.io', 'http://localhost:*'];
  assert.equal(originAllowed(undefined, allowed), true);
  assert.equal(originAllowed('https://warner-wvez.github.io', allowed), true);
  assert.equal(originAllowed('http://localhost:8934', allowed), true);
  assert.equal(originAllowed('https://evil.example', allowed), false);
});
