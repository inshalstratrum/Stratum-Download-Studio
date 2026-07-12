const test = require("node:test");
const assert = require("node:assert/strict");
const {
  CandidateStore,
  PlayerOwnershipStore,
  applyTrustedOwner,
  canonicalCandidateUrl,
  classifyCandidate,
  isOverlayTargetDescriptor,
  isSegmentUrl,
  isUsefulResponseEvidence,
  stablePageUrl
} = require("./media_candidates.js");

const pageUrl = "https://example.test/watch/lesson";

function classify(url, extra = {}) {
  return classifyCandidate({ pageUrl, url, evidence: "fixture", ...extra });
}

test("classifies direct video and audio formats", () => {
  for (const url of ["movie.mp4", "movie.webm"]) {
    const item = classify(url, { evidence: "dom-media" });
    assert.equal(item.type, "direct_media");
    assert.equal(item.mediaKind, "video");
  }
  for (const url of ["song.mp3", "song.m4a"]) {
    const item = classify(url, { evidence: "dom-media" });
    assert.equal(item.type, "direct_media");
    assert.equal(item.mediaKind, "audio");
  }
});

test("uses response evidence for extensionless media", () => {
  assert.equal(classify("https://cdn.test/play?id=1", { contentType: "video/mp4", evidence: "webRequest-response" }), null);
  assert.equal(classify("https://cdn.test/play?id=1", { contentType: "video/mp4", evidence: "webRequest-main-frame" }).type, "direct_media");
  assert.equal(classify("https://cdn.test/get?id=2", { contentDisposition: "attachment; filename=track.m4a", evidence: "webRequest-response" }).mediaKind, "audio");
  assert.equal(isUsefulResponseEvidence("audio/aac", ""), true);
});

test("classifies one HLS or DASH manifest", () => {
  const hls = classify("https://cdn.test/master.m3u8");
  const dash = classify("https://cdn.test/manifest.mpd", { contentType: "application/dash+xml" });
  assert.equal(hls.type, "hls");
  assert.equal(hls.priority, 0);
  assert.equal(hls.label, "Video • Best quality");
  assert.equal(dash.type, "dash");
  assert.equal(dash.priority, 0);
  assert.equal(dash.label, "Video • Best quality");
  assert.equal(classify("https://cdn.test/live", { contentType: "application/vnd.apple.mpegurl" }).type, "hls");
  assert.equal(classify("https://cdn.test/initialization/manifest.mpd").type, "dash");
});

test("suppresses segments, chunks, and googlevideo fragments", () => {
  for (const url of [
    "https://cdn.test/segment-14.ts",
    "https://cdn.test/video/chunk_3.m4s",
    "https://r1---sn.test.googlevideo.com/videoplayback?id=x"
  ]) {
    assert.equal(isSegmentUrl(url), true);
    assert.equal(classify(url, { contentType: "video/mp4" }), null);
  }
});

test("normalizes YouTube and embedded YouTube to one stable page", () => {
  const watch = stablePageUrl("https://www.youtube.com/watch?v=AbCdEf12345&list=PL1");
  const embed = stablePageUrl("https://www.youtube-nocookie.com/embed/AbCdEf12345?autoplay=1");
  assert.equal(watch, "https://www.youtube.com/watch?v=AbCdEf12345");
  assert.equal(embed, watch);
  assert.equal(classify(embed).type, "page");
  assert.notEqual(
    classify("https://www.youtube.com/embed/AbCdEf12345").id,
    classify("https://www.youtube.com/embed/ZyXwVu98765").id
  );
});

test("rejects unsupported schemes and only permits extractor blob fallback", () => {
  for (const url of ["blob:https://example.test/id", "data:video/mp4;base64,AAAA", "javascript:void(0)", "chrome-extension://id/file.mp4", "moz-extension://id/file.mp4", "file:///movie.mp4"]) {
    assert.equal(classify(url), null);
  }
  const fallback = classifyCandidate({ pageUrl, url: "blob:https://example.test/id", blobOnly: true, mediaKind: "video", evidence: "dom-media" });
  assert.equal(fallback, null);
  const extractorFallback = classifyCandidate({ pageUrl: "https://www.youtube.com/embed/AbCdEf12345", url: "blob:https://youtube.com/id", blobOnly: true, mediaKind: "video", evidence: "dom-media" });
  assert.equal(extractorFallback.type, "page");
  assert.equal(classify("https://user:secret@cdn.test/movie.mp4"), null);
  assert.equal(classify(`https://cdn.test/${"x".repeat(8200)}.mp4`), null);
});

