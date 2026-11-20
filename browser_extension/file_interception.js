/* I-DS: conservative, opt-in Chrome/Edge ordinary-file handoff.
 * No clipboard, cookies or browser profile data is transferred.
 */
(function (root) {
  "use strict";
  const EXTENSIONS = new Set([
    "pdf", "zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso",
    "exe", "msi", "msix", "apk", "deb", "rpm", "dmg", "pkg",
    "jpg", "jpeg", "png", "gif", "webp", "svg", "bmp",
    "txt", "csv", "json", "xml", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "epub", "sqlite", "db", "psd", "blend", "stl"
  ]);
  function basename(value) {
    if (typeof value !== "string") return "";
    return value.replace(/\\/g, "/").split("/").pop().replace(/[^\x20-\x7e]/g, "_").slice(0, 180);
  }
  function eligible(item) {
    if (!item || !Number.isInteger(item.id) || item.id < 0 ||
        item.byExtensionId || item.state !== "in_progress" || item.paused) return null;
    let parsed;
    try {
      parsed = new URL(item.finalUrl || item.url || "");
    } catch {
      return null;
    }
    if (!["https:", "http:"].includes(parsed.protocol) ||
        parsed.username || parsed.password ||
        ["localhost", "127.0.0.1", "::1"].includes(parsed.hostname)) return null;
    const name = basename(item.filename || decodeURIComponent(parsed.pathname.split("/").pop()));
    const extension = name.match(/\.([a-z0-9]{1,7})$/i);
    if (!extension || !EXTENSIONS.has(extension[1].toLowerCase())) return null;
    return { url: parsed.href, fileName: name, id: item.id };
  }

  async function transfer(item, deps) {
    const target = eligible(item);
    if (!target) return { status: "skipped" };
    let paused = false;
    try {
      await deps.pause(target.id);
      paused = true;
      await deps.remember(target.id, true);
      const response = await deps.send(target.url, target.fileName);
      if (!response || response.success !== true) {
        return { status: "native", reason: response && response.code || "desktop_unavailable" };
      }
      await deps.cancel(target.id);
      return { status: "desktop" };
    } catch {
      return { status: "native", reason: "handoff_or_cancel_failed" };
    } finally {
      if (paused) {
        // Resume is harmless when the native download was already cancelled.
        try {
          if (await deps.isPaused(target.id)) await deps.resume(target.id);
        } catch { /* Interrupted or removed browser download */ }
        await deps.remember(target.id, false);
      }
    }
  }

  const api = { basename, eligible, transfer };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.IDSFileInterception = api;
})(typeof globalThis === "object" ? globalThis : this);
