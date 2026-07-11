const extensionApi = globalThis.browser || globalThis.chrome;
const candidateApi = globalThis.StratumMediaCandidates;
const mediaControls = new Map();
const elementCandidateIds = new WeakMap();
const elementEvidence = new WeakMap();
const drmMedia = new WeakSet();
let showMediaButtons = true;
let positionFrame = null;
let lastPageUrl = window.location.href;
const mediaResizeObserver = typeof ResizeObserver === "function" ? new ResizeObserver(() => schedulePositionUpdate()) : null;

function supportedPageUrl() {
  return window.location.protocol === "http:" || window.location.protocol === "https:";
}

function pageTitle() {
  return String(document.title || "Media").replace(/\s+/g, " ").trim().slice(0, 160);
}

function rawCandidate(url, mediaKind, evidence, extra = {}) {
  return {
    pageUrl: window.location.href,
    url,
    mediaKind,
    title: extra.title || pageTitle(),
    evidence,
    ...extra
  };
}

async function reportCandidate(candidate) {
  try {
    const response = await extensionApi.runtime.sendMessage({ type: "stratrum-candidate-observed", candidate });
    return response && response.candidate ? response.candidate : null;
  } catch (error) {
    return null;
  }
}

function mediaKindFor(element) {
  return element.tagName === "AUDIO" ? "audio" : "video";
}

function elementCandidates(element, evidence = "dom-media") {
  if (element.tagName === "IFRAME") {
    const iframeUrl = element.getAttribute("src") || "";
    return candidateApi.isExtractorPage(iframeUrl) ? [rawCandidate(iframeUrl, "video", "embedded-frame", { title: element.title || pageTitle() })] : [];
  }
  if (element.tagName === "A") {
    return [rawCandidate(element.href, "video", "media-link", { title: element.textContent || element.title || pageTitle() })];
  }

  if (drmMedia.has(element) || element.mediaKeys) return [];

  const kind = mediaKindFor(element);
  const candidates = [];
  const sources = [
    { url: element.currentSrc, type: element.getAttribute("type") || "", source: evidence },
    { url: element.getAttribute("src") || "", type: element.getAttribute("type") || "", source: evidence }
  ];
  element.querySelectorAll("source").forEach((source) => {
    sources.push({ url: source.src || source.getAttribute("src") || "", type: source.type || "", source: "nested-source" });
  });
  for (const source of sources) {
    if (!source.url) continue;
    const blobOnly = /^(?:blob|data):/i.test(source.url);
    candidates.push(rawCandidate(source.url, kind, source.source, {
      contentType: source.type,
      blobOnly,
      allowPage: true,
      title: element.getAttribute("aria-label") || element.title || pageTitle()
    }));
  }
  if (element.srcObject || candidates.length === 0) {
    candidates.push(rawCandidate(window.location.href, kind, evidence, { blobOnly: true, title: pageTitle() }));
  }
  return candidates;
}

async function observeElement(element, evidence) {
  const observed = [];
  for (const candidate of elementCandidates(element, evidence)) {
    const result = await reportCandidate(candidate);
    if (result) observed.push(result);
  }
  elementCandidateIds.set(element, new Set(observed.map((item) => item.id)));
  return observed;
}

function removeElementCandidates(element) {
  const ids = Array.from(elementCandidateIds.get(element) || []);
  elementCandidateIds.delete(element);
  if (ids.length) extensionApi.runtime.sendMessage({ type: "stratrum-remove-candidates", ids }).catch(() => {});
}

function showStatus(message, success = false) {
  const existing = document.getElementById("stratum-extension-status");
  if (existing) existing.remove();
  const status = document.createElement("div");
  status.id = "stratum-extension-status";
  status.textContent = message;
  Object.assign(status.style, {
    position: "fixed", right: "16px", bottom: "16px", zIndex: "2147483647",
    maxWidth: "360px", padding: "10px 12px", borderRadius: "6px", color: "#ffffff",
    background: success ? "#107c10" : "#a4262c", boxShadow: "0 4px 14px rgba(0,0,0,.3)",
    font: "13px/1.4 system-ui, sans-serif"
  });
  document.documentElement.appendChild(status);
  setTimeout(() => status.remove(), 6000);
}