test("deduplicates DOM, performance, and webRequest evidence", () => {
  let now = 1000;
  const store = new CandidateStore({ clock: () => now });
  const base = { tabId: 4, frameId: 0, pageUrl, url: "https://cdn.test/movie.mp4" };
  const first = store.observe({ ...base, evidence: "dom-media" });
  now += 10;
  const second = store.observe({ ...base, evidence: "nested-source" });
  now += 10;
  store.observe({ ...base, contentType: "video/mp4", evidence: "source-change" });
  assert.equal(first.id, second.id);
  assert.equal(store.list({ tabId: 4 }).length, 1);
  assert.deepEqual(store.list({ tabId: 4 })[0].evidence, ["dom-media", "nested-source", "source-change"]);
});

test("keeps tab and frame candidates separate", () => {
  const store = new CandidateStore();
  const base = { pageUrl, url: "https://cdn.test/movie.mp4", evidence: "dom-media" };
  const main = store.observe({ ...base, tabId: 1, frameId: 0 });
  const frame = store.observe({ ...base, tabId: 1, frameId: 2 });
  const otherTab = store.observe({ ...base, tabId: 2, frameId: 0 });
  assert.notEqual(main.id, frame.id);
  assert.notEqual(main.id, otherTab.id);
  assert.equal(store.list({ tabId: 1 }).length, 2);
});

test("bounds candidates and expires stale observations", () => {
  let now = 0;
  const store = new CandidateStore({ maxCandidates: 2, ttlMs: 1000, clock: () => now });
  for (let index = 0; index < 3; index += 1) {
    now += 10;
    store.observe({ tabId: 1, frameId: 0, pageUrl, url: `https://cdn.test/${index}.mp4`, evidence: "dom-media" });
  }
  assert.equal(store.list().length, 2);
  now += 1001;
  assert.equal(store.list().length, 0);
});

test("removes only candidates owned by the addressed tab and frame", () => {
  const store = new CandidateStore();
  const first = store.observe({ tabId: 1, frameId: 0, pageUrl, url: "https://cdn.test/one.mp4", evidence: "dom-media" });
  const second = store.observe({ tabId: 1, frameId: 2, pageUrl, url: "https://cdn.test/two.mp4", evidence: "dom-media" });
  store.removeIds([first.id, second.id], { tabId: 1, frameId: 0 });
  assert.deepEqual(store.list().map((item) => item.id), [second.id]);
});

test("creates a direct top-level MP4 only from strong document evidence", () => {
  const extensionOnly = classifyCandidate({
    tabId: 8,
    frameId: 0,
    pageUrl: "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    url: "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    topLevelDocument: true,
    evidence: "top-level-media-document"
  });
  const byDocumentType = classifyCandidate({
    tabId: 8, frameId: 0,
    pageUrl: "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    url: "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    contentType: "video/mp4", topLevelDocument: true, evidence: "top-level-media-document"
  });
  const byVerifiedResponse = classifyCandidate({
    tabId: 8, frameId: 0, pageUrl: "https://media.test/file", url: "https://media.test/file",
    contentType: "video/mp4", evidence: "webRequest-main-frame"
  });
  assert.equal(extensionOnly, null);
  for (const item of [byDocumentType, byVerifiedResponse]) {
    assert.equal(item.type, "direct_media");
    assert.equal(item.priority, 0);
  }
  assert.equal(byDocumentType.label, "Video • Best quality");
});

test("captures MPD response evidence and prefers it over DASH segments", () => {
  const store = new CandidateStore();
  const owner = { tabId: 5, frameId: 3, pageUrl: "https://reference.dashif.org/player" };
  store.observe({ ...owner, url: "https://dash.test/audio/track.m4a", contentType: "audio/mp4", evidence: "webRequest-response" });
  const manifest = store.observe({ ...owner, url: "https://dash.test/stream/manifest.mpd", contentType: "application/dash+xml", evidence: "webRequest-response" });
  store.observe({ ...owner, url: "https://dash.test/video/representation.mp4?range=1-500", contentType: "video/mp4", evidence: "performance-resource" });
  assert.equal(manifest.type, "dash");
  assert.deepEqual(store.list(owner).map((item) => item.url), [manifest.url]);
});

