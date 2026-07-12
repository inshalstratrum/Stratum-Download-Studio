# Phase 2A.7A Media Backend Capability Audit

Status: documentation-only audit, 2026-07-12. Baseline: `898e949fb6a04ee439acc555a29b03fe0b54df77`. No update, install, binary execution on untrusted input, source change, or implementation was performed.

## Evidence rules and official sources

- **Confirmed** means directly established from the baseline repository or a read-only local diagnostic. **Upstream** means current official project documentation/release metadata. **Likely** is an architectural inference requiring an experiment. **Reported** is a supplied symptom not reproduced in this phase.
- yt-dlp: [repository/README](https://github.com/yt-dlp/yt-dlp), [supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), [latest release](https://github.com/yt-dlp/yt-dlp/releases/latest), [EJS guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS).
- gallery-dl: [official repository](https://github.com/mikf/gallery-dl), [official documentation](https://gdl-org.github.io/docs/), [supported sites](https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.md), [official Codeberg project](https://codeberg.org/mikf/gallery-dl).
- Poppler: [official site and signed source release](https://poppler.freedesktop.org/), [official repository](https://gitlab.freedesktop.org/poppler/poppler).

## 1. Actual yt-dlp installation

### Finding

Stratum is an **embedded Python-module integration**, not a subprocess integration. `stratum_download_studio.py:22` imports `yt_dlp`; metadata and downloads instantiate `yt_dlp.YoutubeDL` at lines 1262 and 1706. Development therefore resolves Python's import path. The current environment resolves `yt_dlp` to `C:\Users\ROC STORE\AppData\Roaming\Python\Python314\site-packages\yt_dlp\__init__.py`, version `2026.03.17` (package metadata `2026.3.17`). The console launcher at `...\Scripts\yt-dlp.exe` is only a 108,312-byte entry-point wrapper for that same pip installation; its SHA-256 is `28F638B262D94C097B0F77DAB6C6763C3EC6C4F1B1993876E92FEF650BC2EEF4`.

| Question | Evidence-backed answer |
|---|---|
| Standalone executable used by Stratum | No. The launcher exists on `PATH`, but application code never invokes it. |
| Pip package/imported module | Yes: user-site pip package, version 2026.03.17, about 22,199,668 bytes in the observed source/package directory. |
| Vendored source | None found. |
| PyInstaller-collected dependency | Expected implicitly because the entry script imports `yt_dlp`, but no frozen build was produced in this phase. `StratumDownloadStudio.spec` has empty `hiddenimports`, `datas`, and `binaries`; exact collection is not locked or proven. |
| Multiple copies | One importable package plus its launcher were observed. No repository copy exists. A future frozen executable would become a separate collected copy. |
| Development resolution order | Entry script directory, Python environment paths/user site, then other configured paths. The global `yt-dlp.exe` is irrelevant to `import yt_dlp`; a different importable package earlier on `sys.path` can override. |
| Packaged resolution | Frozen module under PyInstaller's `_MEIPASS`; build-environment version becomes embedded. There is no runtime fallback to the global launcher. This remains unverified until a controlled build inspection. |
| Would `yt-dlp -U` update Stratum's copy? | **No/reliably not applicable.** Upstream reserves `-U` for release binaries. This is pip/module integration; the correct mechanism is a pinned package-environment rebuild. Running the wrapper's `-U` does not constitute a governed application upgrade. |
| Pinning/lock/build references | No requirements file, lock file, or yt-dlp pin exists. The spec imports the application only. Builds can silently collect whichever user/global package is installed. |
| Global override/customer drift | Development can drift whenever the user-site package changes. A properly frozen app should not be overridden by `PATH`, but customer self-updates are neither implemented nor permitted; rebuild provenance is absent. |
| Licence | Upstream says the PyPI source/wheel contains Unlicense code. Official PyInstaller release executables contain GPLv3+ components; therefore switching distribution form changes obligations. Stratum's own frozen dependency set must receive a generated third-party notice/SBOM review. |
| Latest official stable | `2026.06.09`, released 2026-06-09. This is the proposed controlled target, subject to the gates in document 16. |
| Channels | Stable: mostly monthly and release candidate for Stratum. Nightly: daily development snapshot, useful only in a clean compatibility branch. Master: per-push canary, never a release input. |

No current yt-dlp artifact is stored in the repository, so there is no repository artifact hash or durable provenance record. The required future mechanism is: isolated lock/constraints, exact stable version, hashes, clean environment, controlled PyInstaller collection, SBOM/licence inventory, fixture regression, signed release—not `yt-dlp -U` and never arbitrary `--update-to <repository>`.

## 2. yt-dlp and media dependency inventory

Observed sizes describe this workstation only; proposed bundle impact must be measured from a clean frozen build.

| Component | Presence/version/path/form | Purpose and upstream importance | Licence / redistribution | Size, security, update and compatibility consequence |
|---|---|---|---|---|
| `yt_dlp` | Present 2026.03.17; user-site pip module; ~22.2 MB directory | Core extractor/download API; required by current code | PyPI wheel/source: Unlicense | Unpinned and mutable; customer behavior can differ from CI/build. Target 2026.06.09 only after gates. |
| `yt-dlp.exe` | Present wrapper, 108 KB, user Scripts path | Console entry point; **not used by Stratum** | Same installed distribution | Hash recorded above; updating it is not an app update strategy. |
| FFmpeg | Repo-local 8.1.1 essentials build; 101,457,920 bytes; SHA-256 `228D7A8556258DE907FDB55F36850078EBC7680B84EC30D84EA02E99BEC1D1EB` | Merge, remux, transcode; strongly recommended/required for selected formats | Observed `--enable-gpl --enable-version3`; development-only release blocker | Source prefers repo-local binary. Large attack surface; untrusted media requires timeout/isolation. Spec does not add it explicitly, so packaged availability is unproven. |
| FFprobe | Repo-local 8.1.1; 101,251,072 bytes; SHA-256 `0FDE260F5ABD35C9CAFD96F594CC76365A780C1B73A90E35B6A3409EA1DB1BF0` | Final stream/container verification | Same GPL-enabled build provenance issue | Source prefers repo-local binary. Same packaging gap; final validation correctly fails closed. |
| `yt-dlp-ejs` | Missing | Full YouTube support; upstream strongly recommends it | Unlicense; wheel bundles MIT/ISC components | Major compatibility gap. Must match yt-dlp's declared supported version and be locked/reviewed. |
| Deno | Missing | Upstream-recommended restricted JS runtime for EJS | Separate upstream licence/notice review | Major compatibility gap. Prefer a pinned, provenance-verified Deno over an ambient runtime. |
| Node | Present 24.14.1 at `C:\Program Files\nodejs\node.exe`, but not enabled in yt-dlp options | Alternative EJS runtime; upstream requires Node 22+ and explicit `--js-runtimes node` | Node dependency notices required if bundled | System-provided and currently inert. Ambient discovery is non-reproducible; do not silently enable. |
| Bun / QuickJS | Missing | Optional EJS runtimes; Bun is deprecated upstream | Separate licences | Not required if governed Deno is chosen. QuickJS has temporary-file/TOCTOU considerations upstream. |
| `certifi` | Present 2026.4.22, user-site; ~246 KB | Mozilla CA bundle; networking optional dependency | MPL-2.0 | Pin and include notices; predictable trust-store update policy required. |
| `brotli` / `brotlicffi` | Missing | Brotli content decoding; networking optional | MIT | Compatibility gap on Brotli-only responses; add only in Phase B after tests. |
| `websockets` | Present 16.0, user-site; ~1.38 MB | WebSocket downloads | BSD-3-Clause | Pin/notice; increases protocol surface. |
| `requests` | Present 2.34.2, user-site; ~499 KB | HTTPS proxy and persistent connections | Apache-2.0 plus transitive notices | Pin full dependency closure; current repo has no lock. |
| `curl_cffi` | Missing | Browser TLS impersonation for sites requiring it; upstream recommended optional extra | MIT plus bundled curl/impersonation obligations | Important compatibility gap; high native-binary/security/update impact. Isolate to Phase B. |
| `pycryptodomex` | Missing | AES-128 HLS and other data decryption; optional, not a DRM bypass | BSD-2-Clause | Compatibility gap for authorized encrypted HLS. Explicitly reject DRM/key-system workflows. |
| `secretstorage` | Missing/not applicable on Windows | Linux Chromium keyring access | BSD-3-Clause | Do not bundle for Windows; reconsider only in governed authenticated Linux support. |
| Other material options | `mutagen`, AtomicParsley, xattr tools, PhantomJS not audited/present for current scope | Metadata/thumbnail/platform-specific; PhantomJS deprecated | GPL or other licences vary | Exclude until a selected feature requires them; never add broad extras without an SBOM decision. |

## 3. gallery-dl image/gallery engine assessment

Latest official stable observed: **1.32.6 (2026-07-11)**. Official distribution paths are the project on Codeberg/GitHub, PyPI stable packages, and official project-linked standalone builds. It supports galleries, albums/posts/profiles, pagination, metadata, templates, retries/backoff/rate controls, cookies, OAuth for selected extractors, and download archives/deduplication. It overlaps yt-dlp on social sites but is materially stronger for multi-image collections and gallery history.

### Integration decision

Use a **separate, optional, version-pinned subprocess for a proof of concept**, not an import and not initial-release inclusion yet. Importing GPL-2.0 code into a proprietary application creates the tightest combined-work risk. A separately invoked tool preserves a clearer process boundary, but distributing it still requires GPL-2.0 compliance, complete corresponding source/licence handling, and legal review; subprocess separation is not a licence waiver. If those obligations are unacceptable, make it a separately user-installed optional tool or exclude it.

The subprocess contract must use argument arrays (never a shell), an exact executable path and SHA-256 allowlist, a private per-job working/config directory, explicit config-ignore behavior, bounded output paths/concurrency/retries/rate, no extractor prefixes or `r:` indirection from user input, no arbitrary `-o`/plugin arguments, and no ambient `%APPDATA%`, `%USERPROFILE%`, executable-adjacent, or system configuration. Only validated HTTP(S) URLs and allowlisted extractor names enter the process. Credentials use an explicit consent flow and short-lived restricted cookie material; never scrape a browser profile implicitly.

Progress must be a versioned machine-readable adapter over controlled stdout/IPC events, normalized to item count/current item/bytes/status. Cancellation terminates the process tree with a grace period then kill; partial files remain quarantined. Normalize unsupported URL, authentication, rate limit, network, unavailable item, filename/path, archive, and internal-tool errors without leaking cookies/tokens. Archive history is per Stratum profile/site and transactionally committed only after verified output.

Installed-size impact is **unknown until the isolated PoC**; record wheel/executable, Python/runtime, Requests and optional dependency closure separately. Security risks include extractor churn, remote content, cookies/OAuth, user/global config, template traversal, plugin/import injection, excessive pagination, and sensitive metadata. Exact PoC tests: supported/unsupported dispatch, single post/album/profile pagination, duplicate archive, collision and reserved names, traversal templates, symlinks/reparse points, rate/retry/429, cancellation/process-tree kill, malformed JSON/events, auth redaction/expiry, private configuration isolation, huge gallery bounds, network loss, extractor failure, partial cleanup, GPL notice/source package, clean install/hash/rollback, and representative fixtures from document 15. Do not execute gallery-dl before Phase D authorization.

## 4. Poppler PDF engine assessment

Poppler **processes PDFs; it does not download them**. Direct/general HTTP owns download, redirects, resume, size limits, content-type/signature validation and final receipt. Latest official source release observed: **26.07.0**, signed upstream. The official site publishes signed source and labels the linked Windows CI as non-official; it does not present an official supported Windows binary distribution. Therefore no random Windows build is acceptable. A future PoC must either produce a reproducible Windows build from the signed upstream source or stop for a provenance/licence decision.

| Utility | Decision / purpose |
|---|---|
| `pdfinfo` | PoC required: metadata, page count, encryption status and basic parse validation; never sole safety proof. |
| `pdftotext` | Optional feature: explicit text extraction with encoding/output validation. |
| `pdftoppm` or `pdftocairo` | Choose one after benchmark for bounded page previews/export; prefer one renderer, not both by default. |
| `pdfimages` | Optional explicit embedded-image extraction; bound count/bytes and validate each result. |
| `pdfseparate` | Optional explicit page separation. |
| `pdfunite` | Optional explicit joining of already validated PDFs; preserve originals and verify result. |
| Other utilities | Excluded unless a later requirement and threat model justify them. |

Poppler is GPL-2.0-or-later; executable/DLL redistribution requires notices and GPL source obligations. Individual utilities may be packaged only if all runtime DLL/data dependencies, licences, symbols/build recipe, source offer and integrity records remain complete; merely copying selected EXEs does not reduce obligations automatically. Expected installed-size impact is unknown until a reproducible minimal build is measured.

Safety contract: exact executable paths and argument arrays; no shell or user-supplied flags; isolated ACL-restricted temporary directory per job; no inherited writable config/plugin paths; randomized names; file/page/pixel/time/memory/output-count limits; Job Object process-tree termination; stdout/stderr caps; cancellation and hard timeout; no network; low-privilege/sandboxed worker where practical. Validate HTTP status and final URL, reject HTML/error bodies, require `%PDF-` near the beginning plus a successful bounded parse, enforce declared/actual size, and never trust extension or MIME alone. Password-protected PDFs return `password_required`; accept a password only through explicit ephemeral input and never logs. Malformed, decompression-bomb, huge-page, recursive/object-heavy and image-bomb fixtures must fail safely. Verify every derived output's signature, path containment, nonzero bounded size, expected page/count, and reopenability before promotion; quarantine then delete failures.

## 5. Current backend execution trace

| Step | Baseline behavior and gap |
|---:|---|
| 1 URL validation | Desktop accepts only HTTP(S), max 2048 chars, hostname required, no embedded credentials. Extension independently accepts up to 8192 chars. Length policy is inconsistent. |
| 2 Canonicalisation | Extension canonicalizes YouTube/Vimeo and strips transient query keys only for candidate identity. Desktop receives and stores the operational URL; it has no normalized canonical-source field. |
| 3 Browser delivery | Authenticated loopback POST, strict extension origin, bounded JSON, rate limit and action allowlist; Qt signal routes to Quick Download or Options. |
| 4 Engine selection | No true router. All accepted browser URLs and dialog URLs enter yt-dlp, including direct files/manifests. Direct HTTP/document/image engines do not exist. |
| 5 Metadata probe | Options dialog runs `YoutubeDL.extract_info(download=False)` in a worker. Quick Download can skip the probe and uses empty metadata. Errors are shown but not normalized by class. |
| 6 Extractor selection | Entirely yt-dlp's URL dispatch. Browser recognizes page URLs only for YouTube, Vimeo and CNBC; other supported social pages may be replaced by CDN/manifests. |
| 7 Format enumeration | Reads `info.formats`; keeps standard heights with video. It does not preserve a normalized full format model. |
| 8 A/V classification | Uses yt-dlp codecs for formats/progress. Browser inference uses element/MIME/path evidence and can be uncertain. |
| 9 Resolution/container | Height-bound selectors plus output profiles. UI choice represents height, not deterministic complete-format identity/estimated final size. |
| 10 Best video/audio | Selector prefers AVC MP4 + M4A for MP4, then best video+audio, then best. Browser candidate choice occurs before yt-dlp and can pass a rendition URL that has already discarded page-level choice. |
| 11 FFmpeg merge | yt-dlp invokes repo-local FFmpeg; merge state comes from postprocessor hooks. |
| 12 Remux/transcode | Explicit output-profile postprocessors; no false extension rename in this path. MP4 may transcode when pre-probe metadata is missing, especially Quick Download. |
| 13 Temporary files | yt-dlp paths tracked from hooks; verified intermediates cleaned after success. No isolated per-job temp root; downloads share destination. |
| 14 Windows filename | yt-dlp output template `%(title)s [%(id)s]-<job>.%(ext)s`. The standalone `generate_safe_filename` helper is not used by downloads. |
| 15 Sanitisation | Relies primarily on yt-dlp. Local helper handles reserved names/characters but does not govern the main path. No single filename policy/model. |
| 16 Path length | Title helper caps 200 characters but main yt-dlp template has no repository-defined full-path budget. |
| 17 Collision | `overwrites=False` and a job suffix reduce collisions; final scan excludes pre-existing matching-extension files. Policy is not centralized or reserved atomically. |
| 18 Pause/resume/cancel | Progress hook raises pause/cancel; continuation uses yt-dlp partials. Pause drops the thread reference. Controls are cooperative, not a hard process boundary. |
| 19 Child termination | Embedded yt-dlp/FFmpeg has no owned external process handle here; cancellation is hook-based and may not promptly kill a postprocessor. Converter has explicit process-tree handling, but downloader does not. |
| 20 Final FFprobe | Strong fail-closed containment, extension/container/stream validation; only verified output is completed. |
| 21 Cleanup | Known intermediates removed only after verified success; explicit partial deletion is destination-bounded. Failed intermediates retained. |
| 22 Error presentation | Stage-prefixed and token-sanitized summaries, but no stable engine/error codes or provenance. |

## 6. Reported website/candidate defects

No live site/manual test was performed. “Confirmed” below refers to code behavior, not live compatibility.

| Reported symptom | Classification, evidence and required experiment |
|---|---|
| Facebook, Instagram and TikTok public videos not routed correctly | **Confirmed architectural gap:** `isExtractorPage` only recognizes YouTube, Vimeo and CNBC. Blob/page evidence for these sites is dropped; detected CDN/manifest candidates can bypass the site extractor. Add canonical-site routing in a later phase, then owned public fixtures and live manual tests. |
| Threads query strings entering Windows filenames | **Reported; likely generic/direct fallback gap.** Candidate labels now use path only, but the operational URL reaches yt-dlp and main output naming relies on extractor title rather than the unused local sanitizer. Capture an owned Threads case, record extractor/info/title and final planned name; do not infer a fix without reproduction. |
| X exposes video-only/audio-only streams | **Likely architecture:** X is not a recognized extractor page, so adaptive CDN representations can become DOM candidates; the picker operates before yt-dlp format composition. Use one owned post with combined and split formats; confirm selected page URL versus CDN URL and final streams. |
| Pinterest buttons receive unrelated page videos | **Reported; likely ownership ambiguity:** top-frame DOM scanning and frame/page ownership do not identify a specific media element/player beyond frame. Test multi-pin feed and single-pin page with stable element identity. |
| Snapchat Stories buttons receive unrelated page videos | Same **likely player/element ownership** gap; only frame identity is enforced. Test multiple story tiles/players and navigation reuse. |
| Snapchat unusual-extension errors | **Reported; likely direct CDN/generic selection** plus profile conversion/verification mismatch. Capture operational URL, Content-Type/Disposition, yt-dlp info and FFprobe result without storing tokens. |
| Rumble buttons receive unrelated choices | **Reported; likely page URL not preferred** because Rumble is absent from extractor-page recognition; frame-wide candidates may remain. Test multi-player/embed and page canonical route. |
| Brightcove exposes master and child renditions | **Partially corrected in code, awaiting manual test:** same-family HLS master suppresses recognized children; DASH is treated as master. Filename heuristics may miss provider-specific children. Test observation order, query refresh and multiple players. |
| HLS initialization-fragment ordering failures | **Reported; browser filter rejects obvious init/segment URLs, but download behavior unverified.** Passing a child playlist or incomplete candidate can still lose master ordering. Test known owned CMAF/HLS fixture through page and direct manifest, verify final FFprobe. |
| Browser candidates bypass best-video-plus-audio | **Confirmed design fact:** the browser can send direct/manifest rendition URLs; yt-dlp cannot recover page-level formats if the selected URL is a video-only representation. Router must prefer supported canonical pages and hide raw representations in normal mode. |
| Multiple player buttons receive frame-wide candidate sets | **Confirmed design fact:** `stratrum-get-candidates` filters tab/frame/page, not element/player identity. Existing iframe isolation helps only when players occupy separate frames. Add trusted per-element/player ID and local ownership tests later. |

## 7. Unified media router and normalized job model (design only)

The router makes one evidence-based primary decision; it must not run every engine sequentially.

1. Validate scheme/host/credentials/length and produce both immutable `original_operational_url` (secrets protected) and `canonical_source_url`.
2. Enforce legal/access policy: DRM/EME or access-control bypass request is terminal `unsupported_protected`; authentication requires the later consent flow.
3. Combine user intent, known extractor match, browser player identity, response headers, sniffed signature and confidence/provenance.
4. Route supported video/audio/playlist/live pages to pinned yt-dlp; complete media files to direct HTTP then FFprobe; HLS/DASH manifests to yt-dlp/native+FFmpeg only when complete/master evidence is adequate.
5. Route gallery/collection/image-post intent to pinned gallery-dl only when its allowlisted extractor matches; single complete images use direct HTTP.
6. Route documents/PDF to direct HTTP. After signature/content validation, optional PDF actions go to the isolated Poppler worker.
7. When evidence conflicts or confidence is low, ask the user for a simple intent or return a bounded unsupported result; never cascade through all engines.

Normalized job fields: `job_id`, `package_id`, `intent` (`video|audio|image|gallery|document|pdf|playlist|collection|live_stream`), original operational URL, canonical source URL, engine/version, extractor/version, media ID, trusted frame/player/element identity, title, uploader, duration, live/VOD state, available formats, container, video/audio codec, width, height, resolution, FPS, bitrate, known/estimated size, audio availability, subtitles, thumbnail, authentication requirement, DRM/access-control state, safe output filename, destination, temp root, collision policy, confidence, evidence/provenance, archive key, retry/cancellation state, final verification evidence and normalized error.

Deterministic video selection: default to best complete video with sound; otherwise best bounded video plus best compatible audio and merge. “Choose quality” selects a target height with deterministic lower fallback; “Smaller file” uses an explicit size/bitrate budget. Audio-only is emitted only by deliberate intent. Simple mode never offers video-only, raw segments, init fragments or internal format IDs. Never rename a media extension to simulate conversion. When metadata is incomplete, prefer a verified complete format, then bounded page-level re-probe, then a clear unavailable result. Completion requires FFprobe-verified expected streams/container inside the destination.

## 8. Simple presentation contract

Backend objects and evidence remain internal. Normal actions are: **Download video, Download audio, Download image, Download all images, Download document, Download PDF, Save PDF pages as images, Extract PDF text, Best quality, Choose quality, Smaller file**. Choices render as `[Title] — Best quality`, `1080p`, `720p`, `Smaller file`, or deliberate `Audio only`.

Normal mode never exposes HLS, DASH, manifest, m3u8, mpd, signed URLs, CDN tokens/names, raw format IDs, command arguments, or “Source 1/2”. A future explicit advanced view may show sanitized codec/container/bitrate/provenance without secrets and without enabling arbitrary arguments.
