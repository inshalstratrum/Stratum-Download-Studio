if (!globalThis.StratumMediaCandidates && typeof importScripts === "function") {
  importScripts("media_candidates.js");
}

const extensionApi = globalThis.browser || globalThis.chrome;
const candidateApi = globalThis.StratumMediaCandidates;
const candidateStore = new candidateApi.CandidateStore({ maxCandidates: 200, ttlMs: 30 * 60 * 1000 });
const framePageUrls = new Map();
const blockedFrames = new Set();
const playerOwners = new candidateApi.PlayerOwnershipStore(400);
const DESKTOP_ENDPOINT = "http://127.0.0.1:8000/add_download";

extensionApi.runtime.onInstalled.addListener(async () => {
  await extensionApi.contextMenus.removeAll();
  extensionApi.contextMenus.create({
    id: "quick-download-stratum",
    title: "Quick Download with Stratum Download Studio",
    contexts: ["link", "video", "audio"]
  });
  extensionApi.contextMenus.create({
    id: "download-options-stratum",
    title: "Download with Options in Stratum Download Studio",
    contexts: ["link", "video", "audio"]
  });
});

async function readLocalStorage(keys) {
  return await extensionApi.storage.local.get(keys);
}

async function sendToDesktopApp(url, action) {
  const safeUrl = candidateApi.safeUrl(url);
  if (!safeUrl) {
    return { success: false, code: "invalid_url", message: "Stratum rejected an unsafe or unsupported URL." };
  }
  const stored = await readLocalStorage(["authToken"]);
  const token = stored.authToken || "";
  if (!token) {
    return {
      success: false,
      code: "missing_token",
      message: "Open Stratum extension Options and save the desktop authentication token."
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(DESKTOP_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Stratrum-Auth": token
      },
      body: JSON.stringify({ url: safeUrl.href, action }),
      signal: controller.signal
    });

    if (response.ok) {
      return { success: true, message: "Sent to Stratum Download Studio." };
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
      message: "Stratum Download Studio is unavailable. Start the desktop app and try again."
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
  if (!candidateApi.validPlayerId(playerId)) return null;
  const pageUrl = bindFramePage(tabId, frameId, trustedSenderPage(message.candidate && message.candidate.pageUrl, sender));
  if (!bindPlayerOwner(tabId, frameId, playerId, pageUrl)) return null;
  return candidateStore.observe(candidateApi.applyTrustedOwner({ ...message.candidate, pageUrl }, tabId, frameId, playerId));
}

function frameKey(tabId, frameId) {
  return `${tabId}:${frameId}`;
}

function bindPlayerOwner(tabId, frameId, playerId, pageUrl) {
  const before = playerOwners.playerIds(tabId, frameId, pageUrl).length;
  const bound = playerOwners.bind(tabId, frameId, playerId, pageUrl);
  if (bound && before === 1 && playerOwners.playerIds(tabId, frameId, pageUrl).length === 2) candidateStore.removeFrameNetwork(tabId, frameId);
  return bound;
}

function ownsPlayer(tabId, frameId, playerId, pageUrl) {
  return playerOwners.owns(tabId, frameId, playerId, pageUrl);
}

function removeFrameOwners(tabId, frameId) {
  playerOwners.removeFrame(tabId, frameId);
}

function trustedSenderPage(requestedPageUrl, sender) {
  const senderUrl = candidateApi.safeUrl(sender && sender.url || "");
  const requested = candidateApi.safeUrl(requestedPageUrl || "");
  if (senderUrl && requested && senderUrl.origin === requested.origin) return requested.href;
  if (senderUrl) return senderUrl.href;
  if (sender && sender.frameId === 0 && sender.tab) return sender.tab.url;
  return null;
}

function bindFramePage(tabId, frameId, pageUrl) {
  const stable = candidateApi.stablePageUrl(pageUrl || "");
  if (!stable) return framePageUrls.get(frameKey(tabId, frameId)) || null;
  const key = frameKey(tabId, frameId);
  const previous = framePageUrls.get(key);
  if (!previous) candidateStore.reassignFramePage(tabId, frameId, stable);
  else if (previous !== stable) {
    candidateStore.removeFrame(tabId, frameId);
    removeFrameOwners(tabId, frameId);
    blockedFrames.delete(key);
  }
  framePageUrls.set(key, stable);
  return stable;
}

extensionApi.contextMenus.onClicked.addListener(async (info, tab) => {
  const actions = {
    "quick-download-stratum": "quick_download",
    "download-options-stratum": "download_with_options"
  };
  if (!actions[info.menuItemId]) {
    return;
  }
  const targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;
  const result = await sendToDesktopApp(targetUrl, actions[info.menuItemId]);
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
    bindFramePage(tabId, frameId, trustedSenderPage(message.pageUrl, sender));
    sendResponse({ success: true });
    return false;
  }
  if (message.type === "stratrum-get-candidates") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    const pageUrl = bindFramePage(tabId, frameId, trustedSenderPage(message.pageUrl, sender));
    const playerId = message.playerId;
    sendResponse({ candidates: blockedFrames.has(frameKey(tabId, frameId)) || !ownsPlayer(tabId, frameId, playerId, pageUrl) ? [] : candidateStore.list({ tabId, frameId, pageUrl, playerId }) });
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
    if (ownsPlayer(tabId, frameId, message.playerId, pageUrl)) candidateStore.removeIds(message.ids, { tabId, frameId, playerId: message.playerId });
    sendResponse({ success: true });
    return false;
  }
  if (message.type === "stratrum-download-request") {
    const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : -1;
    const frameId = sender && Number.isInteger(sender.frameId) ? sender.frameId : 0;
    const pageUrl = framePageUrls.get(frameKey(tabId, frameId)) || null;
    const selected = ownsPlayer(tabId, frameId, message.playerId, pageUrl)
      ? candidateStore.list({ tabId, frameId, pageUrl, playerId: message.playerId }).find((candidate) => candidate.id === message.candidateId)
      : null;
    if (!selected) {
      sendResponse({ success: false, code: "invalid_candidate", message: "No complete downloadable media detected." });
      return false;
    }
    sendToDesktopApp(selected.url, "default").then(sendResponse);
    return true;
  }
  return false;
});

