const extensionApi = globalThis.browser || globalThis.chrome;
const mediaButtons = new Map();
let showMediaButtons = true;
let positionFrame = null;

function supportedPageUrl() {
  return window.location.protocol === "http:" || window.location.protocol === "https:";
}

function chooseDownloadUrl(mediaElement) {
  if (mediaElement.srcObject) {
    return supportedPageUrl() ? window.location.href : null;
  }
  const candidate = mediaElement.currentSrc || mediaElement.src || "";
  try {
    const resolved = new URL(candidate, document.baseURI);
    const segmentedPath = /\.(?:m3u8|mpd|m4s)(?:$|[?#])/i.test(resolved.href);
    const segmentedType = Array.from(mediaElement.querySelectorAll("source")).some((source) =>
      /mpegurl|dash\+xml/i.test(source.type || "")
    );
    if ((resolved.protocol === "http:" || resolved.protocol === "https:") && !segmentedPath && !segmentedType) {
      return resolved.href;
    }
  } catch (error) {
    // Blob, MediaSource, segmented, empty, and malformed sources fall back to the page.
  }
  return supportedPageUrl() ? window.location.href : null;
}

function showStatus(message, success = false) {
  const existing = document.getElementById("stratrum-extension-status");
  if (existing) {
    existing.remove();
  }
  const status = document.createElement("div");
  status.id = "stratrum-extension-status";
  status.textContent = message;
  Object.assign(status.style, {
    position: "fixed",
    right: "16px",
    bottom: "16px",
    zIndex: "2147483647",
    maxWidth: "360px",
    padding: "10px 12px",
    borderRadius: "6px",
    color: "#ffffff",
    background: success ? "#107c10" : "#a4262c",
    boxShadow: "0 4px 14px rgba(0,0,0,.3)",
    font: "13px/1.4 system-ui, sans-serif"
  });
  document.documentElement.appendChild(status);
  setTimeout(() => status.remove(), 6000);
}

async function requestDownload(mediaElement, button) {
  const url = chooseDownloadUrl(mediaElement);
  if (!url) {
    showStatus("This page type is not supported by Stratrum.");
    return;
  }
  const originalText = button.textContent;
  button.textContent = "Sending…";
  button.disabled = true;
  try {
    const result = await extensionApi.runtime.sendMessage({
      type: "stratrum-download-request",
      url
    });
    showStatus(result && result.message ? result.message : "The extension did not receive a response.", Boolean(result && result.success));
    button.textContent = result && result.success ? "Sent ✓" : originalText;
  } catch (error) {
    showStatus("Stratrum extension communication failed. Open extension Options and try again.");
    button.textContent = originalText;
  } finally {
    button.disabled = false;
    setTimeout(() => {
      if (button.isConnected) {
        button.textContent = originalText;
      }
    }, 2000);
  }
}

function positionButtons() {
  positionFrame = null;
  for (const [mediaElement, button] of mediaButtons) {
    if (!mediaElement.isConnected) {
      button.remove();
      mediaButtons.delete(mediaElement);
      continue;
    }
    const rect = mediaElement.getBoundingClientRect();
    button.hidden = rect.width < 80 || rect.height < 45;
    if (!button.hidden) {
      button.style.top = `${Math.max(4, rect.top + window.scrollY + 8)}px`;
      button.style.left = `${Math.max(4, rect.right + window.scrollX - button.offsetWidth - 8)}px`;
    }
  }
}

function schedulePositionUpdate() {
  if (positionFrame === null) {
    positionFrame = window.requestAnimationFrame(positionButtons);
  }
}

function attachButton(mediaElement) {
  if (!showMediaButtons || mediaButtons.has(mediaElement) || !mediaElement.isConnected) {
    return;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "↓ Stratrum";
  button.setAttribute("aria-label", "Send this media to Stratrum Download Studio");
  Object.assign(button.style, {
    position: "absolute",
    zIndex: "2147483646",
    padding: "5px 9px",
    border: "1px solid #ffffff",
    borderRadius: "5px",
    color: "#ffffff",
    background: "#0067b8",
    boxShadow: "0 2px 8px rgba(0,0,0,.35)",
    cursor: "pointer",
    font: "600 12px/1.2 system-ui, sans-serif"
  });
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    requestDownload(mediaElement, button);
  });
  document.documentElement.appendChild(button);
  mediaButtons.set(mediaElement, button);
  schedulePositionUpdate();
}

function scanNode(node) {
  if (!showMediaButtons || !(node instanceof Element)) {
    return;
  }
  if (node.matches("video, audio")) {
    attachButton(node);
  }
  node.querySelectorAll("video, audio").forEach(attachButton);
}

function removeAllButtons() {
  for (const button of mediaButtons.values()) {
    button.remove();
  }
  mediaButtons.clear();
}

if (supportedPageUrl()) {
  extensionApi.storage.local.get(["showMediaButtons"]).then((stored) => {
    showMediaButtons = stored.showMediaButtons !== false;
    if (showMediaButtons) {
      scanNode(document.documentElement);
    }
  });

  const observer = new MutationObserver((mutations) => {
    if (!showMediaButtons) {
      return;
    }
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(scanNode);
    }
    schedulePositionUpdate();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  extensionApi.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "local" || !changes.showMediaButtons) {
      return;
    }
    showMediaButtons = changes.showMediaButtons.newValue !== false;
    if (showMediaButtons) {
      scanNode(document.documentElement);
    } else {
      removeAllButtons();
    }
  });

  extensionApi.runtime.onMessage.addListener((message) => {
    if (message && message.type === "stratrum-status") {
      showStatus(message.message, Boolean(message.success));
    }
  });
  window.addEventListener("scroll", schedulePositionUpdate, { passive: true });
  window.addEventListener("resize", schedulePositionUpdate, { passive: true });
}
