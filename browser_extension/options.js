const extensionApi = globalThis.browser || globalThis.chrome;

document.addEventListener("DOMContentLoaded", async () => {
  const result = await extensionApi.storage.local.get(["authToken", "showMediaButtons", "interceptGeneralDownloads"]);
  if (result.authToken) {
    document.getElementById("token").placeholder = "A token is currently saved";
  }
  document.getElementById("show-media-buttons").checked = result.showMediaButtons !== false;
  document.getElementById("intercept-general-files").checked = result.interceptGeneralDownloads === true;
});

document.getElementById("paste-connect").addEventListener("click", async () => {
  const status = document.getElementById("status");
  try {
    // Clipboard read only on an explicit click in the extension's own page.
    const token = (await navigator.clipboard.readText()).trim();
    if (!/^[a-fA-F0-9]{64}$/.test(token)) {
      status.style.color = "#9c3344";
      status.textContent = "Copy Token in I-DS desktop, then click Connect here.";
      return;
    }
    await extensionApi.storage.local.set({ authToken: token });
    document.getElementById("token").placeholder = "A token is currently saved";
    status.style.color = "#087e86";
    status.textContent = "Pairing token saved. Try a download to check the connection.";
  } catch (error) {
    status.style.color = "#9c3344";
    status.textContent = "Clipboard access unavailable. Paste the token manually below.";
  }
});

document.getElementById("toggle-visibility").addEventListener("click", () => {
  const tokenInput = document.getElementById("token");
  const toggleButton = document.getElementById("toggle-visibility");
  const reveal = tokenInput.type === "password";
  tokenInput.type = reveal ? "text" : "password";
  toggleButton.textContent = reveal ? "Hide" : "Show";
});

document.getElementById("save").addEventListener("click", async () => {
  const tokenInput = document.getElementById("token");
  const token = tokenInput.value.trim();
  const status = document.getElementById("status");
  if (!/^[a-fA-F0-9]{64}$/.test(token)) {
    status.style.color = "#d13438";
    status.textContent = "Error: Token must be exactly 64 hexadecimal characters.";
    return;
  }
  await extensionApi.storage.local.set({ authToken: token });
  status.style.color = "green";
  status.textContent = "Token saved successfully.";
  tokenInput.value = "";
  tokenInput.placeholder = "A token is currently saved";
  setTimeout(() => { status.textContent = ""; }, 2000);
});

document.getElementById("clear").addEventListener("click", async () => {
  await extensionApi.storage.local.remove("authToken");
  const tokenInput = document.getElementById("token");
  const status = document.getElementById("status");
  tokenInput.value = "";
  tokenInput.placeholder = "Paste 64-character hex token here";
  status.style.color = "#d13438";
  status.textContent = "Token cleared.";
  setTimeout(() => { status.textContent = ""; }, 2000);
});

document.getElementById("show-media-buttons").addEventListener("change", async (event) => {
  await extensionApi.storage.local.set({ showMediaButtons: event.target.checked });
});

// Explicit opt-in: the browser keeps its native downloader until this is enabled.
document.getElementById("intercept-general-files").addEventListener("change", async (event) => {
  await extensionApi.storage.local.set({ interceptGeneralDownloads: event.target.checked });
  const status = document.getElementById("status");
  status.style.color = "#16635a";
  status.textContent = event.target.checked ? "Automatic file handoff enabled." : "Chrome will handle ordinary files normally.";
});
