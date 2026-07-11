// 1. Right-Click Menu Setup
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "download-stratrum",
    title: "Download with Stratrum Download Studio",
    contexts: ["link", "video", "audio"]
  });
});

// 2. Listen for Right-Clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "download-stratrum") {
    const targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;
    sendToDesktopApp(targetUrl);
  }
});

// 3. The actual function that talks to Python
async function sendToDesktopApp(url) {
  try {
    const data = await chrome.storage.local.get(['authToken']);
    const token = data.authToken || '';
    if (!token) {
        console.error("No auth token configured. Please check Options.");
        return false;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5-second timeout

    let response = await fetch("http://127.0.0.1:8000/add_download", {
      method: "POST",
      headers: { 
          "Content-Type": "application/json",
          "X-Stratrum-Auth": token
      },
      body: JSON.stringify({ url: url }),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
        console.error("Desktop app rejected request:", response.status);
    } else {
        console.log("Sent to Stratrum Download Studio!");
    }
    return response.ok;
  } catch (err) {
    console.error("Failed to connect to Stratrum Download Studio.", err);
    return false;
  }
}