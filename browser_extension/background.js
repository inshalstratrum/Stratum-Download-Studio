if (!globalThis.StratumMediaCandidates && typeof importScripts === "function") {
  importScripts("media_candidates.js", "file_interception.js");
}

const extensionApi = globalThis.browser || globalThis.chrome;
const candidateApi = globalThis.StratumMediaCandidates;
const fileInterceptApi = globalThis.IDSFileInterception;
const candidateStore = new candidateApi.CandidateStore({ maxCandidates: 200, ttlMs: 30 * 60 * 1000 });
const framePageUrls = new Map();
const frameGenerations = new Map();
const blockedFrames = new Set();
const playerRegistry = new candidateApi.PlayerRegistry({ maxOwners: 400, ttlMs: 2 * 60 * 1000, leaseMs: 15 * 1000 });
const quarantineStore = new candidateApi.QuarantineStore({ maxItems: 100, ttlMs: 30 * 1000 });
const DESKTOP_ENDPOINT = "http://127.0.0.1:18765/add_download";

extensionApi.runtime.onInstalled.addListener(async () => {
  await extensionApi.contextMenus.removeAll();
  extensionApi.contextMenus.create({
    id: "quick-download-stratum",
    title: "Quick Download with I-DS",
    contexts: ["link", "video", "audio"]
  });
  extensionApi.contextMenus.create({
    id: "download-file-i-ds",
    title: "Download file with I-DS",
    contexts: ["link"]
  });
  extensionApi.contextMenus.create({
    id: "download-options-stratum",
    title: "Download with Options in I-DS",
    contexts: ["link", "video", "audio"]
  });
});

// The toolbar mark opens pairing/settings; it never starts a download by itself.
if (extensionApi.action && extensionApi.action.onClicked) {
  extensionApi.action.onClicked.addListener(() => extensionApi.runtime.openOptionsPage());
}

async function readLocalStorage(keys) {
  return await extensionApi.storage.local.get(keys);
}

