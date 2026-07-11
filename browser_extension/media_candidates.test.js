const test = require("node:test");
const assert = require("node:assert/strict");
const {
  CandidateStore,
  classifyCandidate,
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
    const item = classify(url);
    assert.equal(item.type, "direct_media");
    assert.equal(item.mediaKind, "video");
  }
  for (const url of ["song.mp3", "song.m4a"]) {
    const item = classify(url);
    assert.equal(item.type, "direct_media");
    assert.equal(item.mediaKind, "audio");
  }
});

test("uses response evidence for extensionless media", () => {
  assert.equal(classify("https://cdn.test/play?id=1", { contentType: "video/mp4" }).type, "direct_media");
  assert.equal(classify("https://cdn.test/get?id=2", { contentDisposition: "attachment; filename=track.m4a" }).mediaKind, "audio");
  assert.equal(isUsefulResponseEvidence("audio/aac", ""), true);
});

test("classifies one HLS or DASH manifest", () => {
  assert.equal(classify("https://cdn.test/master.m3u8").type, "hls");
  assert.equal(classify("https://cdn.test/manifest.mpd").type, "dash");
  assert.equal(classify("https://cdn.test/live", { contentType: "application/vnd.apple.mpegurl" }).type, "hls");
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
});

test("rejects unsupported schemes and supports blob page fallback", () => {
  for (const url of ["blob:https://example.test/id", "data:video/mp4;base64,AAAA", "javascript:void(0)", "chrome-extension://id/file.mp4", "moz-extension://id/file.mp4", "file:///movie.mp4"]) {
    assert.equal(classify(url), null);
  }
  const fallback = classifyCandidate({ pageUrl, url: "blob:https://example.test/id", blobOnly: true, mediaKind: "video", evidence: "dom-media" });
  assert.equal(fallback.type, "page");
  assert.equal(fallback.url, pageUrl);
  assert.equal(classify("https://user:secret@cdn.test/movie.mp4"), null);
  assert.equal(classify(`https://cdn.test/${"x".repeat(8200)}.mp4`), null);
});

test("deduplicates DOM, performance, and webRequest evidence", () => {
  let now = 1000;
  const store = new CandidateStore({ clock: () => now });
  const base = { tabId: 4, frameId: 0, pageUrl, url: "https://cdn.test/movie.mp4" };
  const first = store.observe({ ...base, evidence: "dom-media" });
  now += 10;
  const second = store.observe({ ...base, evidence: "performance-resource" });
  now += 10;
  store.observe({ ...base, contentType: "video/mp4", evidence: "webRequest-response" });
  assert.equal(first.id, second.id);
  assert.equal(store.list({ tabId: 4 }).length, 1);
  assert.deepEqual(store.list({ tabId: 4 })[0].evidence, ["dom-media", "performance-resource", "webRequest-response"]);
});

test("keeps tab and frame candidates separate", () => {
  const store = new CandidateStore();
  const base = { pageUrl, url: "https://cdn.test/movie.mp4", evidence: "fixture" };
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
    store.observe({ tabId: 1, frameId: 0, pageUrl, url: `https://cdn.test/${index}.mp4`, evidence: "fixture" });
  }
  assert.equal(store.list().length, 2);
  now += 1001;
  assert.equal(store.list().length, 0);
});

test("removes only candidates owned by the addressed tab and frame", () => {
  const store = new CandidateStore();
  const first = store.observe({ tabId: 1, frameId: 0, pageUrl, url: "https://cdn.test/one.mp4", evidence: "fixture" });
  const second = store.observe({ tabId: 1, frameId: 2, pageUrl, url: "https://cdn.test/two.mp4", evidence: "fixture" });
  store.removeIds([first.id, second.id], { tabId: 1, frameId: 0 });
  assert.deepEqual(store.list().map((item) => item.id), [second.id]);
});
