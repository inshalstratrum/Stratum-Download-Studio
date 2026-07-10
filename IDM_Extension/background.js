// 1. Right-Click Menu Setup
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "download-idm",
    title: "Download with IDM Clone",
    contexts: ["link", "video", "audio"]
  });
});

// 2. Listen for Right-Clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "download-idm") {
    const targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;
    sendToDesktopApp(targetUrl);
  }
});

// 3. NEW: Listen for whispers from content.js (the Video Hover Button)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "SEND_TO_IDM") {
    sendToDesktopApp(request.url)
      .then(success => sendResponse({ success: success }));
    return true; // Keeps the communication channel open for the async response
  }
});

// 4. The actual function that talks to Python
async function sendToDesktopApp(url) {
  try {
    let response = await fetch("http://127.0.0.1:8000/add_download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    });
    console.log("Sent to IDM Clone!");
    return response.ok;
  } catch (err) {
    console.error("Failed to connect to IDM Clone.", err);
    return false;
  }
}