async function sendToDesktopApp(url, action, handoff = {}) {
  const safeUrl = candidateApi.safeUrl(url);
  if (!safeUrl) {
    return { success: false, code: "invalid_url", message: "I-DS rejected an unsupported URL." };
  }
  const stored = await readLocalStorage(["authToken"]);
  const token = stored.authToken || "";
  if (!token) {
    return {
      success: false,
      code: "missing_token",
      message: "Open I-DS extension Options and save the desktop pairing token."
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 9000);
  try {
    const response = await fetch(DESKTOP_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Stratrum-Auth": token
      },
      body: JSON.stringify({
        url: safeUrl.href, action,
        fileName: handoff.fileName || "",
        sourcePage: handoff.sourcePage || "",
        contentType: handoff.contentType || "",
        requestContext: handoff.requestContext || {}
      }),
      signal: controller.signal
    });

    if (response.ok) {
      // A different local service can occupy a port. Only trust our expected acknowledgment.
      let reply = null;
      try {
        reply = await response.json();
      } catch (error) {
        return { success: false, code: "invalid_bridge_response", message: "The local endpoint is not responding as I-DS. Restart the desktop app." };
      }
      if (reply && reply.status === "success") {
        return { success: true, message: "Sent to I-DS." };
      }
      return { success: false, code: "invalid_bridge_response", message: "The local endpoint did not confirm an I-DS download." };
    }
    if (response.status === 403) {
      return {
        success: false,
        code: "pairing_rejected",
        message: "Browser pairing was rejected. Reset browser pairing in desktop Options, then try again."
      };
    }
    if (response.status === 401) {
      return {
        success: false,
        code: "unauthorized",
        message: "The saved token was rejected. Copy the current token from desktop Options."
      };
    }
    return {
      success: false,
      code: "request_rejected",
      message: `The desktop app rejected the request (${response.status}).`
    };
  } catch (error) {
    return {
      success: false,
      code: "desktop_unavailable",
      message: "I-DS is unavailable. Start the desktop app and try again."
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

async function showResultInTab(tabId, result) {
  if (Number.isInteger(tabId)) {
    try {
      await extensionApi.tabs.sendMessage(tabId, {
        type: "stratrum-status",
        success: result.success,
        message: result.message
      });
    } catch (error) {
      // Restricted pages and frames may not host content scripts.
    }
  }
  if (result.code === "missing_token") {
    await extensionApi.runtime.openOptionsPage();
  }
}

function observeFromMessage(message, sender) {
  const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
  const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
  if (blockedFrames.has(frameKey(tabId, frameId))) return null;
  const playerId = message.candidate && message.candidate.playerId;
  const documentGeneration = Number.isInteger(message.candidate && message.candidate.documentGeneration) ? message.candidate.documentGeneration : -1;
  if (!candidateApi.validPlayerId(playerId)) return null;
  const pageUrl = bindFramePage(tabId, frameId, trustedSenderPage(message.candidate && message.candidate.pageUrl, sender), documentGeneration);
  if (!playerRegistry.touch({
    tabId, frameId, documentGeneration, playerId, pageUrl,
    visible: message.candidate.visiblePlayer,
    active: message.candidate.evidence === "control-click" ? true : undefined,
    sourceHints: message.candidate.sourceHints,
    permalink: message.candidate.nearestPermalink
  })) return null;
  return candidateStore.observe(candidateApi.applyTrustedOwner({ ...message.candidate, pageUrl }, tabId, frameId, playerId, documentGeneration));
}

function frameKey(tabId, frameId) {
  return `${tabId}:${frameId}`;
}

function ownsPlayer(tabId, frameId, documentGeneration, playerId, pageUrl) {
  return playerRegistry.owns(tabId, frameId, documentGeneration, playerId, pageUrl);
}

function removeFrameOwners(tabId, frameId) {
  playerRegistry.removeFrame(tabId, frameId);
  quarantineStore.removeFrame(tabId, frameId);
}

function trustedSenderPage(requestedPageUrl, sender) {
  const senderUrl = candidateApi.safeUrl(sender && sender.url || "");
  const requested = candidateApi.safeUrl(requestedPageUrl || "");
  if (senderUrl && requested && senderUrl.origin === requested.origin) return requested.href;
  if (senderUrl) return senderUrl.href;
  if (sender && sender.frameId === 0 && sender.tab) return sender.tab.url;
  return null;
}

function bindFramePage(tabId, frameId, pageUrl, documentGeneration) {
  const stable = candidateApi.stablePageUrl(pageUrl || "");
  if (!stable) return framePageUrls.get(frameKey(tabId, frameId)) || null;
  const key = frameKey(tabId, frameId);
  const previous = framePageUrls.get(key);
  const previousGeneration = frameGenerations.get(key);
  if (!previous) candidateStore.reassignFramePage(tabId, frameId, stable);
  else if (previous !== stable || (Number.isInteger(documentGeneration) && previousGeneration !== documentGeneration)) {
    candidateStore.removeFrame(tabId, frameId);
    removeFrameOwners(tabId, frameId);
    blockedFrames.delete(key);
  }
  framePageUrls.set(key, stable);
  if (Number.isInteger(documentGeneration)) frameGenerations.set(key, documentGeneration);
  return stable;
}

function trustedHandoff(candidate, pageUrl) {
  const page = candidateApi.safeUrl(pageUrl || "");
  const source = candidateApi.safeUrl(candidate && candidate.sourcePage || "");
  const platform = (url) => {
    const host = url.hostname.toLowerCase().replace(/^www\.|^m\./, "");
    return ["facebook.com", "instagram.com", "tiktok.com", "dailymotion.com", "x.com", "twitter.com"].find((domain) => host === domain || host.endsWith(`.${domain}`)) || "";
  };
  const provenanceAllowed = Boolean(page && source && (page.origin === source.origin || (platform(page) && platform(page) === platform(source)) || (candidateApi.isExtractorPage(page.href) && candidateApi.isExtractorPage(source.href))));
  const sourcePage = provenanceAllowed ? source.href : page ? page.href : "";
  const candidateContext = candidate && candidate.requestContext || {};
  const userAgent = candidateContext.userAgent || (globalThis.navigator && navigator.userAgent) || "";
  return {
    sourcePage,
    contentType: String(candidate && candidate.contentType || "").slice(0, 120),
    requestContext: candidateApi.sanitizeRequestContext({ ...candidateContext, userAgent }, sourcePage)
  };
}

function observeNetworkEvidence(raw, tabId, frameId) {
  const key = frameKey(tabId, frameId);
  const pageUrl = framePageUrls.get(key) || candidateApi.stablePageUrl(raw.pageUrl || raw.documentUrl || raw.initiator || "");
  const documentGeneration = frameGenerations.get(key);
  const playerId = playerRegistry.correlate({
    tabId, frameId, documentGeneration, pageUrl,
    documentUrl: raw.documentUrl, initiator: raw.initiator, observedAt: raw.observedAt
  });
  if (!playerId) {
    quarantineStore.observe({ ...raw, tabId, frameId, documentGeneration, pageUrl });
    return null;
  }
  return candidateStore.observe(candidateApi.applyTrustedOwner({ ...raw, pageUrl }, tabId, frameId, playerId, documentGeneration));
}

function promoteQuarantinedEvidence(tabId, frameId, documentGeneration, playerId, pageUrl) {
  const promoted = [];
  const matches = quarantineStore.takeMatching(
    { tabId, frameId, documentGeneration, pageUrl },
    (item) => playerRegistry.evidenceMatches(tabId, frameId, documentGeneration, playerId, item)
  );
  for (const item of matches) {
    const evidence = Array.isArray(item.evidence) ? item.evidence.concat("quarantine-promoted") : [item.evidence, "quarantine-promoted"];
    const candidate = candidateStore.observe(candidateApi.applyTrustedOwner({ ...item, pageUrl, evidence }, tabId, frameId, playerId, documentGeneration));
    if (candidate) promoted.push(candidate);
  }
  return promoted;
}

extensionApi.contextMenus.onClicked.addListener(async (info, tab) => {
  const actions = {
    "quick-download-stratum": "quick_download",
    "download-options-stratum": "download_with_options",
    "download-file-i-ds": "http_download"
  };
  if (!actions[info.menuItemId]) {
    return;
  }
  const targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;
  const result = await sendToDesktopApp(targetUrl, actions[info.menuItemId], {
    sourcePage: candidateApi.stablePageUrl(info.pageUrl || targetUrl) || "",
    contentType: "",
    requestContext: candidateApi.sanitizeRequestContext({}, info.pageUrl || targetUrl)
  });
  await showResultInTab(tab && tab.id, result);
});

extensionApi.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;
  if (message.type === "stratrum-candidate-observed") {
    sendResponse({ candidate: observeFromMessage(message, sender) });
    return false;
  }
  if (message.type === "stratrum-frame-page") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    bindFramePage(tabId, frameId, trustedSenderPage(message.pageUrl, sender), message.documentGeneration);
    sendResponse({ success: true });
    return false;
  }
  if (message.type === "stratrum-player-state") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    const pageUrl = bindFramePage(tabId, frameId, trustedSenderPage(message.pageUrl, sender), message.documentGeneration);
    const success = playerRegistry.touch({
      tabId, frameId, documentGeneration: message.documentGeneration, playerId: message.playerId,
      pageUrl, visible: message.visible, active: message.active, activity: message.activity,
      sourceHints: message.sourceHints, permalink: message.permalink
    });
    const promoted = success && message.active ? promoteQuarantinedEvidence(tabId, frameId, message.documentGeneration, message.playerId, pageUrl) : [];
    sendResponse({ success, promoted: promoted.length });
    return false;
  }
  if (message.type === "stratrum-player-removed") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    playerRegistry.removePlayer(tabId, frameId, message.documentGeneration, message.playerId);
    candidateStore.removePlayer(tabId, frameId, message.documentGeneration, message.playerId);
    sendResponse({ success: true });
    return false;
  }
  if (message.type === "stratrum-network-evidence") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    sendResponse({ candidate: blockedFrames.has(frameKey(tabId, frameId)) ? null : observeNetworkEvidence({ ...message.candidate, pageUrl: trustedSenderPage(message.candidate && message.candidate.pageUrl, sender) }, tabId, frameId) });
    return false;
  }
  if (message.type === "stratrum-get-candidates") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    const pageUrl = bindFramePage(tabId, frameId, trustedSenderPage(message.pageUrl, sender), message.documentGeneration);
    const playerId = message.playerId;
    sendResponse({ candidates: blockedFrames.has(frameKey(tabId, frameId)) || !ownsPlayer(tabId, frameId, message.documentGeneration, playerId, pageUrl) ? [] : candidateStore.list({ tabId, frameId, documentGeneration: message.documentGeneration, pageUrl, playerId }) });
    return false;
  }
  if (message.type === "stratrum-frame-blocked") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    blockedFrames.add(frameKey(tabId, frameId));
    candidateStore.removeFrame(tabId, frameId);
    removeFrameOwners(tabId, frameId);
    sendResponse({ success: true });
    return false;
  }
  if (message.type === "stratrum-remove-candidates") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    const pageUrl = framePageUrls.get(frameKey(tabId, frameId)) || null;
    if (ownsPlayer(tabId, frameId, message.documentGeneration, message.playerId, pageUrl)) candidateStore.removeIds(message.ids, { tabId, frameId, documentGeneration: message.documentGeneration, playerId: message.playerId });
    sendResponse({ success: true });
    return false;
  }
  if (message.type === "stratrum-download-request") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    const pageUrl = framePageUrls.get(frameKey(tabId, frameId)) || null;
    const selected = ownsPlayer(tabId, frameId, message.documentGeneration, message.playerId, pageUrl)
      ? candidateStore.list({ tabId, frameId, documentGeneration: message.documentGeneration, pageUrl, playerId: message.playerId }).find((candidate) => candidate.id === message.candidateId)
      : null;
    if (!selected) {
      sendResponse({ success: false, code: "invalid_candidate", message: "No complete downloadable media detected." });
      return false;
    }
    sendToDesktopApp(selected.url, "default", trustedHandoff(selected, pageUrl)).then(sendResponse);
    return true;
  }
  return false;
});