async function requestDownload(candidate, button) {
  const originalText = button.textContent;
  button.textContent = "Sending…";
  button.disabled = true;
  try {
    const result = await extensionApi.runtime.sendMessage({ type: "stratrum-download-request", url: candidate.url });
    showStatus(result && result.message ? result.message : "The extension did not receive a response.", Boolean(result && result.success));
    button.textContent = result && result.success ? "Sent ✓" : originalText;
  } catch (error) {
    showStatus("Stratum extension communication failed. Open extension Options and try again.");
    button.textContent = originalText;
  } finally {
    button.disabled = false;
    setTimeout(() => { if (button.isConnected) button.textContent = originalText; }, 2000);
  }
}

function closePicker() {
  const existing = document.getElementById("stratum-candidate-picker");
  if (existing) existing.remove();
}

function candidateLabel(candidate) {
  const type = { page: "Page", direct_media: "Direct", hls: "HLS", dash: "DASH" }[candidate.type] || "Media";
  return `${candidate.title} — ${type} ${candidate.mediaKind}`;
}

function showPicker(candidates, button) {
  closePicker();
  const picker = document.createElement("div");
  picker.id = "stratum-candidate-picker";
  picker.setAttribute("role", "menu");
  Object.assign(picker.style, {
    position: "absolute", zIndex: "2147483647", minWidth: "240px", maxWidth: "360px",
    padding: "5px", border: "1px solid #777", borderRadius: "6px", background: "#ffffff",
    boxShadow: "0 4px 16px rgba(0,0,0,.35)", font: "13px/1.35 system-ui, sans-serif"
  });
  for (const candidate of candidates) {
    const choice = document.createElement("button");
    choice.type = "button";
    choice.textContent = candidateLabel(candidate);
    choice.title = candidate.url;
    choice.setAttribute("role", "menuitem");
    Object.assign(choice.style, {
      display: "block", width: "100%", padding: "7px 8px", border: "0", borderRadius: "4px",
      textAlign: "left", color: "#1b1b1b", background: "transparent", cursor: "pointer"
    });
    choice.addEventListener("click", (event) => {
      event.preventDefault(); event.stopPropagation(); closePicker(); requestDownload(candidate, button);
    });
    picker.appendChild(choice);
  }
  document.documentElement.appendChild(picker);
  const rect = button.getBoundingClientRect();
  picker.style.top = `${rect.bottom + window.scrollY + 4}px`;
  picker.style.left = `${Math.max(4, rect.right + window.scrollX - picker.offsetWidth)}px`;
}

async function handleControlClick(element, button) {
  await observeElement(element, "control-click");
  let candidates = [];
  try {
    const result = await extensionApi.runtime.sendMessage({ type: "stratrum-get-candidates", pageUrl: window.location.href });
    candidates = result && Array.isArray(result.candidates) ? result.candidates : [];
  } catch (error) {
    showStatus("Stratum could not load detected media choices.");
    return;
  }
  if (candidates.length === 0) {
    showStatus("No safe downloadable media was detected on this player.");
  } else if (candidates.length === 1) {
    await requestDownload(candidates[0], button);
  } else {
    showPicker(candidates, button);
  }
}

function positionControls() {
  positionFrame = null;
  for (const [element, button] of mediaControls) {
    if (!element.isConnected) {
      button.remove(); mediaControls.delete(element); removeElementCandidates(element);
      if (mediaResizeObserver) mediaResizeObserver.unobserve(element);
      continue;
    }
    const rect = element.getBoundingClientRect();
    const minimumHeight = element.tagName === "AUDIO" || element.tagName === "A" ? 28 : 80;
    const usefulSize = rect.width >= 160 && rect.height >= minimumHeight;
    button.hidden = !usefulSize || rect.bottom < 0 || rect.right < 0;
    if (!button.hidden) {
      if (!elementCandidateIds.has(element)) observeElement(element, elementEvidence.get(element) || "dom-media");
      button.style.top = `${Math.max(4, rect.top + window.scrollY + 8)}px`;
      button.style.left = `${Math.max(4, rect.right + window.scrollX - button.offsetWidth - 8)}px`;
    }
  }
}

function schedulePositionUpdate() {
  if (positionFrame === null) positionFrame = window.requestAnimationFrame(positionControls);
}

function attachControl(element) {
  if (!showMediaButtons || mediaControls.has(element) || !element.isConnected) return;
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "↓ Stratum";
  button.setAttribute("aria-label", "Choose detected media for Stratum Download Studio");
  Object.assign(button.style, {
    position: "absolute", zIndex: "2147483646", padding: "5px 9px", border: "1px solid #ffffff",
    borderRadius: "5px", color: "#ffffff", background: "#0067b8", boxShadow: "0 2px 8px rgba(0,0,0,.35)",
    cursor: "pointer", font: "600 12px/1.2 system-ui, sans-serif"
  });
  button.addEventListener("click", (event) => {
    event.preventDefault(); event.stopPropagation(); handleControlClick(element, button);
  });
  document.documentElement.appendChild(button);
  mediaControls.set(element, button);
  elementEvidence.set(element, "dom-media");
  if (mediaResizeObserver) mediaResizeObserver.observe(element);
  schedulePositionUpdate();
}

