const extensionApi = globalThis.browser || globalThis.chrome;
const DESKTOP_ENDPOINT = "http://127.0.0.1:8000/add_download";

extensionApi.runtime.onInstalled.addListener(async () => {
  await extensionApi.contextMenus.removeAll();
  extensionApi.contextMenus.create({
    id: "download-stratrum",
    title: "Download with Stratrum Download Studio",
    contexts: ["link", "video", "audio"]
  });
});

async function readLocalStorage(keys) {
  return await extensionApi.storage.local.get(keys);
}

async function sendToDesktopApp(url) {
  const stored = await readLocalStorage(["authToken"]);
  const token = stored.authToken || "";
  if (!token) {
    return {
      success: false,
      code: "missing_token",
      message: "Open Stratrum extension Options and save the desktop authentication token."
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
      body: JSON.stringify({ url }),
      signal: controller.signal
    });

    if (response.ok) {
      return { success: true, message: "Sent to Stratrum Download Studio." };
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
      message: "Stratrum Download Studio is unavailable. Start the desktop app and try again."
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
      // Some restricted pages cannot host content scripts.
    }
  }
  if (result.code === "missing_token") {
    await extensionApi.runtime.openOptionsPage();
  }
}

extensionApi.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "download-stratrum") {
    return;
  }
  const targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;
  const result = await sendToDesktopApp(targetUrl);
  await showResultInTab(tab && tab.id, result);
});

extensionApi.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "stratrum-download-request") {
    return false;
  }
  sendToDesktopApp(message.url).then(sendResponse);
  return true;
});