test("prefers a Shaka manifest over its unsupported page fallback", () => {
  const store = new CandidateStore();
  const owner = { tabId: 6, frameId: 0, pageUrl: "https://shaka-player-demo.appspot.com/demo/" };
  store.observe({ ...owner, url: owner.pageUrl, blobOnly: true, evidence: "dom-media" });
  const manifest = store.observe({ ...owner, url: "https://storage.test/asset/manifest.mpd?token=secret", contentType: "application/dash+xml", evidence: "webRequest-response" });
  const listed = store.list(owner);
  assert.equal(listed.length, 1);
  assert.equal(listed[0].id, manifest.id);
  assert.doesNotMatch(listed[0].label, /token|secret/i);
});

test("does not grow a segment list after a manifest exists", () => {
  let now = 0;
  const store = new CandidateStore({ maxCandidates: 200, clock: () => now });
  const owner = { tabId: 7, frameId: 0, pageUrl: "https://player.test/demo" };
  store.observe({ ...owner, url: "https://cdn.test/master.m3u8", contentType: "application/vnd.apple.mpegurl", evidence: "webRequest-response" });
  for (let index = 0; index < 500; index += 1) {
    now += 120;
    store.observe({ ...owner, url: `https://cdn.test/audio/adaptive-${index}.m4a?token=${index}`, contentType: "audio/mp4", evidence: "webRequest-response" });
    store.observe({ ...owner, url: `https://cdn.test/video/chunk-${index}.m4s`, contentType: "video/mp4", evidence: "performance-resource" });
  }
  assert.equal(store.items.size, 1);
  assert.equal(store.list(owner)[0].type, "hls");
});

test("YouTube page candidate suppresses network fragments", () => {
  const store = new CandidateStore();
  const owner = { tabId: 9, frameId: 4, pageUrl: "https://www.youtube.com/embed/AbCdEf12345" };
  store.observe({ ...owner, url: "https://cdn.other.test/adaptive-video.mp4?signature=secret", contentType: "video/mp4", evidence: "performance-resource" });
  const page = store.observe({ ...owner, url: owner.pageUrl, title: "First video", evidence: "page-url" });
  assert.deepEqual(store.list({ tabId: 9, frameId: 4 }).map((item) => item.id), [page.id]);
});

test("player-local frame lists cannot see sibling iframe candidates", () => {
  const store = new CandidateStore();
  const first = store.observe({ tabId: 10, frameId: 21, pageUrl: "https://www.youtube.com/embed/AbCdEf12345", url: "https://www.youtube.com/embed/AbCdEf12345", title: "First", evidence: "page-url" });
  const second = store.observe({ tabId: 10, frameId: 22, pageUrl: "https://www.youtube.com/embed/ZyXwVu98765", url: "https://www.youtube.com/embed/ZyXwVu98765", title: "Second", evidence: "page-url" });
  assert.deepEqual(store.list({ tabId: 10, frameId: 21 }).map((item) => item.id), [first.id]);
  assert.deepEqual(store.list({ tabId: 10, frameId: 22 }).map((item) => item.id), [second.id]);
});

test("trusted sender ownership overrides page-supplied identifiers", () => {
  const owned = applyTrustedOwner({ tabId: 999, frameId: 888, url: "https://cdn.test/movie.mp4" }, 12, 34);
  assert.equal(owned.tabId, 12);
  assert.equal(owned.frameId, 34);
});

test("candidate labels are useful, distinct, and query-safe", () => {
  const store = new CandidateStore();
  const owner = { tabId: 11, frameId: 0, pageUrl };
  store.observe({ ...owner, url: "https://one.test/path/movie.mp4?token=secret", evidence: "dom-media", width: 1920, height: 1080 });
  store.observe({ ...owner, url: "https://two.test/other/movie.mp4?signature=hidden", evidence: "dom-media", width: 1920, height: 1080 });
  const labels = store.list(owner).map((item) => item.label);
  assert.equal(new Set(labels).size, 2);
  assert.ok(labels.every((label) => /Video • 1920×1080 • Source [12]/.test(label)));
  assert.ok(labels.every((label) => !/secret|hidden|token|signature/i.test(label)));
  assert.equal(canonicalCandidateUrl("https://one.test/path/movie.mp4?token=a&id=public"), "https://one.test/path/movie.mp4?id=public");
});

