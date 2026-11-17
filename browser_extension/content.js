const extensionApi = globalThis.browser || globalThis.chrome;
const candidateApi = globalThis.StratumMediaCandidates;
const mediaControls = new Map();
const elementCandidateIds = new WeakMap();
const elementPlayerIds = new WeakMap();
const elementEvidence = new WeakMap();
const elementSourceKeys = new WeakMap();
const frameCapabilities = new WeakMap();
const observedRoots = new WeakSet();
const queriedFrames = new WeakSet();
const drmMedia = new WeakSet();
let showMediaButtons = true;
let positionFrame = null;
let domObserver = null;
let capabilityTimer = null;
let capabilityReady = false;
let lastPageUrl = window.location.href;
let playerSequence = 0;
let pageGeneration = 0;
const DETECTION_WAIT_MS = 1600;
const DETECTION_POLL_MS = 160;
const mediaResizeObserver = typeof ResizeObserver === "function" ? new ResizeObserver(() => schedulePositionUpdate()) : null;

function supportedPageUrl() {
  return window.location.protocol === "http:" || window.location.protocol === "https:";
}

function pageTitle() {
  return String(document.title || "Media").replace(/\s+/g, " ").trim().slice(0, 160);
}

function newPlayerId() {
  playerSequence += 1;
  const random = globalThis.crypto && typeof globalThis.crypto.randomUUID === "function"
    ? globalThis.crypto.randomUUID().replace(/-/g, "")
    : `${Date.now().toString(36)}${playerSequence.toString(36)}`;
  return `player-${pageGeneration.toString(36)}-${playerSequence.toString(36)}-${random}`;
}

function playerIdFor(element) {
  let id = elementPlayerIds.get(element);
  if (!id) {
    id = newPlayerId();
    elementPlayerIds.set(element, id);
  }
  return id;
}

function visiblePlayer(element) {
  if (!element.isConnected) return false;
  const rect = element.getBoundingClientRect();
  const style = globalThis.getComputedStyle ? getComputedStyle(element) : null;
  return rect.width >= 160 && rect.height >= (element.tagName === "AUDIO" ? 28 : 80) && (!style || (style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0));
}

function jsonLdVideoUrls() {
  const foundUrls = [];
  const visit = (value) => {
    if (!value || typeof value !== "object") return;
    const types = Array.isArray(value["@type"]) ? value["@type"] : [value["@type"]];
    if (types.includes("VideoObject")) {
      const main = value.mainEntityOfPage;
      const candidate = value.url || (typeof main === "string" ? main : main && main["@id"]) || "";
      if (candidate) foundUrls.push(candidate);
    }
    for (const child of Object.values(value)) {
      if (Array.isArray(child)) {
        for (const item of child) visit(item);
      } else if (child && typeof child === "object") {
        visit(child);
      }
    }
  };
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { visit(JSON.parse(script.textContent || "null")); } catch (error) { /* Ignore malformed page metadata. */ }
  }
  return Array.from(new Set(foundUrls)).slice(0, 12);
}

function domDistance(left, right) {
  const ancestry = (node) => {
    const result = [];
    for (let current = node; current; current = current.parentNode || current.host) result.push(current);
    return result;
  };
  const leftPath = ancestry(left);
  const rightPath = ancestry(right);
  let best = 1000;
  for (let leftIndex = 0; leftIndex < leftPath.length; leftIndex += 1) {
    const rightIndex = rightPath.indexOf(leftPath[leftIndex]);
    if (rightIndex >= 0) best = Math.min(best, leftIndex + rightIndex);
  }
  return best;
}

function queryAllOpenRoots(selector) {
  const matches = [];
  const roots = [document];
  const seen = new Set();
  while (roots.length) {
    const root = roots.pop();
    if (!root || seen.has(root) || typeof root.querySelectorAll !== "function") continue;
    seen.add(root);
    root.querySelectorAll(selector).forEach((element) => matches.push(element));
    root.querySelectorAll("*").forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
  }
  return matches;
}

function composedContains(container, node) {
  for (let current = node; current; current = current.parentNode || current.host) {
    if (current === container) return true;
  }
  return false;
}

