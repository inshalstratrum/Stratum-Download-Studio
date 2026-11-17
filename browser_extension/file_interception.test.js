const test = require("node:test");
const assert = require("node:assert/strict");
const { eligible, transfer } = require("./file_interception.js");

function makeDownload(extra = {}) {
  return { id: 10, state: "in_progress", paused: false,
    url: "https://example.org/releases/manual.pdf", filename: "C:\\Downloads\\manual.pdf", ...extra };
}
function mockTransport(accepted = true, cancelFails = false) {
  const calls = [];
  let paused = false;
  const deps = {
    calls,
    pause: async id => { calls.push("pause"); paused = true; },
    remember: async (id, value) => calls.push(value ? "remember" : "forget"),
    send: async () => { calls.push("send"); return { success: accepted, code: "desktop_unavailable" }; },
    cancel: async () => { calls.push("cancel"); if (cancelFails) throw new Error("cancel failed"); paused = false; },
    isPaused: async () => paused,
    resume: async () => { calls.push("resume"); paused = false; },
  };
  return deps;
}
test("only supported explicit general files are eligible", () => {
  assert.equal(eligible(makeDownload()).fileName, "manual.pdf");
  for (const url of ["https://example.org/a.mp4", "https://example.org/watch", "file:///home/a.zip",
                     "http://localhost/a.zip", "https://user:pass@example.org/a.zip"]) {
    assert.equal(eligible(makeDownload({ url, filename: "" })), null, url);
  }
  assert.equal(eligible(makeDownload({ byExtensionId: "other" })), null);
  assert.equal(eligible(makeDownload({ state: "complete" })), null);
  assert.equal(eligible(makeDownload({ paused: true })), null);
  assert.equal(eligible(makeDownload({ filename: "C:\\Downloads\\archive.ZIP" })).fileName, "archive.ZIP");
});
test("accepted desktop file cancels Chrome only after real handoff response", async () => {
  const deps = mockTransport(true);
  assert.deepEqual(await transfer(makeDownload(), deps), { status: "desktop" });
  assert.deepEqual(deps.calls, ["pause", "remember", "send", "cancel", "forget"]);
});
test("unavailable desktop resumes Chrome and does not cancel", async () => {
  const deps = mockTransport(false);
  const outcome = await transfer(makeDownload(), deps);
  assert.equal(outcome.status, "native");
  assert.deepEqual(deps.calls, ["pause", "remember", "send", "resume", "forget"]);
});
test("failed browser cancellation resumes Chrome", async () => {
  const deps = mockTransport(true, true);
  const outcome = await transfer(makeDownload(), deps);
  assert.equal(outcome.status, "native");
  assert.deepEqual(deps.calls, ["pause", "remember", "send", "cancel", "resume", "forget"]);
});
test("unsupported download does nothing", async () => {
  const deps = mockTransport();
  assert.equal((await transfer(makeDownload({ filename: "index.html", url: "https://example.org/index.html" }), deps)).status, "skipped");
  assert.deepEqual(deps.calls, []);
});