test("late trusted frame-page binding keeps an early manifest owned by its player", () => {
  const store = new CandidateStore();
  const manifest = store.observe({ tabId: 13, frameId: 2, pageUrl: "https://shaka.test/", url: "https://cdn.test/manifest.mpd", contentType: "application/dash+xml", evidence: "webRequest-response" });
  store.reassignFramePage(13, 2, "https://shaka.test/demo/player");
  store.observe({ tabId: 13, frameId: 2, pageUrl: "https://shaka.test/demo/player", url: "https://shaka.test/demo/player", blobOnly: true, evidence: "dom-media" });
  assert.deepEqual(store.list({ tabId: 13, frameId: 2, pageUrl: "https://shaka.test/demo/player" }).map((item) => item.id), [manifest.id]);
});

test("rejects CMAF init, byte-range, and fragmented representation requests", () => {
  const network = { pageUrl: "https://player.test", contentType: "video/mp4", evidence: "webRequest-response" };
  for (const url of [
    "https://cdn.test/init-f1-a1.mp4",
    "https://cdn.test/video/init_0.mp4",
    "https://cdn.test/v-0576p-1400k-libx264-s6.mp4",
    "https://cdn.test/movie.mp4?range=0-999"
  ]) assert.equal(classifyCandidate({ ...network, url }), null);
  assert.equal(classifyCandidate({ ...network, url: "https://cdn.test/movie.mp4", statusCode: 206 }), null);
  assert.equal(classifyCandidate({ ...network, url: "https://cdn.test/movie.mp4", contentRange: "bytes 0-999/5000" }), null);
});

test("media extension alone is not complete-file evidence", () => {
  assert.equal(classify("https://cdn.test/movie.mp4", { evidence: "performance-resource" }), null);
  assert.equal(classify("https://cdn.test/audio.m4a", { contentType: "audio/mp4", evidence: "webRequest-response" }), null);
  assert.equal(classify("https://cdn.test/movie.mp4", { evidence: "dom-media" }).type, "direct_media");
  assert.equal(classify("https://cdn.test/download", { contentDisposition: "attachment; filename=movie.mp4", evidence: "webRequest-response" }).type, "direct_media");
  assert.equal(classify("https://cdn.test/movie_1080p_final.mp4", { contentDisposition: "attachment; filename=movie_1080p_final.mp4", evidence: "webRequest-response" }).type, "direct_media");
});

test("normal HTML never becomes a direct media document", () => {
  assert.equal(classifyCandidate({ pageUrl: "https://example.test/article.mp4", url: "https://example.test/article.mp4", contentType: "text/html", topLevelDocument: true, evidence: "top-level-media-document" }), null);
  assert.equal(classifyCandidate({ pageUrl: "https://example.test/article", url: "https://example.test/article", contentType: "text/html", evidence: "webRequest-main-frame" }), null);
});

test("Brightcove manifest replaces an Al Jazeera-style page fallback", () => {
  const store = new CandidateStore();
  const owner = { tabId: 14, frameId: 0, pageUrl: "https://www.aljazeera.com/news/example" };
  assert.equal(store.observe({ ...owner, url: owner.pageUrl, blobOnly: true, evidence: "dom-media" }), null);
  const manifest = store.observe({ ...owner, url: "https://manifest.prod.boltdns.net/manifest/v1/hls/master.m3u8?token=secret", contentType: "application/x-mpegURL", evidence: "webRequest-response" });
  assert.equal(manifest.type, "hls");
  assert.equal(manifest.label, "Video • Best quality");
  assert.equal(store.list(owner).length, 1);
  assert.match(store.list(owner)[0].url, /\?token=secret$/);
});

test("CNBC supported extractor page and HLS MIME regressions remain accepted", () => {
  const cnbc = classifyCandidate({ pageUrl: "https://www.cnbc.com/video/2026/07/11/example.html", url: "https://www.cnbc.com/video/2026/07/11/example.html", title: "Housing reform", evidence: "page-url" });
  assert.equal(cnbc.type, "page");
  assert.equal(cnbc.label, "Housing reform • Best quality");
  assert.equal(classify("https://cdn.test/live?id=public", { contentType: "application/x-mpegURL", evidence: "webRequest-response" }).type, "hls");
});

