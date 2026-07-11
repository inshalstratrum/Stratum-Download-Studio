(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.StratumMediaCandidates = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const HTTP_PROTOCOLS = new Set(["http:", "https:"]);
  const DIRECT_EXTENSIONS = /\.(?:mp4|webm|mov|mkv|avi|mp3|m4a|aac|ogg|oga|opus|wav|flac)(?:$|[?#])/i;
  const HLS_EXTENSION = /\.m3u8(?:$|[?#])/i;
  const DASH_EXTENSION = /\.mpd(?:$|[?#])/i;
  const SEGMENT_PATH = /(?:\.(?:ts|m4s|cmfv|cmfa)(?:$|[?#])|(?:^|[\/_-])(?:segment|seg|chunk|frag|fragment|videoplayback)[\/_-]?\d*(?:[.?#/_-]|$))/i;
  const MEDIA_CONTENT_TYPE = /^(?:video|audio)\//i;
  const MANIFEST_CONTENT_TYPE = /(?:mpegurl|vnd\.apple\.mpegurl|dash\+xml)/i;
  const MEDIA_DISPOSITION = /filename\*?\s*=\s*(?:UTF-8''|["'])?[^;"']+\.(?:mp4|webm|mov|mkv|avi|mp3|m4a|aac|ogg|oga|opus|wav|flac|m3u8|mpd)/i;
  const MAX_TITLE_LENGTH = 160;
  const MAX_URL_LENGTH = 8192;

  function safeUrl(value, baseUrl) {
    if (typeof value !== "string" || !value.trim() || value.length > MAX_URL_LENGTH) {
      return null;
    }
    try {
      const parsed = new URL(value, baseUrl);
      return HTTP_PROTOCOLS.has(parsed.protocol) && !parsed.username && !parsed.password ? parsed : null;
    } catch (error) {
      return null;
    }
  }

  function youtubeVideoId(parsed) {
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
    if (host === "youtu.be") {
      return parsed.pathname.split("/").filter(Boolean)[0] || "";
    }
    if (host === "youtube.com" || host.endsWith(".youtube.com") || host === "youtube-nocookie.com" || host.endsWith(".youtube-nocookie.com")) {
      if (parsed.pathname === "/watch") {
        return parsed.searchParams.get("v") || "";
      }
      const match = parsed.pathname.match(/^\/(?:embed|shorts|live)\/([^/?#]+)/);
      return match ? match[1] : "";
    }
    return "";
  }

  function stablePageUrl(value) {
    const parsed = safeUrl(value);
    if (!parsed) {
      return null;
    }
    const youtubeId = youtubeVideoId(parsed);
    if (youtubeId && /^[A-Za-z0-9_-]{6,32}$/.test(youtubeId)) {
      return `https://www.youtube.com/watch?v=${encodeURIComponent(youtubeId)}`;
    }
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
    if (host === "vimeo.com" || host.endsWith(".vimeo.com")) {
      const match = parsed.pathname.match(/\/(?:video\/)?(\d+)/);
      if (match) {
        return `https://vimeo.com/${match[1]}`;
      }
    }
    parsed.hash = "";
    return parsed.href;
  }

  function isExtractorPage(value) {
    const parsed = safeUrl(value);
    if (!parsed) {
      return false;
    }
    const host = parsed.hostname.toLowerCase();
    return Boolean(youtubeVideoId(parsed)) || /(^|\.)vimeo\.com$/.test(host);
  }

  function isSegmentUrl(value) {
    const parsed = safeUrl(value);
    if (!parsed) {
      return false;
    }
    const host = parsed.hostname.toLowerCase();
    return host === "googlevideo.com" || host.endsWith(".googlevideo.com") || SEGMENT_PATH.test(`${parsed.pathname}${parsed.search}`);
  }

  function inferKind(raw, contentType, parsed) {
    if (raw.mediaKind === "audio" || raw.mediaKind === "video") {
      return raw.mediaKind;
    }
    if (/^audio\//i.test(contentType) || /\.(?:mp3|m4a|aac|ogg|oga|opus|wav|flac)(?:$|[?#])/i.test(parsed.href) || /\.(?:mp3|m4a|aac|ogg|oga|opus|wav|flac)(?:["';]|$)/i.test(String(raw.contentDisposition || ""))) {
      return "audio";
    }
    return "video";
  }

  function classifyCandidate(raw) {
    raw = raw && typeof raw === "object" ? raw : {};
    const pageUrl = stablePageUrl(raw.pageUrl || "");
    const original = typeof raw.url === "string" ? raw.url.trim() : "";
    const parsed = safeUrl(original, pageUrl || undefined);
    const contentType = String(raw.contentType || "").split(";", 1)[0].trim().toLowerCase();
    const disposition = String(raw.contentDisposition || "");
    const evidence = Array.isArray(raw.evidence) ? raw.evidence : [raw.evidence || "unknown"];

    if (raw.blobOnly) {
      if (!pageUrl) {
        return null;
      }
      return finish(pageUrl, "page", raw.mediaKind || "video", raw, evidence.concat("blob-page-fallback"), pageUrl);
    }
    if (!parsed || isSegmentUrl(parsed.href)) {
      return null;
    }

    if (isExtractorPage(parsed.href)) {
      const stable = stablePageUrl(parsed.href);
      return finish(stable, "page", inferKind(raw, contentType, parsed), raw, evidence, pageUrl || stable);
    }
    if (HLS_EXTENSION.test(parsed.href) || /mpegurl|vnd\.apple\.mpegurl/i.test(contentType)) {
      return finish(parsed.href, "hls", inferKind(raw, contentType, parsed), raw, evidence, pageUrl);
    }
    if (DASH_EXTENSION.test(parsed.href) || /dash\+xml/i.test(contentType)) {
      return finish(parsed.href, "dash", inferKind(raw, contentType, parsed), raw, evidence, pageUrl);
    }
    if (DIRECT_EXTENSIONS.test(parsed.href) || MEDIA_CONTENT_TYPE.test(contentType) || MEDIA_DISPOSITION.test(disposition)) {
      return finish(parsed.href, "direct_media", inferKind(raw, contentType, parsed), raw, evidence, pageUrl);
    }
    if (raw.allowPage && pageUrl) {
      return finish(pageUrl, "page", raw.mediaKind || "video", raw, evidence.concat("page-fallback"), pageUrl);
    }
    return null;
  }

  function finish(url, type, mediaKind, raw, evidence, pageUrl) {
    const cleanEvidence = Array.from(new Set(evidence.filter((item) => typeof item === "string" && item).map((item) => item.slice(0, 80))));
    const title = String(raw.title || raw.label || "").replace(/\s+/g, " ").trim().slice(0, MAX_TITLE_LENGTH);
    return {
      id: stableId(`${raw.tabId ?? -1}|${raw.frameId ?? 0}|${type}|${mediaKind}|${url}`),
      tabId: Number.isInteger(raw.tabId) ? raw.tabId : -1,
      frameId: Number.isInteger(raw.frameId) ? raw.frameId : 0,
      pageUrl: pageUrl || url,
      url,
      type,
      mediaKind,
      title: title || defaultLabel(type, mediaKind),
      evidence: cleanEvidence,
      firstObserved: Number(raw.firstObserved) || Date.now(),
      lastObserved: Number(raw.lastObserved) || Date.now()
    };
  }

  function defaultLabel(type, mediaKind) {
    if (type === "hls") return "HLS stream";
    if (type === "dash") return "DASH stream";
    if (type === "page") return `${mediaKind === "audio" ? "Audio" : "Video"} page`;
    return mediaKind === "audio" ? "Audio file" : "Video file";
  }

  function stableId(value) {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return `media-${(hash >>> 0).toString(16).padStart(8, "0")}`;
  }

  class CandidateStore {
    constructor(options = {}) {
      this.maxCandidates = Math.max(1, Number(options.maxCandidates) || 200);
      this.ttlMs = Math.max(1000, Number(options.ttlMs) || 30 * 60 * 1000);
      this.clock = typeof options.clock === "function" ? options.clock : Date.now;
      this.items = new Map();
    }

    observe(raw) {
      const now = this.clock();
      const candidate = classifyCandidate({ ...raw, firstObserved: now, lastObserved: now });
      if (!candidate) return null;
      const existing = this.items.get(candidate.id);
      if (existing) {
        existing.lastObserved = now;
        existing.title = candidate.title || existing.title;
        if (existing.pageUrl === existing.url && candidate.pageUrl !== candidate.url) existing.pageUrl = candidate.pageUrl;
        existing.evidence = Array.from(new Set(existing.evidence.concat(candidate.evidence)));
        return { ...existing, evidence: [...existing.evidence] };
      }
      this.items.set(candidate.id, candidate);
      this.prune(now);
      return { ...candidate, evidence: [...candidate.evidence] };
    }

    list(filter = {}) {
      this.prune(this.clock());
      return Array.from(this.items.values())
        .filter((item) => filter.tabId === undefined || item.tabId === filter.tabId)
        .filter((item) => filter.frameId === undefined || item.frameId === filter.frameId)
        .filter((item) => !filter.pageUrl || item.pageUrl === stablePageUrl(filter.pageUrl))
        .sort((left, right) => right.lastObserved - left.lastObserved)
        .map((item) => ({ ...item, evidence: [...item.evidence] }));
    }

    removeTab(tabId) {
      for (const [id, item] of this.items) {
        if (item.tabId === tabId) this.items.delete(id);
      }
    }

    removeIds(ids, filter = {}) {
      for (const id of Array.isArray(ids) ? ids : []) {
        const item = this.items.get(id);
        if (!item) continue;
        if (filter.tabId !== undefined && item.tabId !== filter.tabId) continue;
        if (filter.frameId !== undefined && item.frameId !== filter.frameId) continue;
        this.items.delete(id);
      }
    }

    prune(now = this.clock()) {
      for (const [id, item] of this.items) {
        if (now - item.lastObserved > this.ttlMs) this.items.delete(id);
      }
      if (this.items.size <= this.maxCandidates) return;
      const oldest = Array.from(this.items.values()).sort((left, right) => left.lastObserved - right.lastObserved);
      for (let index = 0; index < oldest.length - this.maxCandidates; index += 1) {
        this.items.delete(oldest[index].id);
      }
    }
  }

  function isUsefulResponseEvidence(contentType, contentDisposition) {
    return MEDIA_CONTENT_TYPE.test(String(contentType || "")) || MANIFEST_CONTENT_TYPE.test(String(contentType || "")) || MEDIA_DISPOSITION.test(String(contentDisposition || ""));
  }

  return { CandidateStore, classifyCandidate, isExtractorPage, isSegmentUrl, isUsefulResponseEvidence, safeUrl, stableId, stablePageUrl };
});