if (extensionApi.tabs && extensionApi.tabs.onRemoved) {
  extensionApi.tabs.onRemoved.addListener((tabId) => {
    candidateStore.removeTab(tabId);
    for (const key of framePageUrls.keys()) if (key.startsWith(`${tabId}:`)) framePageUrls.delete(key);
    for (const key of blockedFrames) if (key.startsWith(`${tabId}:`)) blockedFrames.delete(key);
    playerOwners.removeTab(tabId);
  });
}

if (extensionApi.webRequest && extensionApi.webRequest.onHeadersReceived) {
  extensionApi.webRequest.onHeadersReceived.addListener((details) => {
    if (details.tabId < 0 || candidateApi.isSegmentUrl(details.url)) return;
    const frameId = Number.isInteger(details.frameId) ? details.frameId : 0;
    const isFrameDocument = details.type === "main_frame" || details.type === "sub_frame";
    if (isFrameDocument) blockedFrames.delete(frameKey(details.tabId, frameId));
    if (isFrameDocument) bindFramePage(details.tabId, frameId, details.url);
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
    const pageUrl = isFrameDocument ? details.url : framePageUrls.get(frameKey(details.tabId, frameId)) || details.documentUrl || details.initiator || details.url;
    const players = playerOwners.playerIds(details.tabId, frameId, pageUrl);
    if (players.length !== 1) return;
    candidateStore.observe({
      tabId: details.tabId,
      frameId,
      playerId: players[0],
      pageUrl,
      url: details.url,
      contentType,
      contentDisposition,
      contentRange,
      statusCode: details.statusCode,
      requestType: details.type,
      topLevelDocument: details.type === "main_frame",
      evidence: details.type === "main_frame" ? "webRequest-main-frame" : "webRequest-response"
    });
  }, { urls: ["http://*/*", "https://*/*"] }, ["responseHeaders"]);
}