test("embedded iframe overlay ownership yields two buttons, not four", () => {
  const parentTargets = [
    { tagName: "iframe", href: "https://www.youtube.com/embed/AbCdEf12345" },
    { tagName: "iframe", href: "https://www.youtube.com/embed/ZyXwVu98765" }
  ];
  const frameTargets = [{ tagName: "video" }, { tagName: "video" }];
  assert.equal(parentTargets.filter(isOverlayTargetDescriptor).length, 0);
  assert.equal(frameTargets.filter(isOverlayTargetDescriptor).length, 2);
});

test("recognizes Shaka audio-only and video HLS variants", () => {
  const audio = classify("https://storage.googleapis.com/shaka-demo-assets/bbb-dark-truths-hls/playlist_a-eng-0128k-aac-2c.mp4.m3u8", { contentType: "application/vnd.apple.mpegurl", evidence: "webRequest-response" });
  const video = classify("https://storage.googleapis.com/shaka-demo-assets/bbb-dark-truths-hls/playlist_v-0720p-2500k-libx264.mp4.m3u8", { contentType: "application/vnd.apple.mpegurl", evidence: "webRequest-response" });
  assert.equal(audio.mediaKind, "audio");
  assert.equal(audio.manifestRole, "audio_variant");
  assert.equal(audio.label, "Audio • Audio only");
  assert.equal(video.mediaKind, "video");
  assert.equal(video.manifestRole, "video_variant");
  assert.equal(video.label, "Video • Video only");
  const store = new CandidateStore();
  const owner = { tabId: 19, frameId: 0, pageUrl };
  store.observe({ ...owner, url: "https://cdn.test/stream.m3u8", evidence: "performance-resource" });
  store.observe({ ...owner, url: "https://cdn.test/stream.m3u8", contentType: "audio/mpegurl", evidence: "webRequest-response" });
  assert.equal(store.list(owner).length, 0);
  assert.equal(store.list({ ...owner, simpleMode: false })[0].label, "Audio • Audio only");
});

test("Shaka master manifest suppresses related child variants in either observation order", () => {
  const owner = { tabId: 20, frameId: 0, pageUrl: "https://shaka-project.github.io/demo" };
  const store = new CandidateStore();
  store.observe({ ...owner, url: "https://storage.googleapis.com/shaka-demo-assets/bbb-dark-truths-hls/playlist_a-eng-0128k-aac-2c.mp4.m3u8", evidence: "webRequest-response" });
  store.observe({ ...owner, url: "https://storage.googleapis.com/shaka-demo-assets/bbb-dark-truths-hls/playlist_v-0720p-2500k-libx264.mp4.m3u8", evidence: "webRequest-response" });
  const master = store.observe({ ...owner, url: "https://storage.googleapis.com/shaka-demo-assets/bbb-dark-truths-hls/hls.m3u8?token=signed", evidence: "webRequest-response" });
  assert.deepEqual(store.list(owner).map((item) => item.id), [master.id]);
  assert.equal(store.observe({ ...owner, url: "https://storage.googleapis.com/shaka-demo-assets/bbb-dark-truths-hls/playlist_a-fra-0064k-aac-2c.mp4.m3u8", evidence: "webRequest-response" }), null);
});

test("Brightcove master preference keeps signed URL and redacts its label", () => {
  const owner = { tabId: 21, frameId: 0, pageUrl: "https://news.test/article" };
  const store = new CandidateStore();
  store.observe({ ...owner, url: "https://manifest.prod.boltdns.net/player-42/playlist_a-eng-128k.m3u8?token=child-secret", evidence: "webRequest-response" });
  store.observe({ ...owner, url: "https://manifest.prod.boltdns.net/player-42/playlist_v-720p-2500k.m3u8?token=video-secret", evidence: "webRequest-response" });
  store.observe({ ...owner, url: "https://manifest.prod.boltdns.net/player-42/master.m3u8?token=first-secret", evidence: "webRequest-response" });
  const refreshed = store.observe({ ...owner, url: "https://manifest.prod.boltdns.net/player-42/master.m3u8?token=fresh-secret", evidence: "webRequest-response" });
  const listed = store.list(owner);
  assert.equal(listed.length, 1);
  assert.equal(listed[0].url, refreshed.url);
  assert.match(listed[0].url, /token=fresh-secret/);
  assert.doesNotMatch(listed[0].label, /token|secret/i);
});