function pageProvenance(element) {
  const canonical = document.querySelector('link[rel="canonical"]');
  const og = document.querySelector('meta[property="og:url"], meta[name="og:url"]');
  const container = element.closest('[role="dialog"], article, [role="article"], [data-testid*="post" i], [data-e2e*="feed" i], [data-e2e*="video" i], li') || element.parentElement;
  const anchorCandidates = [];
  if (container) {
    for (const link of container.querySelectorAll("a[href]")) {
      if (candidateApi.isExtractorPage(link.href)) anchorCandidates.push({ url: link.href, distance: domDistance(element, link) });
    }
  }
  const jsonLdUrls = jsonLdVideoUrls();
  const provenance = {
    pageUrl: window.location.href,
    anchorCandidates,
    canonicalUrl: canonical ? canonical.href : "",
    ogUrl: og ? og.content : "",
    jsonLdUrls,
    jsonLdUrl: jsonLdUrls[0] || "",
    activePlayer: element instanceof HTMLMediaElement ? !element.paused : false
  };
  const nearestPermalink = candidateApi.resolvePlayerPermalink(provenance, window.location.href) || "";
  return {
    nearestPermalink,
    ...provenance
  };
}

function sourceHintsFor(element, provenance) {
  const hints = [];
  if (element instanceof HTMLMediaElement) {
    hints.push(element.currentSrc, element.getAttribute("src") || "");
    element.querySelectorAll("source[src]").forEach((source) => hints.push(source.src || source.getAttribute("src") || ""));
  }
  hints.push(provenance.nearestPermalink || "");
  return Array.from(new Set(hints.filter((value) => /^https?:/i.test(value)))).slice(0, 12);
}

function playerContext(element) {
  const provenance = pageProvenance(element);
  return {
    playerId: playerIdFor(element),
    documentGeneration: pageGeneration,
    visiblePlayer: visiblePlayer(element),
    requestContext: { userAgent: String(navigator.userAgent || "").slice(0, 512) },
    sourceHints: sourceHintsFor(element, provenance),
    ...provenance
  };
}

function reportPlayerState(element, activity, active = true) {
  const context = playerContext(element);
  return extensionApi.runtime.sendMessage({
    type: "stratrum-player-state", pageUrl: window.location.href,
    playerId: context.playerId, documentGeneration: pageGeneration,
    visible: context.visiblePlayer, active, activity,
    sourceHints: context.sourceHints, permalink: context.nearestPermalink
  }).catch(() => {});
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

function sourceFingerprint(element) {
  if (!(element instanceof HTMLMediaElement)) return `${element.tagName}:${element.getAttribute("src") || ""}:${window.location.href}`;
  const nested = Array.from(element.querySelectorAll("source")).map((source) => `${source.src || source.getAttribute("src") || ""}|${source.type || ""}`);
  return [element.currentSrc, element.getAttribute("src") || "", element.getAttribute("poster") || "", ...nested].join("\n");
}

function refreshPlayerOwnership(element) {
  const next = sourceFingerprint(element);
  const previous = elementSourceKeys.get(element);
  elementSourceKeys.set(element, next);
  if (previous === undefined || previous === next) return false;
  removeElementCandidates(element);
  retirePlayer(element);
  playerIdFor(element);
  return true;
}

function elementCandidates(element, evidence = "dom-media") {
  if (drmMedia.has(element) || element.mediaKeys) return [];

  const kind = mediaKindFor(element);
  const context = playerContext(element);
  const playerId = context.playerId;
  const candidates = [];
  if (element.tagName === "IFRAME" && element.dataset.stratumFrameProxy === "true") {
    candidates.push(rawCandidate(window.location.href, "video", evidence, {
      blobOnly: true, articleFallback: true, title: pageTitle(), ...context
    }));
    return candidates;
  }
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
      title: element.getAttribute("aria-label") || element.title || pageTitle(),
      width: Number(element.videoWidth) || 0,
      height: Number(element.videoHeight) || 0,
      ...context
    }));
  }
  const sourcePage = candidateApi.validatedSourcePage(context, window.location.href);
  if (sourcePage && candidateApi.isExtractorPage(sourcePage)) {
    candidates.push(rawCandidate(sourcePage, kind, evidence, { title: pageTitle(), ...context }));
  } else if (element.srcObject || candidates.length === 0) {
    candidates.push(rawCandidate(window.location.href, kind, evidence, { blobOnly: true, articleFallback: true, title: pageTitle(), ...context }));
  }
  return candidates;
}

