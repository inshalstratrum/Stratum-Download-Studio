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
  const SEGMENT_PATH = /(?:\.(?:ts|m4s|cmfv|cmfa)(?:$|[?#])|(?:^|\/)(?:init(?:ialization)?|segment|seg|chunk|frag|fragment)(?:[-_.][^/?#]*)?\.(?:mp4|m4a|webm)(?:$|[?#])|(?:^|[\/_-])videoplayback(?:[.?#/_-]|$))/i;
  const ADAPTIVE_REPRESENTATION_PATH = /(?:^|\/)(?:[av]-\d{3,4}p-\d+k[^/]*|[^/]*(?:representation|bitrate)[_-]\d+[^/]*|[^/]*[_-](?:\d{3,4}p|\d{2,6}k)[_-][^/]*)\.(?:mp4|m4a|webm)(?:$|[?#])/i;
  const MEDIA_CONTENT_TYPE = /^(?:video|audio)\//i;
  const MANIFEST_CONTENT_TYPE = /(?:mpegurl|vnd\.apple\.mpegurl|dash\+xml)/i;
  const MEDIA_DISPOSITION = /filename\*?\s*=\s*(?:UTF-8''|["'])?[^;"']+\.(?:mp4|webm|mov|mkv|avi|mp3|m4a|aac|ogg|oga|opus|wav|flac|m3u8|mpd)/i;
  const MAX_TITLE_LENGTH = 160;
  const MAX_URL_LENGTH = 8192;
  const PLAYER_ID_PATTERN = /^player-[a-z0-9_-]{6,96}$/i;
  const DOM_EVIDENCE = new Set(["dom-media", "nested-source", "source-change", "currentSrc-change", "control-click", "loaded-metadata"]);
  const TRANSIENT_QUERY_KEYS = /^(?:token|access_token|auth|authorization|signature|sig|expires?|expiry|exp|e|policy|key-pair-id|hdnts|hdntl|hdnea|hmac|jwt|session|sessionid|acl|ip|ipbits|st|__gda__|x-amz-.+|x-goog-.+|range|rn|rbuf|sq)$/i;

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
    const social = canonicalSocialPage(parsed, host);
    if (social) return social;
    if (host === "vimeo.com" || host.endsWith(".vimeo.com")) {
      const match = parsed.pathname.match(/\/(?:video\/)?(\d+)/);
      if (match) {
        return `https://vimeo.com/${match[1]}`;
      }
    }
    parsed.hash = "";
    return parsed.href;
  }

  function canonicalSocialPage(parsed, host) {
    parsed.hash = "";
    if (host === "dai.ly") {
      const id = parsed.pathname.split("/").filter(Boolean)[0] || "";
      return /^[A-Za-z0-9]+$/.test(id) ? `https://www.dailymotion.com/video/${id}` : null;
    }
    if (host === "dailymotion.com" || host.endsWith(".dailymotion.com")) {
      const match = parsed.pathname.match(/^\/video\/([A-Za-z0-9]+)/);
      return match ? `https://www.dailymotion.com/video/${match[1]}` : null;
    }
    if (host === "facebook.com" || host.endsWith(".facebook.com") || host === "fb.watch") {
      if (host === "fb.watch") return `https://fb.watch${parsed.pathname.replace(/\/$/, "")}/`;
      const watchId = parsed.searchParams.get("v");
      if (/^\/watch\/?$/.test(parsed.pathname) && watchId) return `https://www.facebook.com/watch/?v=${encodeURIComponent(watchId)}`;
      const storyId = parsed.searchParams.get("story_fbid");
      const ownerId = parsed.searchParams.get("id");
      if (/^\/permalink\.php$/.test(parsed.pathname) && storyId && ownerId) return `https://www.facebook.com/permalink.php?story_fbid=${encodeURIComponent(storyId)}&id=${encodeURIComponent(ownerId)}`;
      const match = parsed.pathname.match(/^\/(?:reel\/[^/?#]+|[^/?#]+\/videos\/[^/?#]+|share\/v\/[^/?#]+)/);
      return match ? `https://www.facebook.com${match[0].replace(/\/$/, "")}/` : null;
    }
    if (host === "instagram.com" || host.endsWith(".instagram.com")) {
      const match = parsed.pathname.match(/^\/(?:p|reel|tv)\/[^/?#]+/);
      return match ? `https://www.instagram.com${match[0].replace(/\/$/, "")}/` : null;
    }
    if (host === "tiktok.com" || host.endsWith(".tiktok.com")) {
      const match = parsed.pathname.match(/^\/@[^/?#]+\/video\/\d+/);
      return match ? `https://www.tiktok.com${match[0]}` : null;
    }
    if (host === "x.com" || host === "twitter.com" || host.endsWith(".twitter.com")) {
      const match = parsed.pathname.match(/^\/([^/?#]+)\/status\/(\d+)/);
      return match ? `https://x.com/${match[1]}/status/${match[2]}` : null;
    }
    return null;
  }

  function canonicalCandidateUrl(value) {
    const extractor = stablePageUrl(value);
    if (!extractor) return null;
    if (isExtractorPage(extractor)) return extractor;
    const parsed = safeUrl(extractor);
    parsed.hash = "";
    const retained = Array.from(parsed.searchParams.entries())
      .filter(([key]) => !TRANSIENT_QUERY_KEYS.test(key))
      .sort(([leftKey, leftValue], [rightKey, rightValue]) => leftKey.localeCompare(rightKey) || leftValue.localeCompare(rightValue));
    parsed.search = "";
    for (const [key, value] of retained) parsed.searchParams.append(key, value);
    return parsed.href;
  }

  function isExtractorPage(value) {
    const parsed = safeUrl(value);
    if (!parsed) {
      return false;
    }
    const host = parsed.hostname.toLowerCase();
    return Boolean(youtubeVideoId(parsed)) || Boolean(canonicalSocialPage(parsed, host.replace(/^www\./, ""))) || /(^|\.)vimeo\.com$/.test(host) || (/(^|\.)cnbc\.com$/.test(host) && /^\/video\//.test(parsed.pathname));
  }

  function isSegmentUrl(value) {
    const parsed = safeUrl(value);
    if (!parsed) {
      return false;
    }
    const host = parsed.hostname.toLowerCase();
    return host === "googlevideo.com" || host.endsWith(".googlevideo.com") || SEGMENT_PATH.test(`${parsed.pathname}${parsed.search}`) || parsed.searchParams.has("range");
  }

  function isNetworkFragment(raw, parsed, evidence, completeAttachment) {
    const networkOnly = evidence.some((item) => item === "performance-resource" || item === "webRequest-response");
    if (!networkOnly) return false;
    if (Number(raw.statusCode) === 206 || String(raw.contentRange || "").trim()) return true;
    if (completeAttachment) return false;
    return ADAPTIVE_REPRESENTATION_PATH.test(`${parsed.pathname}${parsed.search}`);
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

  function inferManifestKind(raw, contentType, parsed) {
    const path = parsed.pathname.toLowerCase();
    const audioMime = /^audio\//i.test(contentType) || /audio[^/;]*mpegurl/i.test(contentType);
    const audioName = /(?:^|\/)(?:audio(?:[_-]|\/)|[^/]*playlist[_-]a(?:[_-]|\.)|[^/]*[_-]a(?:ac)?[_-][^/]*)/i.test(path);
    const videoName = /(?:^|\/)(?:video(?:[_-]|\/)|[^/]*playlist[_-]v(?:[_-]|\.))/i.test(path);
    if (audioMime || audioName) return { kind: "audio", strong: true };
    if (/^video\//i.test(contentType) || videoName) return { kind: "video", strong: true };
    if (raw.mediaKind === "audio" || raw.mediaKind === "video") return { kind: raw.mediaKind, strong: true };
    return { kind: inferKind(raw, contentType, parsed), strong: false };
  }

  function classifyCandidate(raw) {
    raw = raw && typeof raw === "object" ? raw : {};
    const pageUrl = stablePageUrl(raw.pageUrl || "");
    const original = typeof raw.url === "string" ? raw.url.trim() : "";
    const parsed = safeUrl(original, pageUrl || undefined);
    const contentType = String(raw.contentType || "").split(";", 1)[0].trim().toLowerCase();
    const disposition = String(raw.contentDisposition || "");
    const evidence = Array.isArray(raw.evidence) ? raw.evidence : [raw.evidence || "unknown"];

    if (raw.blobOnly) return pageUrl && isExtractorPage(pageUrl) ? finish(pageUrl, "page", raw.mediaKind || "video", raw, evidence.concat("extractor-page"), pageUrl) : null;
    if (!parsed || isSegmentUrl(parsed.href)) {
      return null;
    }

    if (isExtractorPage(parsed.href)) {
      const stable = stablePageUrl(parsed.href);
      return finish(stable, "page", inferKind(raw, contentType, parsed), raw, evidence, pageUrl || stable);
    }
    if (HLS_EXTENSION.test(parsed.href) || /mpegurl|vnd\.apple\.mpegurl/i.test(contentType)) {
      const manifestKind = inferManifestKind(raw, contentType, parsed);
      return finish(parsed.href, "hls", manifestKind.kind, { ...raw, strongMediaKind: manifestKind.strong ? manifestKind.kind : "" }, evidence, pageUrl);
    }
    if (DASH_EXTENSION.test(parsed.href) || /dash\+xml/i.test(contentType)) {
      const manifestKind = inferManifestKind(raw, contentType, parsed);
      return finish(parsed.href, "dash", manifestKind.kind, { ...raw, strongMediaKind: manifestKind.strong ? manifestKind.kind : "" }, evidence, pageUrl);
    }
    const completeAttachment = /\battachment\b/i.test(disposition) && MEDIA_DISPOSITION.test(disposition);
    if (isNetworkFragment(raw, parsed, evidence, completeAttachment)) return null;
    const explicitDomSource = evidence.some((item) => DOM_EVIDENCE.has(item));
    const verifiedMainFrameMedia = evidence.includes("webRequest-main-frame") && MEDIA_CONTENT_TYPE.test(contentType);
    const verifiedDocumentMedia = raw.topLevelDocument && evidence.includes("top-level-media-document") && MEDIA_CONTENT_TYPE.test(contentType) && DIRECT_EXTENSIONS.test(parsed.href);
    if (explicitDomSource || verifiedMainFrameMedia || verifiedDocumentMedia || completeAttachment) {
      return finish(parsed.href, "direct_media", inferKind(raw, contentType, parsed), raw, evidence, pageUrl);
    }
    return null;
  }

  function finish(url, type, mediaKind, raw, evidence, pageUrl) {
    const cleanEvidence = Array.from(new Set(evidence.filter((item) => typeof item === "string" && item).map((item) => item.slice(0, 80))));
    const title = sanitizeTitle(raw.title || raw.label || "");
    const canonicalUrl = canonicalCandidateUrl(url);
    const priority = candidatePriority(type, url, cleanEvidence, raw);
    const kindConfidence = raw.strongMediaKind || raw.mediaKind === "audio" || raw.mediaKind === "video" || /^(?:audio|video)\//i.test(String(raw.contentType || "")) ? 3 : 1;
    const metadata = candidateMetadata(url, type, mediaKind, raw, contentFormat(raw, url, type, mediaKind));
    return {
      id: stableId(`${raw.tabId ?? -1}|${raw.frameId ?? 0}|${raw.playerId || ""}|${type}|${canonicalUrl}`),
      tabId: Number.isInteger(raw.tabId) ? raw.tabId : -1,
      frameId: Number.isInteger(raw.frameId) ? raw.frameId : 0,
      playerId: validPlayerId(raw.playerId) ? raw.playerId : "",
      pageUrl: pageUrl || url,
      url,
      canonicalUrl,
      type,
      mediaKind,
      title: title || defaultLabel(type, mediaKind),
      format: metadata.format,
      resolution: metadata.resolution,
      bitrateKbps: metadata.bitrateKbps,
      safeTarget: metadata.safeTarget,
      manifestRole: metadata.manifestRole,
      manifestFamily: metadata.manifestFamily,
      manifestRank: metadata.manifestRank,
      componentOnly: mediaKind === "audio" || raw.hasAudio === false || raw.componentOnly === true || metadata.manifestRole === "audio_variant" || metadata.manifestRole === "video_variant" || metadata.manifestRole === "variant",
      label: buildLabel(type, mediaKind, title, metadata),
      priority,
      kindConfidence,
      evidence: cleanEvidence,
      firstObserved: Number(raw.firstObserved) || Date.now(),
      lastObserved: Number(raw.lastObserved) || Date.now()
    };
  }

  function sanitizeTitle(value) {
    return String(value || "")
      .replace(/https?:\/\/[^\s]+/gi, (match) => {
        const parsed = safeUrl(match);
        return parsed ? `${parsed.origin}${parsed.pathname}` : "[URL]";
      })
      .replace(/\b(?:token|access_token|authorization|signature|sig|policy|key-pair-id|expires?)\s*=\s*[^\s&]+/gi, "[redacted]")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, MAX_TITLE_LENGTH);
  }

  function candidatePriority(type, url, evidence, raw) {
    if (type === "direct_media" && (raw.topLevelDocument || evidence.includes("top-level-media-document") || evidence.includes("webRequest-main-frame"))) return 0;
    const parsed = safeUrl(url);
    const filename = parsed ? parsed.pathname.split("/").pop() || "" : "";
    if ((type === "hls" || type === "dash") && describeManifest(parsed, type, raw.mediaKind || "video", filename).role === "master") return 0;
    if (type === "page" && isExtractorPage(url)) return 1;
    if (type === "hls" || type === "dash") return 2;
    if (type === "direct_media" && evidence.some((item) => DOM_EVIDENCE.has(item))) return 3;
    if (type === "direct_media" && (raw.topLevelDocument || evidence.includes("top-level-media-document") || evidence.includes("webRequest-main-frame"))) return 4;
    if (type === "direct_media") return 5;
    return 6;
  }

  function contentFormat(raw, url, type, mediaKind) {
    if (type === "hls") return "HLS";
    if (type === "dash") return "DASH";
    const contentType = String(raw.contentType || "").split(";", 1)[0].toLowerCase();
    const subtype = contentType.split("/", 2)[1] || "";
    const parsed = safeUrl(url);
    const extension = parsed && parsed.pathname.match(/\.([a-z0-9]{2,5})$/i);
    const value = String(raw.format || (extension && extension[1]) || subtype.split("+")[0] || "").toUpperCase();
    return value.replace("X-M4A", "M4A").replace("MPEG", mediaKind === "audio" ? "MP3" : "MPEG").slice(0, 12);
  }

  function candidateMetadata(url, type, mediaKind, raw, format) {
    const parsed = safeUrl(url);
    const rawFilename = parsed ? parsed.pathname.split("/").filter(Boolean).pop() || "" : "";
    let filename = rawFilename;
    try { filename = decodeURIComponent(rawFilename); } catch (error) { /* Keep the safe encoded path component. */ }
    const hostname = parsed ? parsed.hostname.replace(/^www\./, "") : "";
    const width = Number(raw.width) || 0;
    const height = Number(raw.height) || 0;
    const bitrate = Number(raw.bitrateKbps || raw.bitrate) || 0;
    const manifest = describeManifest(parsed, type, mediaKind, filename);
    return {
      format,
      resolution: width > 0 && height > 0 ? `${Math.round(width)}×${Math.round(height)}` : "",
      bitrateKbps: bitrate > 0 ? Math.round(bitrate) : 0,
      safeTarget: (type === "direct_media" || type === "hls" || type === "dash") && filename ? filename.slice(0, 100) : hostname.slice(0, 100),
      pageDescriptor: /(^|\.)youtu(?:be\.com|\.be)$/.test(hostname) || /(^|\.)youtube-nocookie\.com$/.test(hostname) ? "YouTube" : /(^|\.)vimeo\.com$/.test(hostname) ? "Vimeo" : /(^|\.)cnbc\.com$/.test(hostname) ? "CNBC page" : "Page",
      provider: /(?:^|\.)(?:brightcove\.com|boltdns\.net)$/.test(hostname) ? "Brightcove" : "",
      manifestRole: manifest.role,
      manifestFamily: manifest.family,
      manifestRank: manifest.rank,
      mediaKind
    };
  }

  function describeManifest(parsed, type, mediaKind, filename) {
    if (!parsed || (type !== "hls" && type !== "dash")) return { role: "", family: "", rank: 99 };
    const lowerName = filename.toLowerCase();
    const path = parsed.pathname.toLowerCase();
    const familyPath = parsed.pathname.slice(0, Math.max(1, parsed.pathname.lastIndexOf("/"))) || "/";
    const family = manifestFamily(parsed, familyPath);
    if (type === "dash") return { role: "master", family, rank: 0 };
    if (mediaKind === "audio" || /playlist[_-]a(?:[_-]|\.)|(?:^|[_-])audio(?:[_-]|\.)/i.test(lowerName)) {
      return { role: "audio_variant", family, rank: 30 };
    }
    if (/playlist[_-]v(?:[_-]|\.)|(?:^|[_-])video(?:[_-]|\.)/i.test(lowerName)) {
      return { role: "video_variant", family, rank: 20 };
    }
    const masterNames = new Map([["master.m3u8", 0], ["hls.m3u8", 1], ["index.m3u8", 2], ["manifest.m3u8", 3], ["main.m3u8", 4]]);
    if (masterNames.has(lowerName) || /(?:^|[_-])master(?:[_-]|\.)/i.test(lowerName)) {
      return { role: "master", family, rank: masterNames.get(lowerName) ?? 5 };
    }
    if (/(?:^|\/)(?:audio|video|variant|rendition)(?:\/|[_-])/i.test(path) || /(?:\d{3,4}p|\d{2,6}k)/i.test(lowerName)) {
      return { role: "variant", family, rank: 25 };
    }
    return { role: "unknown", family, rank: 10 };
  }

  function manifestFamily(parsed, familyPath) {
    const identityKeys = /^(?:id|video|videoid|asset|assetid|contentid|playbackid)$/i;
    const identity = Array.from(parsed.searchParams.entries())
      .filter(([key]) => identityKeys.test(key))
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => `${key.toLowerCase()}=${value}`)
      .join("&");
    return `${parsed.origin}${familyPath}::${identity}`;
  }

  function buildLabel(type, mediaKind, title, metadata) {
    const cleanTitle = title || (mediaKind === "audio" ? "Audio" : "Video");
    if (mediaKind === "audio" || metadata.manifestRole === "audio_variant") return `${cleanTitle} • Audio only`;
    if (metadata.manifestRole === "video_variant" || metadata.manifestRole === "variant") return `${cleanTitle} • Video only${metadata.resolution ? ` • ${metadata.resolution}` : ""}`;
    return `${cleanTitle} • ${metadata.resolution || "Best quality"}`;
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
      if ((candidate.priority === 5 || candidate.priority === 6) && this.hasDominantCandidate(candidate)) return null;
      const existing = this.items.get(candidate.id);
      if (existing) {
        const existingPageWasSelf = existing.pageUrl === existing.url;
        existing.lastObserved = now;
        existing.title = candidate.title || existing.title;
        existing.url = candidate.url;
        existing.priority = Math.min(existing.priority, candidate.priority);
        const existingMetadata = (existing.resolution ? 2 : 0) + (existing.bitrateKbps ? 1 : 0);
        const candidateMetadata = (candidate.resolution ? 2 : 0) + (candidate.bitrateKbps ? 1 : 0);
        if (candidate.kindConfidence > existing.kindConfidence || (candidate.kindConfidence === existing.kindConfidence && candidateMetadata > existingMetadata)) {
          existing.mediaKind = candidate.mediaKind;
          existing.format = candidate.format;
          existing.resolution = candidate.resolution || existing.resolution;
          existing.bitrateKbps = candidate.bitrateKbps || existing.bitrateKbps;
          existing.safeTarget = candidate.safeTarget || existing.safeTarget;
          existing.manifestRole = candidate.manifestRole || existing.manifestRole;
          existing.manifestFamily = candidate.manifestFamily || existing.manifestFamily;
          existing.manifestRank = candidate.manifestRank;
          existing.componentOnly = candidate.componentOnly;
          existing.label = candidate.label;
          existing.kindConfidence = candidate.kindConfidence;
        }
        if (existingPageWasSelf && candidate.pageUrl !== candidate.url) existing.pageUrl = candidate.pageUrl;
        existing.evidence = Array.from(new Set(existing.evidence.concat(candidate.evidence)));
        return { ...existing, evidence: [...existing.evidence] };
      }
      if (candidate.type === "hls") {
        const related = Array.from(this.items.values()).filter((item) => manifestsRelated(item, candidate));
        if (candidate.manifestRole !== "master" && related.some((item) => item.manifestRole === "master")) return null;
        if (candidate.manifestRole === "master") {
          const preferredMaster = related
            .filter((item) => item.manifestRole === "master")
            .sort((left, right) => left.manifestRank - right.manifestRank || left.id.localeCompare(right.id))[0];
          if (preferredMaster && preferredMaster.manifestRank <= candidate.manifestRank) return null;
          for (const item of related) {
            if (item.manifestRole === "master" || isChildManifest(item)) this.items.delete(item.id);
          }
        }
      }
      this.items.set(candidate.id, candidate);
      if (candidate.priority <= 2) this.removeDominatedCandidates(candidate);
      this.prune(now);
      return { ...candidate, evidence: [...candidate.evidence] };
    }

    list(filter = {}) {
      this.prune(this.clock());
      let candidates = Array.from(this.items.values())
        .filter((item) => filter.tabId === undefined || item.tabId === filter.tabId)
        .filter((item) => filter.frameId === undefined || item.frameId === filter.frameId)
        .filter((item) => filter.playerId === undefined || item.playerId === filter.playerId)
        .filter((item) => !filter.pageUrl || item.pageUrl === stablePageUrl(filter.pageUrl))
        .filter((item) => filter.simpleMode === false || !item.componentOnly);
      const completeDirectOrMaster = candidates.filter((item) => item.priority === 0);
      if (completeDirectOrMaster.length) candidates = completeDirectOrMaster;
      else {
        const extractorPages = candidates.filter((item) => item.priority === 1);
        if (extractorPages.length) candidates = extractorPages;
      }
      const manifests = candidates.filter((item) => item.priority === 2);
      if (manifests.length) candidates = candidates.filter((item) => item.priority !== 5 && item.priority !== 6);
      if (candidates.some((item) => item.priority < 6)) candidates = candidates.filter((item) => item.priority < 6);
      candidates.sort((left, right) => left.priority - right.priority || left.manifestRank - right.manifestRank || right.lastObserved - left.lastObserved || left.id.localeCompare(right.id));
      return distinctLabels(candidates).map((item) => ({ ...item, evidence: [...item.evidence] }));
    }

    sameOwner(left, right) {
      return left.tabId === right.tabId && left.frameId === right.frameId && left.pageUrl === right.pageUrl && left.playerId === right.playerId;
    }

    hasDominantCandidate(candidate) {
      for (const item of this.items.values()) {
        if (!this.sameOwner(item, candidate)) continue;
        if (item.priority === 1 || item.priority === 2) return true;
        if (candidate.priority === 6 && item.priority < 6) return true;
      }
      return false;
    }

    removeDominatedCandidates(candidate) {
      for (const [id, item] of this.items) {
        if (id === candidate.id || !this.sameOwner(item, candidate)) continue;
        if ((candidate.priority === 1 && item.priority > 1) || item.priority === 5 || item.priority === 6) this.items.delete(id);
      }
    }

    removeTab(tabId) {
      for (const [id, item] of this.items) {
        if (item.tabId === tabId) this.items.delete(id);
      }
    }

    removeFrame(tabId, frameId) {
      for (const [id, item] of this.items) {
        if (item.tabId === tabId && item.frameId === frameId) this.items.delete(id);
      }
    }

    removeFrameNetwork(tabId, frameId) {
      for (const [id, item] of this.items) {
        if (item.tabId !== tabId || item.frameId !== frameId) continue;
        if (item.evidence.every((value) => value === "webRequest-response" || value === "performance-resource")) this.items.delete(id);
      }
    }

    reassignFramePage(tabId, frameId, pageUrl) {
      const stable = stablePageUrl(pageUrl);
      if (!stable) return;
      for (const item of this.items.values()) {
        if (item.tabId === tabId && item.frameId === frameId) item.pageUrl = stable;
      }
    }

    removeIds(ids, filter = {}) {
      for (const id of Array.isArray(ids) ? ids : []) {
        const item = this.items.get(id);
        if (!item) continue;
        if (filter.tabId !== undefined && item.tabId !== filter.tabId) continue;
        if (filter.frameId !== undefined && item.frameId !== filter.frameId) continue;
        if (filter.playerId !== undefined && item.playerId !== filter.playerId) continue;
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

  class PlayerOwnershipStore {
    constructor(maxOwners = 400) {
      this.maxOwners = Math.max(1, Number(maxOwners) || 400);
      this.items = new Map();
    }

    key(tabId, frameId, playerId) {
      return `${tabId}:${frameId}:${playerId}`;
    }

    bind(tabId, frameId, playerId, pageUrl) {
      const stable = stablePageUrl(pageUrl || "");
      if (!Number.isInteger(tabId) || !Number.isInteger(frameId) || !validPlayerId(playerId) || !stable) return false;
      const key = this.key(tabId, frameId, playerId);
      const existing = this.items.get(key);
      if (existing && existing !== stable) return false;
      this.items.delete(key);
      this.items.set(key, stable);
      while (this.items.size > this.maxOwners) this.items.delete(this.items.keys().next().value);
      return true;
    }

    owns(tabId, frameId, playerId, pageUrl) {
      return validPlayerId(playerId) && this.items.get(this.key(tabId, frameId, playerId)) === stablePageUrl(pageUrl || "");
    }

    playerIds(tabId, frameId, pageUrl) {
      const stable = stablePageUrl(pageUrl || "");
      const prefix = `${tabId}:${frameId}:`;
      return Array.from(this.items.entries())
        .filter(([key, value]) => key.startsWith(prefix) && value === stable)
        .map(([key]) => key.slice(prefix.length));
    }

    removeFrame(tabId, frameId) {
      const prefix = `${tabId}:${frameId}:`;
      for (const key of this.items.keys()) if (key.startsWith(prefix)) this.items.delete(key);
    }

    removeTab(tabId) {
      const prefix = `${tabId}:`;
      for (const key of this.items.keys()) if (key.startsWith(prefix)) this.items.delete(key);
    }
  }

  function isChildManifest(candidate) {
    return candidate.manifestRole === "audio_variant" || candidate.manifestRole === "video_variant" || candidate.manifestRole === "variant" || candidate.manifestRole === "unknown";
  }

  function manifestsRelated(left, right) {
    if (left.type !== "hls" || right.type !== "hls") return false;
    if (left.tabId !== right.tabId || left.frameId !== right.frameId || left.pageUrl !== right.pageUrl || left.playerId !== right.playerId) return false;
    if (!left.manifestFamily || !right.manifestFamily) return false;
    const [leftPath, leftIdentity = ""] = left.manifestFamily.split("::", 2);
    const [rightPath, rightIdentity = ""] = right.manifestFamily.split("::", 2);
    if (leftIdentity !== rightIdentity) return false;
    return leftPath === rightPath || leftPath.startsWith(`${rightPath}/`) || rightPath.startsWith(`${leftPath}/`);
  }

  function distinctLabels(candidates) {
    const groups = new Map();
    for (const item of candidates) {
      const group = groups.get(item.label) || [];
      group.push(item);
      groups.set(item.label, group);
    }
    return candidates.map((item) => {
      const group = groups.get(item.label);
      if (group.length === 1) return item;
      const ordered = [...group].sort((left, right) => left.id.localeCompare(right.id));
      return { ...item, label: `${item.label} • Source ${ordered.indexOf(item) + 1}` };
    });
  }

  function validPlayerId(value) {
    return typeof value === "string" && PLAYER_ID_PATTERN.test(value);
  }

  function applyTrustedOwner(raw, tabId, frameId, playerId) {
    return {
      ...(raw && typeof raw === "object" ? raw : {}),
      tabId: Number.isInteger(tabId) ? tabId : -1,
      frameId: Number.isInteger(frameId) ? frameId : 0,
      playerId: validPlayerId(playerId) ? playerId : ""
    };
  }

  function isUsefulResponseEvidence(contentType, contentDisposition) {
    return MEDIA_CONTENT_TYPE.test(String(contentType || "")) || MANIFEST_CONTENT_TYPE.test(String(contentType || "")) || MEDIA_DISPOSITION.test(String(contentDisposition || ""));
  }

  function isOverlayTargetDescriptor(descriptor) {
    const tagName = String(descriptor && descriptor.tagName || "").toUpperCase();
    return tagName === "VIDEO" || tagName === "AUDIO";
  }

  return { CandidateStore, PlayerOwnershipStore, applyTrustedOwner, canonicalCandidateUrl, classifyCandidate, isExtractorPage, isOverlayTargetDescriptor, isSegmentUrl, isUsefulResponseEvidence, safeUrl, stableId, stablePageUrl, validPlayerId };
});