if (extensionApi.tabs && extensionApi.tabs.onRemoved) {
  extensionApi.tabs.onRemoved.addListener((tabId) => {
    candidateStore.removeTab(tabId);
    for (const key of framePageUrls.keys()) if (key.startsWith(`${tabId}:`)) framePageUrls.delete(key);
    for (const key of frameGenerations.keys()) if (key.startsWith(`${tabId}:`)) frameGenerations.delete(key);
    for (const key of blockedFrames) if (key.startsWith(`${tabId}:`)) blockedFrames.delete(key);
    playerRegistry.removeTab(tabId);
    quarantineStore.removeTab(tabId);
  });
}

if (extensionApi.webRequest && extensionApi.webRequest.onHeadersReceived) {
  extensionApi.webRequest.onHeadersReceived.addListener((details) => {
    if (details.tabId < 0 || candidateApi.isSegmentUrl(details.url) || candidateApi.isAdvertisementUrl(details.url)) return;
    const frameId = Number.isInteger(details.frameId) ? details.frameId : 0;
    const isFrameDocument = details.type === "main_frame" || details.type === "sub_frame";
    if (isFrameDocument) blockedFrames.delete(frameKey(details.tabId, frameId));
    if (isFrameDocument) bindFramePage(details.tabId, frameId, details.url, frameGenerations.get(frameKey(details.tabId, frameId)) || 0);
    if (blockedFrames.has(frameKey(details.tabId, frameId))) return;
    const headers = details.responseHeaders || [];
    const headerValue = (name) => {
      const header = headers.find((item) => String(item.name || "").toLowerCase() === name);
      return header ? String(header.value || "") : "";
    };
    const contentType = headerValue("content-type");
    const contentDisposition = headerValue("content-disposition");
    const contentRange = headerValue("content-range");
    if (!candidateApi.isUsefulResponseEvidence(contentType, contentDisposition) && !/\.(?:m3u8|mpd)(?:$|[?#])/i.test(details.url)) return;
    observeNetworkEvidence({
      pageUrl: isFrameDocument ? details.url : framePageUrls.get(frameKey(details.tabId, frameId)) || details.documentUrl || details.initiator || details.url,
      url: details.url,
      contentType,
      contentDisposition,
      contentRange,
      statusCode: details.statusCode,
      requestType: details.type,
      documentUrl: details.documentUrl || "",
      initiator: details.initiator || "",
      observedAt: Date.now(),
      topLevelDocument: details.type === "main_frame",
      evidence: details.type === "main_frame" ? "webRequest-main-frame" : "webRequest-response"
    }, details.tabId, frameId);
  }, { urls: ["http://*/*", "https://*/*"] }, ["responseHeaders"]);
}


// Phase 2B: opt-in native browser handoff. On any failure Chrome keeps its job.
if (extensionApi.downloads && extensionApi.downloads.onCreated && fileInterceptApi) {
  const PENDING_IDS = "iDsPausedNativeDownloadIds";
  let pendingWrite = Promise.resolve();

  function rememberPaused(id, add) {
    pendingWrite = pendingWrite.catch(() => {}).then(async () => {
      const state = await readLocalStorage([PENDING_IDS]);
      const list = Array.isArray(state[PENDING_IDS]) ? state[PENDING_IDS].filter(Number.isInteger) : [];
      const next = add ? Array.from(new Set([...list, id])).slice(-100) : list.filter((value) => value !== id);
      await extensionApi.storage.local.set({ [PENDING_IDS]: next });
    });
    return pendingWrite;
  }

  async function findNativeDownload(id) {
    const records = await extensionApi.downloads.search({ id });
    return Array.isArray(records) ? records[0] : null;
  }

  async function recoverPausedNativeDownloads() {
    const values = await readLocalStorage([PENDING_IDS]);
    const ids = Array.isArray(values[PENDING_IDS]) ? values[PENDING_IDS] : [];
    for (const id of ids) {
      try {
        const item = await findNativeDownload(id);
        if (item && item.state === "in_progress" && item.paused) {
          await extensionApi.downloads.resume(id);
        }
      } catch (error) {
        // A removed or interrupted native job cannot be resumed.
      } finally {
        await rememberPaused(id, false);
      }
    }
  }

  if (extensionApi.runtime.onStartup) {
    extensionApi.runtime.onStartup.addListener(() => { recoverPausedNativeDownloads().catch(() => {}); });
  }

  extensionApi.downloads.onCreated.addListener(async (item) => {
    if (!fileInterceptApi.eligible(item)) return;
    try {
      const options = await readLocalStorage(["interceptGeneralDownloads"]);
      if (options.interceptGeneralDownloads !== true) return;
      const result = await fileInterceptApi.transfer(item, {
        pause: (id) => extensionApi.downloads.pause(id),
        resume: (id) => extensionApi.downloads.resume(id),
        cancel: (id) => extensionApi.downloads.cancel(id),
        isPaused: async (id) => {
          const current = await findNativeDownload(id);
          return Boolean(current && current.state === "in_progress" && current.paused);
        },
        remember: rememberPaused,
        send: (url, fileName) => sendToDesktopApp(url, "http_download", { fileName }),
      });
      if (result.status === "desktop") {
        await showResultInTab(item.tabId, { success: true, message: "File transferred to I-DS." });
      } else if (result.status === "native") {
        await showResultInTab(item.tabId, { success: false, message: "I-DS handoff unavailable. Chrome download resumed." });
      }
    } catch (error) {
      // The native browser job was never cancelled on this path.
    }
  });
}