async function observeElement(element, evidence) {
  await reportPlayerState(element, evidence, evidence === "control-click" || !element.paused);
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
  const playerId = elementPlayerIds.get(element) || "";
  if (ids.length) extensionApi.runtime.sendMessage({ type: "stratrum-remove-candidates", ids, playerId, documentGeneration: pageGeneration }).catch(() => {});
}

function retirePlayer(element) {
  const playerId = elementPlayerIds.get(element) || "";
  if (playerId) extensionApi.runtime.sendMessage({ type: "stratrum-player-removed", playerId, documentGeneration: pageGeneration }).catch(() => {});
  elementPlayerIds.delete(element);
}

function showStatus(message, state = "error", duration = 6000) {
  const existing = document.getElementById("stratum-extension-status");
  if (existing) existing.remove();
  const status = document.createElement("div");
  status.id = "stratum-extension-status";
  status.textContent = message;
  Object.assign(status.style, {
    position: "fixed", right: "16px", bottom: "16px", zIndex: "2147483647",
    maxWidth: "360px", padding: "10px 12px", borderRadius: "6px", color: "#ffffff",
    background: state === "success" || state === true ? "#107c10" : state === "pending" ? "#0067b8" : "#a4262c", boxShadow: "0 4px 14px rgba(0,0,0,.3)",
    font: "13px/1.4 system-ui, sans-serif"
  });
  document.documentElement.appendChild(status);
  setTimeout(() => status.remove(), duration);
}

async function requestDownload(candidate, button) {
  const originalText = button.textContent;
  button.textContent = "Sending…";
  button.disabled = true;
  try {
    const result = await extensionApi.runtime.sendMessage({ type: "stratrum-download-request", candidateId: candidate.id, playerId: candidate.playerId, documentGeneration: pageGeneration });
    showStatus(result && result.message ? result.message : "The extension did not receive a response.", result && result.success ? "success" : "error");
    button.textContent = result && result.success ? "Sent ✓" : originalText;
  } catch (error) {
    showStatus("I-DS extension communication failed. Open extension Options and try again.");
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
  return candidate.label || `${candidate.mediaKind === "audio" ? "Audio" : "Video"} • Media`;
}

function showPicker(candidates, button) {
  closePicker();
  const picker = document.createElement("div");
  picker.id = "stratum-candidate-picker";
  picker.setAttribute("role", "menu");
  Object.assign(picker.style, {
    position: "fixed", zIndex: "2147483647", minWidth: "240px", maxWidth: "360px",
    padding: "5px", border: "1px solid #777", borderRadius: "6px", background: "#ffffff",
    boxShadow: "0 4px 16px rgba(0,0,0,.35)", font: "13px/1.35 system-ui, sans-serif"
  });
  for (const candidate of candidates) {
    const choice = document.createElement("button");
    choice.type = "button";
    choice.textContent = candidateLabel(candidate);
    choice.title = candidateLabel(candidate);
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
  picker.style.top = `${Math.min(window.innerHeight - picker.offsetHeight - 4, rect.bottom + 4)}px`;
  picker.style.left = `${Math.max(4, rect.right - picker.offsetWidth)}px`;
}

async function handleControlClick(element, button) {
  const originalText = button.textContent;
  button.textContent = "Detecting video…";
  await reportPlayerState(element, "control-click", true);
  await observeElement(element, "control-click");
  const loadCandidates = async () => {
    const result = await extensionApi.runtime.sendMessage({ type: "stratrum-get-candidates", pageUrl: window.location.href, playerId: playerIdFor(element), documentGeneration: pageGeneration });
    return result && Array.isArray(result.candidates) ? result.candidates : [];
  };
  let candidates;
  try {
    candidates = await loadCandidates();
    if (candidates.length === 0) {
      showStatus("Detecting video…", "pending", DETECTION_WAIT_MS + 800);
      const deadline = Date.now() + DETECTION_WAIT_MS;
      while (candidates.length === 0 && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, DETECTION_POLL_MS));
        candidates = await loadCandidates();
      }
    }
  } catch (error) {
    showStatus("I-DS could not load detected media choices.");
    button.textContent = originalText;
    return;
  }
  button.textContent = originalText;
  if (candidates.length === 0) {
    showStatus("No complete downloadable media detected.");
  } else if (candidates.length === 1) {
    await requestDownload(candidates[0], button);
  } else {
    showPicker(candidates, button);
  }
}

