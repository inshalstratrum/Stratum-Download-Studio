const extensionApi = globalThis.browser || globalThis.chrome;

document.addEventListener("DOMContentLoaded", async () => {
  const result = await extensionApi.storage.local.get(["authToken", "showMediaButtons", "primaryAction"]);
  if (result.authToken) {
    document.getElementById("token").placeholder = "A token is currently saved";
  }
  document.getElementById("show-media-buttons").checked = result.showMediaButtons !== false;
  document.getElementById("primary-action").value = result.primaryAction === "download_with_options" ? "download_with_options" : "quick_download";
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

document.getElementById("primary-action").addEventListener("change", async (event) => {
  await extensionApi.storage.local.set({ primaryAction: event.target.value });
});