test("master preference never crosses player identity or trusted frame", () => {
  const store = new CandidateStore();
  const pageUrl = "https://news.test/article";
  const masterA = store.observe({ tabId: 22, frameId: 1, pageUrl, url: "https://cdn.test/shared/master.m3u8?videoId=A&token=secret", evidence: "webRequest-response" });
  const variantB = store.observe({ tabId: 22, frameId: 1, pageUrl, url: "https://cdn.test/shared/playlist_a-eng-128k.m3u8?videoId=B&token=secret", evidence: "webRequest-response" });
  const variantOtherFrame = store.observe({ tabId: 22, frameId: 2, pageUrl, url: "https://cdn.test/shared/playlist_a-eng-128k.m3u8?videoId=A&token=secret", evidence: "webRequest-response" });
  assert.deepEqual(store.list({ tabId: 22, frameId: 1 }).map((item) => item.id), [masterA.id]);
  assert.equal(store.items.has(variantB.id), true);
  assert.deepEqual(store.list({ tabId: 22, frameId: 2 }).map((item) => item.id), []);
  assert.equal(store.items.has(variantOtherFrame.id), true);
});

test("two players in one frame remain isolated by extension player identity", () => {
  const store = new CandidateStore();
  const owner = { tabId: 30, frameId: 0, pageUrl: "https://example.test/feed", evidence: "dom-media" };
  const first = store.observe({ ...owner, playerId: "player-aaaaaaaa", url: "https://cdn.test/first.mp4", title: "First" });
  const second = store.observe({ ...owner, playerId: "player-bbbbbbbb", url: "https://cdn.test/second.mp4", title: "Second" });
  assert.deepEqual(store.list({ ...owner, playerId: "player-aaaaaaaa" }).map((item) => item.id), [first.id]);
  assert.deepEqual(store.list({ ...owner, playerId: "player-bbbbbbbb" }).map((item) => item.id), [second.id]);
});

test("navigation rejects reused player ownership and removes stale candidates", () => {
  const owners = new PlayerOwnershipStore();
  const store = new CandidateStore();
  const playerId = "player-reused01";
  assert.equal(owners.bind(31, 0, playerId, "https://example.test/one"), true);
  const stale = store.observe({ tabId: 31, frameId: 0, playerId, pageUrl: "https://example.test/one", url: "https://cdn.test/old.mp4", evidence: "dom-media" });
  assert.equal(owners.bind(31, 0, playerId, "https://example.test/two"), false);
  store.removeFrame(31, 0);
  owners.removeFrame(31, 0);
  assert.equal(store.items.has(stale.id), false);
  assert.equal(owners.bind(31, 0, "player-reused02", "https://example.test/two"), true);
});

test("canonical social page routing strips tracking but keeps required identifiers", () => {
  const fixtures = new Map([
    ["https://www.dailymotion.com/video/x9abc?playlist=x&token=secret", "https://www.dailymotion.com/video/x9abc"],
    ["https://m.facebook.com/watch/?v=12345&utm_source=x", "https://www.facebook.com/watch/?v=12345"],
    ["https://www.instagram.com/reel/ABC_123/?igsh=secret", "https://www.instagram.com/reel/ABC_123/"],
    ["https://www.tiktok.com/@creator/video/741234567890?is_from_webapp=1", "https://www.tiktok.com/@creator/video/741234567890"],
    ["https://twitter.com/creator/status/182345678901?ref_src=x", "https://x.com/creator/status/182345678901"]
  ]);
  for (const [input, expected] of fixtures) {
    assert.equal(stablePageUrl(input), expected);
    const candidate = classifyCandidate({ tabId: 32, frameId: 0, playerId: "player-social01", pageUrl: input, url: input, title: "Post title", evidence: "dom-media" });
    assert.equal(candidate.type, "page");
    assert.equal(candidate.url, expected);
    assert.equal(candidate.label, "Post title • Best quality");
  }
});