function positionControls() {
  positionFrame = null;
  const activeModal = visibleModal();
  for (const [element, button] of mediaControls) {
    if (!element.isConnected) {
      button.remove(); mediaControls.delete(element); removeElementCandidates(element); retirePlayer(element);
      if (mediaResizeObserver) mediaResizeObserver.unobserve(element);
      continue;
    }
    const rect = element.getBoundingClientRect();
    const minimumHeight = element.tagName === "AUDIO" ? 28 : 80;
    const usefulSize = rect.width >= 160 && rect.height >= minimumHeight;
    const playerVisible = usefulSize && rect.bottom >= 0 && rect.right >= 0 && rect.top <= window.innerHeight && rect.left <= window.innerWidth;
    button.hidden = !candidateApi.shouldShowPlayerOverlay({ playerVisible, modalOpen: Boolean(activeModal), playerInModal: Boolean(activeModal && composedContains(activeModal, element)) });
    if (!button.hidden) {
      if (!elementCandidateIds.has(element)) observeElement(element, elementEvidence.get(element) || "dom-media");
      button.style.top = `${Math.max(4, rect.top + 8)}px`;
      button.style.left = `${Math.max(4, rect.right - button.offsetWidth - 8)}px`;
    }
  }
}

function schedulePositionUpdate() {
  if (positionFrame === null) positionFrame = window.requestAnimationFrame(positionControls);
}

function visibleModal() {
  const candidates = queryAllOpenRoots('[role="dialog"], [aria-modal="true"]').filter((element) => {
    const rect = element.getBoundingClientRect();
    const style = globalThis.getComputedStyle ? getComputedStyle(element) : null;
    return rect.width >= 160 && rect.height >= 80 && (!style || (style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0));
  });
  return candidates.sort((left, right) => (Number.parseInt(getComputedStyle(right).zIndex, 10) || 0) - (Number.parseInt(getComputedStyle(left).zIndex, 10) || 0))[0] || null;
}

function attachControl(element, options = {}) {
  if (!showMediaButtons || mediaControls.has(element) || !element.isConnected) return;
  if (options.frameProxy) element.dataset.stratumFrameProxy = "true";
  elementSourceKeys.set(element, sourceFingerprint(element));
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "↓ I-DS";
  button.setAttribute("aria-label", "Choose detected media for I-DS");
  Object.assign(button.style, {
    position: "fixed", zIndex: "2147483646", padding: "5px 9px", border: "1px solid #ffffff",
    borderRadius: "5px", color: "#ffffff", background: "#0067b8", boxShadow: "0 2px 8px rgba(0,0,0,.35)",
    cursor: "pointer", font: "600 12px/1.2 system-ui, sans-serif"
  });
  button.addEventListener("click", (event) => {
    event.preventDefault(); event.stopPropagation(); handleControlClick(element, button);
  });
  document.documentElement.appendChild(button);
  mediaControls.set(element, button);
  elementEvidence.set(element, options.frameProxy ? "frame-capability" : "dom-media");
  reportPlayerState(element, "attached", false);
  if (mediaResizeObserver) mediaResizeObserver.observe(element);
  schedulePositionUpdate();
}

function isOverlayTarget(element) {
  return candidateApi.isOverlayTargetDescriptor({ tagName: element.tagName, href: element.href || "", frameProxy: element.dataset && element.dataset.stratumFrameProxy === "true" });
}