function isMediaLink(element) {
  return element.tagName === "A" && /\.(?:mp4|webm|mov|mkv|avi|mp3|m4a|aac|ogg|oga|opus|wav|flac|m3u8|mpd)(?:$|[?#])/i.test(element.href || "");
}

function scanNode(node) {
  if (!showMediaButtons || !(node instanceof Element)) return;
  const consider = (element) => {
    if (element.matches("video, audio") || (element.matches("iframe") && candidateApi.isExtractorPage(element.src)) || isMediaLink(element)) attachControl(element);
  };
  consider(node);
  node.querySelectorAll("video, audio, iframe, a[href]").forEach(consider);
}

function removeAllControls() {
  closePicker();
  for (const [element, button] of mediaControls) {
    button.remove();
    removeElementCandidates(element);
    if (mediaResizeObserver) mediaResizeObserver.unobserve(element);
  }
  mediaControls.clear();
}

function observeDirectPage() {
  reportCandidate(rawCandidate(window.location.href, "video", "page-url"));
}

function handleNavigation() {
  if (lastPageUrl === window.location.href) return;
  lastPageUrl = window.location.href;
  closePicker();
  observeDirectPage();
  scanNode(document.documentElement);
}

function installNavigationHooks() {
  for (const method of ["pushState", "replaceState"]) {
    const original = history[method];
    history[method] = function (...args) {
      const result = original.apply(this, args);
      queueMicrotask(handleNavigation);
      return result;
    };
  }
  window.addEventListener("popstate", handleNavigation);
  window.addEventListener("hashchange", handleNavigation);
}

if (supportedPageUrl()) {
  extensionApi.storage.local.get(["showMediaButtons"]).then((stored) => {
    showMediaButtons = stored.showMediaButtons !== false;
    observeDirectPage();
    if (showMediaButtons) scanNode(document.documentElement);
  });

  const observer = new MutationObserver((mutations) => {
    if (!showMediaButtons) return;
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(scanNode);
      if (mutation.type === "attributes") {
        const target = mutation.target.tagName === "SOURCE" ? mutation.target.closest("video, audio") : mutation.target;
        if (target && mediaControls.has(target)) {
          removeElementCandidates(target);
          elementEvidence.set(target, "source-change");
          schedulePositionUpdate();
        }
        if (mutation.target.tagName === "IFRAME") scanNode(mutation.target);
      }
    }
    schedulePositionUpdate();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["src", "poster", "href"] });

  document.addEventListener("loadstart", (event) => {
    if (event.target instanceof HTMLMediaElement && mediaControls.has(event.target)) {
      removeElementCandidates(event.target);
      elementEvidence.set(event.target, "currentSrc-change");
      schedulePositionUpdate();
    }
  }, true);
  document.addEventListener("loadedmetadata", (event) => {
    if (event.target instanceof HTMLMediaElement && mediaControls.has(event.target)) schedulePositionUpdate();
  }, true);
  document.addEventListener("encrypted", (event) => {
    if (!(event.target instanceof HTMLMediaElement)) return;
    drmMedia.add(event.target);
    removeElementCandidates(event.target);
    const button = mediaControls.get(event.target);
    if (button) button.remove();
    if (mediaResizeObserver) mediaResizeObserver.unobserve(event.target);
    mediaControls.delete(event.target);
  }, true);

  if (typeof PerformanceObserver === "function") {
    try {
      const performanceObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          reportCandidate(rawCandidate(entry.name, "video", "performance-resource"));
        }
      });
      performanceObserver.observe({ type: "resource", buffered: true });
    } catch (error) {
      // Older MV3 engines may not support buffered resource observation.
    }
  }

  extensionApi.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes.showMediaButtons) return;
    showMediaButtons = changes.showMediaButtons.newValue !== false;
    if (showMediaButtons) scanNode(document.documentElement); else removeAllControls();
  });

  extensionApi.runtime.onMessage.addListener((message) => {
    if (message && message.type === "stratrum-status") showStatus(message.message, Boolean(message.success));
  });
  installNavigationHooks();
  window.addEventListener("scroll", schedulePositionUpdate, { passive: true });
  window.addEventListener("resize", schedulePositionUpdate, { passive: true });
}