test("canonical page beats components while complete master and direct top-level media survive", () => {
  const social = { tabId: 33, frameId: 0, playerId: "player-social02", pageUrl: "https://www.instagram.com/reel/ABC/" };
  const store = new CandidateStore();
  store.observe({ ...social, url: "https://cdn.test/video-only.mp4", mediaKind: "video", evidence: "dom-media" });
  const page = store.observe({ ...social, url: social.pageUrl, title: "Reel", evidence: "dom-media" });
  assert.deepEqual(store.list(social).map((item) => item.id), [page.id]);

  const masterStore = new CandidateStore();
  const master = masterStore.observe({ ...social, url: "https://cdn.test/master.m3u8?token=signed-secret", evidence: "webRequest-response" });
  masterStore.observe({ ...social, url: social.pageUrl, title: "Reel", evidence: "dom-media" });
  assert.deepEqual(masterStore.list(social).map((item) => item.id), [master.id]);
  assert.match(masterStore.list(social)[0].url, /token=signed-secret/);
  assert.doesNotMatch(masterStore.list(social)[0].label, /m3u8|HLS|signed|secret|CDN/i);

  const direct = classifyCandidate({ ...social, url: "https://files.test/movie.mp4?signature=live", contentType: "video/mp4", topLevelDocument: true, evidence: "top-level-media-document" });
  assert.equal(direct.priority, 0);
  assert.match(direct.url, /signature=live/);
});

test("simple selection suppresses component renditions and never calls them complete", () => {
  const store = new CandidateStore();
  const owner = { tabId: 34, frameId: 1, playerId: "player-components", pageUrl: "https://player.test/watch" };
  const audio = store.observe({ ...owner, url: "https://cdn.test/media/playlist_a-eng-128k.m3u8", evidence: "webRequest-response" });
  const video = store.observe({ ...owner, url: "https://cdn.test/media/playlist_v-720p-2m.m3u8", evidence: "webRequest-response" });
  const master = store.observe({ ...owner, url: "https://cdn.test/media/master.m3u8", evidence: "webRequest-response" });
  assert.equal(audio.label, "Audio • Audio only");
  assert.equal(video.label, "Video • Video only");
  assert.deepEqual(store.list(owner).map((item) => item.id), [master.id]);

  const componentsOnly = new CandidateStore();
  componentsOnly.observe({ ...owner, url: "https://cdn.test/other/playlist_a-eng-128k.m3u8", evidence: "webRequest-response" });
  componentsOnly.observe({ ...owner, url: "https://cdn.test/other/playlist_v-720p-2m.m3u8", evidence: "webRequest-response" });
  assert.equal(componentsOnly.list(owner).length, 0);
});

test("NLM-style iframe ownership remains frame and player local", () => {
  const store = new CandidateStore();
  const first = store.observe({ tabId: 35, frameId: 7, playerId: "player-nlm0001", pageUrl: "https://www.youtube-nocookie.com/embed/AbCdEf12345", url: "https://www.youtube-nocookie.com/embed/AbCdEf12345", evidence: "dom-media" });
  store.observe({ tabId: 35, frameId: 8, playerId: "player-nlm0002", pageUrl: "https://www.youtube-nocookie.com/embed/ZyXwVu98765", url: "https://www.youtube-nocookie.com/embed/ZyXwVu98765", evidence: "dom-media" });
  assert.deepEqual(store.list({ tabId: 35, frameId: 7, playerId: "player-nlm0001" }).map((item) => item.id), [first.id]);
  assert.equal(first.url, "https://www.youtube.com/watch?v=AbCdEf12345");
});

test("ownership storage is bounded and rejects cross-tab frame player requests", () => {
  const owners = new PlayerOwnershipStore(2);
  assert.equal(owners.bind(40, 0, "player-owner001", "https://example.test/a"), true);
  assert.equal(owners.bind(40, 0, "player-owner002", "https://example.test/a"), true);
  assert.equal(owners.bind(40, 0, "player-owner003", "https://example.test/a"), true);
  assert.equal(owners.items.size, 2);
  assert.equal(owners.owns(40, 0, "player-owner001", "https://example.test/a"), false);
  assert.equal(owners.owns(41, 0, "player-owner003", "https://example.test/a"), false);
  assert.equal(owners.owns(40, 1, "player-owner003", "https://example.test/a"), false);
  assert.equal(owners.owns(40, 0, "player-owner003", "https://example.test/b"), false);
  assert.equal(owners.owns(40, 0, "player-owner003", "https://example.test/a"), true);
});