function scanNode(node) {
  if (!showMediaButtons || !node || typeof node.querySelectorAll !== "function") return;
  const consider = (element) => {
    if (isOverlayTarget(element)) attachControl(element);
  };
  if (node instanceof Element) consider(node);
  node.querySelectorAll("video, audio").forEach(consider);
  const roots = [];
  if (node instanceof Element && node.shadowRoot) roots.push(node.shadowRoot);
  node.querySelectorAll("*").forEach((element) => { if (element.shadowRoot) roots.push(element.shadowRoot); });
  for (const root of roots) {
    observeRoot(root);
    scanNode(root);
  }
  node.querySelectorAll("iframe").forEach((frame) => {
    if (!queriedFrames.has(frame)) {
      queriedFrames.add(frame);
      frame.addEventListener("load", () => queryFrameCapability(frame));
    }
    queryFrameCapability(frame);
  });
  scheduleCapabilityAnnouncement();
}

function observeRoot(root) {
  if (!domObserver || !root || observedRoots.has(root)) return;
  observedRoots.add(root);
  domObserver.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["src", "poster", "class", "style", "open", "aria-hidden"] });
}

function customPlayerPresent() {
  return queryAllOpenRoots('[data-video-player], [data-testid*="video" i], [class*="video-player" i], [id*="video-player" i], [class*="vhs" i], video-js').length > 0;
}

function scheduleCapabilityAnnouncement() {
  if (!capabilityReady || capabilityTimer !== null) return;
  capabilityTimer = setTimeout(() => {
    capabilityTimer = null;
    if (window.parent === window) return;
    const nativeMedia = Array.from(mediaControls.keys()).some((element) => element.tagName === "VIDEO" || element.tagName === "AUDIO");
    window.parent.postMessage({
      type: "stratrum-frame-capability", generation: pageGeneration,
      hasNativeMedia: nativeMedia, hasCustomPlayer: !nativeMedia && customPlayerPresent()
    }, "*");
  }, 0);
}

function frameForWindow(source) {
  const frames = queryAllOpenRoots("iframe");
  return frames.find((frame) => {
    try { return frame.contentWindow === source; } catch (error) { return false; }
  }) || null;
}

function queryFrameCapability(frame) {
  try { if (frame.contentWindow) frame.contentWindow.postMessage({ type: "stratrum-parent-capability-query" }, "*"); } catch (error) { /* Cross-origin capability probing uses postMessage only. */ }
}

function removeFrameProxy(frame) {
  if (!frame || frame.dataset.stratumFrameProxy !== "true") return;
  const button = mediaControls.get(frame);
  if (button) button.remove();
  removeElementCandidates(frame);
  retirePlayer(frame);
  mediaControls.delete(frame);
  delete frame.dataset.stratumFrameProxy;
}

window.addEventListener("message", (event) => {
  if (!event.data || typeof event.data !== "object") return;
  if (event.data.type === "stratrum-parent-capability-query") {
    scheduleCapabilityAnnouncement();
    return;
  }
  if (event.data.type !== "stratrum-frame-capability") return;
  const frame = frameForWindow(event.source);
  if (!frame) return;
  frameCapabilities.set(frame, { native: event.data.hasNativeMedia === true, custom: event.data.hasCustomPlayer === true });
  if (event.data.hasNativeMedia === true || event.data.hasCustomPlayer !== true) removeFrameProxy(frame);
  else attachControl(frame, { frameProxy: true });
  schedulePositionUpdate();
});

function removeAllControls() {
  closePicker();
  for (const [element, button] of mediaControls) {
    button.remove();
    removeElementCandidates(element);
    retirePlayer(element);
    if (mediaResizeObserver) mediaResizeObserver.unobserve(element);
  }
  mediaControls.clear();
}

