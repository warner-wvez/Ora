const test = require('node:test');
const assert = require('node:assert/strict');
const { parsePath, upstreamUrl, rewritePlaylist, isPlaylist, originAllowed, parsePassPath, passUrl, rewritePassPlaylist } = require('./relay');

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

test('parsePath reads North Carolina regional hosts and refuses the other states\' shapes', () => {
  assert.deepEqual(parsePath('/nc/4020/cfmse01/chan-5135_l/index.m3u8'), { state: 'nc', imageId: '4020', host: 'cfmse01', chan: 'chan-5135_l', file: 'index.m3u8' });
  assert.equal(parsePath('/nc/4020/cftse12/chan-5135_l/d0e1d450bf25_seg3601.mp4').host, 'cftse12');
  assert.equal(parsePath('/nc/4020/se1/chan-5135_l/index.m3u8'), null);
  assert.equal(parsePath('/pa/4020/cfmse01/chan-5135_l/index.m3u8'), null);
});

test('upstreamUrl builds each state host from the short name and appends the token', () => {
  const p = parsePath('/fl/691/se7/chan-3936_h/xflow.m3u8');
  assert.equal(upstreamUrl(p, 'abc123'), 'https://dis-se7.divas.cloud:8200/chan-3936_h/xflow.m3u8?token=abc123');
  assert.equal(upstreamUrl(p), 'https://dis-se7.divas.cloud:8200/chan-3936_h/xflow.m3u8');
  const q = parsePath('/pa/4774/se1/chan-2274/xflow.m3u8');
  assert.equal(upstreamUrl(q, 'abc123'), 'https://pa-se1.arcadis-ivds.com:8200/chan-2274/xflow.m3u8?token=abc123');
  const n = parsePath('/nc/4020/cfmse01/chan-5135_l/xflow.m3u8');
  assert.equal(upstreamUrl(n, 'abc123'), 'https://cfmse01.services.ncdot.gov:8887/chan-5135_l/xflow.m3u8?token=abc123');
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

// New Jersey needs no token, so its relay path is the upstream path itself behind a host key
test('parsePassPath reads New Jersey\'s two hosts and refuses anything else', () => {
  const w = 'hls/public/30/WF01-6478-AAD0-D5C0-F5D7_high/index.m3u8';
  assert.deepEqual(parsePassPath(`/nj/w/${w}`), { state: 'nj', key: 'w', path: w, file: 'index.m3u8' });
  assert.equal(parsePassPath('/nj/t/njta/203/public/hls/WF05-24AF-4D42-C020-79C1_nj0.ts').file, 'WF05-24AF-4D42-C020-79C1_nj0.ts');
  // one Turnpike camera lives under /media/
  assert.equal(parsePassPath('/nj/t/njta/204/media/public/hls/WF05-24B0-46EE-0875-23D7_nj.m3u8').key, 't');
  assert.equal(parsePassPath('/nj/w/hls/public/30/WF01-6478-AAD0-D5C0-F5D7_high/../../secret'), null);
  assert.equal(parsePassPath('/nj/w/admin/index.m3u8'), null);
  assert.equal(parsePassPath('/nj/x/hls/public/30/WF01_high/index.m3u8'), null);
  assert.equal(parsePassPath('/nj/t/hls/public/30/WF01-6478-AAD0-D5C0-F5D7_high/index.m3u8'), null);
  // the token states keep their own shape and never match here
  assert.equal(parsePassPath('/fl/691/se7/chan-3936_h/index.m3u8'), null);
});

test('passUrl puts the upstream path back on its host', () => {
  assert.equal(passUrl(parsePassPath('/nj/w/hls/public/30/WF01-6478-AAD0-D5C0-F5D7_high/video1_stream.m3u8')),
    'https://nj-511.wink.co/hls/public/30/WF01-6478-AAD0-D5C0-F5D7_high/video1_stream.m3u8');
  assert.equal(passUrl(parsePassPath('/nj/t/njta/203/public/hls/WF05-24AF-4D42-C020-79C1_nj.m3u8')),
    'https://njtpk-wink.xcmdata.org/njta/203/public/hls/WF05-24AF-4D42-C020-79C1_nj.m3u8');
});

// wink.co serves low-latency HLS: a quarter-second part every request. A traffic camera
// gains nothing from that, and it would multiply the relay's requests by eight, so the
// part tags go and the player sees plain two-second segments.
test('rewritePassPlaylist drops the low-latency tags and any otp, and pins absolute links', () => {
  const p = parsePassPath('/nj/w/hls/public/30/WF01-6478-AAD0-D5C2-F190_high/video1_stream.m3u8');
  const upstream = [
    '#EXTM3U',
    '#EXT-X-VERSION:10',
    '#EXT-X-TARGETDURATION:2',
    '#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES,PART-HOLD-BACK=0.66750,CAN-SKIP-UNTIL=12.00000',
    '#EXT-X-PART-INF:PART-TARGET=0.26700',
    '#EXT-X-MEDIA-SEQUENCE:10141',
    '#EXT-X-MAP:URI="87707b121360_video1_init.mp4?otp=468612307396"',
    '#EXT-X-PART:DURATION=0.26667,URI="87707b121360_video1_part18995.mp4",INDEPENDENT=YES',
    '#EXTINF:2.00000,',
    '87707b121360_video1_seg10141.mp4?otp=468612307396',
    '#EXTINF:2.00000,',
    'https://nj-511.wink.co/hls/public/30/WF01-6478-AAD0-D5C2-F190_high/87707b121360_video1_seg10142.mp4',
    '#EXT-X-PRELOAD-HINT:TYPE=PART,URI="87707b121360_video1_part19004.mp4"',
    '#EXT-X-RENDITION-REPORT:URI="video2_stream.m3u8",LAST-MSN=10142,LAST-PART=1',
    '',
  ].join('\n');
  assert.equal(rewritePassPlaylist(upstream, p), [
    '#EXTM3U',
    '#EXT-X-VERSION:10',
    '#EXT-X-TARGETDURATION:2',
    '#EXT-X-MEDIA-SEQUENCE:10141',
    '#EXT-X-MAP:URI="87707b121360_video1_init.mp4"',
    '#EXTINF:2.00000,',
    '87707b121360_video1_seg10141.mp4',
    '#EXTINF:2.00000,',
    '/nj/w/hls/public/30/WF01-6478-AAD0-D5C2-F190_high/87707b121360_video1_seg10142.mp4',
    '',
  ].join('\n'));
});

test('rewritePassPlaylist leaves the Turnpike\'s plain playlist alone', () => {
  const p = parsePassPath('/nj/t/njta/203/public/hls/WF05-24AF-4D42-C020-79C1_nj.m3u8');
  const text = '#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:2.000000,\nWF05-24AF-4D42-C020-79C1_nj0.ts\n';
  assert.equal(rewritePassPlaylist(text, p), text);
});