function observeDirectPage() {
  const contentType = String(document.contentType || "").toLowerCase();
  if (!/^(?:audio|video)\//.test(contentType)) return;
  const mediaKind = contentType.startsWith("audio/") ? "audio" : "video";
  const topLevelDocument = window.top === window;
  const element = queryAllOpenRoots(mediaKind === "audio" ? "audio" : "video")[0] || queryAllOpenRoots("video, audio")[0];
  if (!element) return;
  if (showMediaButtons) attachControl(element);
  const context = playerContext(element);
  reportPlayerState(element, "direct-media-document", false);
  reportCandidate(rawCandidate(window.location.href, mediaKind, topLevelDocument ? "top-level-media-document" : "frame-document-url", {
    contentType,
    topLevelDocument,
    title: pageTitle(),
    ...context
  }));
}

function handleNavigation() {
  if (lastPageUrl === window.location.href) return;
  lastPageUrl = window.location.href;
  pageGeneration += 1;
  closePicker();
  for (const element of mediaControls.keys()) {
    removeElementCandidates(element);
    retirePlayer(element);
    elementPlayerIds.set(element, newPlayerId());
    elementSourceKeys.set(element, sourceFingerprint(element));
    elementEvidence.set(element, "dom-media");
  }
  extensionApi.runtime.sendMessage({ type: "stratrum-frame-page", pageUrl: window.location.href, documentGeneration: pageGeneration }).catch(() => {});
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
  extensionApi.runtime.sendMessage({ type: "stratrum-frame-page", pageUrl: window.location.href, documentGeneration: pageGeneration }).catch(() => {});
  domObserver = new MutationObserver((mutations) => {
    if (!showMediaButtons) return;
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(scanNode);
      if (mutation.type === "attributes") {
        const target = mutation.target.tagName === "SOURCE" ? mutation.target.closest("video, audio") : mutation.target;
        if (target && mediaControls.has(target) && ["src", "poster"].includes(mutation.attributeName)) {
          refreshPlayerOwnership(target);
          elementEvidence.set(target, "source-change");
          reportPlayerState(target, "source-change", true);
        }
      }
    }
    schedulePositionUpdate();
    scheduleCapabilityAnnouncement();
  });
  observeRoot(document.documentElement);
  extensionApi.storage.local.get(["showMediaButtons"]).then((stored) => {
    showMediaButtons = stored.showMediaButtons !== false;
    observeDirectPage();
    if (showMediaButtons) scanNode(document.documentElement);
    capabilityReady = true;
    scheduleCapabilityAnnouncement();
  });

  document.addEventListener("loadstart", (event) => {
    if (event.target instanceof HTMLMediaElement && mediaControls.has(event.target)) {
      refreshPlayerOwnership(event.target);
      elementEvidence.set(event.target, "currentSrc-change");
      reportPlayerState(event.target, "loadstart", true);
      schedulePositionUpdate();
    }
  }, true);
  document.addEventListener("loadedmetadata", (event) => {
    if (event.target instanceof HTMLMediaElement && mediaControls.has(event.target)) {
      reportPlayerState(event.target, "loadedmetadata", true);
      schedulePositionUpdate();
    }
  }, true);
  for (const activity of ["play", "playing"]) {
    document.addEventListener(activity, (event) => {
      if (event.target instanceof HTMLMediaElement && mediaControls.has(event.target)) {
        reportPlayerState(event.target, activity, true);
        observeElement(event.target, activity);
      }
    }, true);
  }
  document.addEventListener("encrypted", (event) => {
    if (!(event.target instanceof HTMLMediaElement)) return;
    drmMedia.add(event.target);
    extensionApi.runtime.sendMessage({ type: "stratrum-frame-blocked" }).catch(() => {});
    showStatus("DRM or access-controlled media is not supported.");
    removeElementCandidates(event.target);
    retirePlayer(event.target);
    const button = mediaControls.get(event.target);
    if (button) button.remove();
    if (mediaResizeObserver) mediaResizeObserver.unobserve(event.target);
    mediaControls.delete(event.target);
  }, true);

  if (typeof PerformanceObserver === "function") {
    try {
      const performanceObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          extensionApi.runtime.sendMessage({
            type: "stratrum-network-evidence", candidate: rawCandidate(entry.name, null, "performance-resource", {
              documentGeneration: pageGeneration, observedAt: Date.now(), documentUrl: window.location.href,
              initiator: window.location.origin, requestContext: { userAgent: String(navigator.userAgent || "").slice(0, 512) }
            })
          }).catch(() => {});
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
    if (message && message.type === "stratrum-status") showStatus(message.message, message.success ? "success" : "error");
  });
  installNavigationHooks();
  window.addEventListener("scroll", schedulePositionUpdate, { passive: true });
  window.addEventListener("resize", schedulePositionUpdate, { passive: true });
}
