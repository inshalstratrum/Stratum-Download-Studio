# Phase 2A.5 Media Output and Functional UI Handoff

## Root causes corrected

1. Download completion trusted progress-hook intermediate filenames and then renamed extensions, which could mislabel streams or thumbnails as finished media.
2. Format selection was hard-coded, resolution selection was not populated from extractor metadata, and AVI/MOV conversion was assumed rather than explicit.
3. UI capability and conversion checks read progress-bar text instead of a persistent job state.
4. Popup Pause/Cancel, speed limiting, completion options, details, menus, and several toolbar actions were disconnected, dummy, or placeholders.
5. Save folders were a one-off text field; queue/recovery, responsive preferences, sanitized diagnostics, and a no-console development launcher were absent.

## Exact files changed

- `stratrum_download_studio.py`
- `StratrumDownloadStudio.pyw`
- `test_security.py`
- `docs/09_PHASE_2A3_MANUAL_TEST.md`
- `docs/12_PHASE_2A5_MEDIA_OUTPUT_UI_HANDOFF.md`

The PyInstaller spec remains `console=False` and continues to package `stratrum_download_studio.py`. Final distribution will launch the packaged `StratrumDownloadStudio.exe`; the `.py` and `.pyw` files are development entrypoints, not installer payload claims.

## Output-profile behavior

- Video profiles: MP4, MKV, WebM, AVI, MOV.
- Audio profiles: MP3, M4A, WAV, FLAC.
- MP4 prefers height-bounded H.264/MP4 plus AAC/M4A streams. When compatible streams are unavailable, yt-dlp is given an explicit FFmpeg video conversion postprocessor.
- MKV and WebM use explicit merge/remux targets. AVI and MOV always use explicit FFmpeg video conversion. Audio profiles use explicit FFmpeg audio extraction with the requested codec.
- Progress-hook paths are recorded only as temporary implementation details. Postprocessor hooks and final extractor metadata supply candidates; no media extension rename occurs.
- A final candidate must exist inside the selected save directory, match the requested extension, not be a thumbnail or `.f###` intermediate, pass ffprobe container validation, and contain the required video or audio stream.
- Failed download, merge, conversion, and verification stages return distinct safe errors and never report Complete. Useful intermediates remain on failure; known intermediate/partial files are deleted only after a final output passes verification.
- All related component streams remain inside one package/job and never become independent successful user downloads.

## Resolution behavior

The dialog debounces URL inspection and ignores stale extractor results. It lists only available standard heights from 4320p through 240p, with video codec, audio codec, container, and estimated size. Selection is height-based, supports portrait/non-16:9 media, falls back to the highest available lower height, labels the actual fallback, and is disabled for audio-only profiles.

## Job/controller and functional controls

- `DownloadJob` persists stable ID, package ID, source, requested/actual output and resolution, final/temporary paths, bytes, speed, ETA, priority, queue, state, retries, safe error, resumability, and timestamps.
- Explicit states cover queued, resolving, connecting, downloading, paused, merging, converting, verifying, completed, cancelled, retrying, and failed.
- `DownloadManager` owns state/capabilities, persisted incomplete-job recovery, queue order, bounded retry, maximum simultaneous downloads, priority, and stop-after-current behavior independently of `QTableWidget` labels.
- Progress painting is throttled to approximately 8 updates/second per active job while numeric metrics continue updating the job model.
- Popup Pause/Resume/Cancel routes by exact job ID, continuation is enabled, partial deletion is explicit and save-directory bounded, speed limits apply to the current yt-dlp instance, and completion actions execute before popup closure.
- Dummy connection rows were removed. The popup now provides real state/output/safe-error details.
- Conversion supports video to MP4, video/audio to MP3 or WAV, and audio to M4A. Audio-only to MP4 is rejected. Outputs remain unique and non-overwriting; failures show sanitized FFmpeg summaries.
- Recent folders are an editable MRU dropdown persisted atomically under local configuration, deduplicated, existence-filtered, capped at ten, and clearable from Options.
- View, Help, Properties, Share, queue commands, toolbar actions, diagnostics, and column controls are functional. Batch Download, Site Grabber, and Registration are visibly disabled with scope explanations rather than empty or "coming soon" behavior.

## Responsive/product foundation

Network extraction, FFmpeg, and ffprobe remain in worker threads. History writes and diagnostic export run outside the Qt UI thread; queue/config payloads are bounded and atomic. Window size, splitter sizes, column widths/visibility, format, resolution, speed, completion behavior, queue concurrency, recent folders, and stop-after-current preferences persist locally. Filename/source cells use tooltips and sanitized display URLs; horizontal scrolling remains available. Business capability logic lives in job/controller helpers so Phase 3 can later migrate from `QTableWidget` without rewriting the engine.

## Automated verification

- Preserved Phase 2A.4 tests: `102`
- Added Phase 2A.5 tests: `65`
- Total: `167 passed`
- `python -m py_compile stratrum_download_studio.py StratrumDownloadStudio.pyw` — exit `0`
- `python -m pytest -q` — exit `0`
- `git diff --check` — exit `0`
- Chromium and Firefox manifest validation — exit `0`
- Background/content/options JavaScript syntax validation — exit `0`
- Chrome, Edge, and Firefox packages generated reproducibly, allowlist-inspected, and deleted — exit `0`

## Manual Windows tests still required

The owned/authorized-content checklist in `docs/09_PHASE_2A3_MANUAL_TEST.md` remains unperformed for Phase 2A.5. Real yt-dlp/FFmpeg profile outputs, resolution fallback, postprocess failure retention, live pause/resume/cancel, rate limiting, completion actions, queue/recovery, responsive layout persistence, diagnostics, `.pyw` double-click behavior, tray exit, and port closure require Windows execution.

## Explicit deferrals

The general HTTP file engine and multi-connection HTTP segmentation are deferred to Phase 2B. Cloud remote control, captcha solving, premium-host accounts, automatic archive extraction, full site crawling, proxy credential storage, a full scheduler, and torrents are Phase 2B/2C candidates only. None was implemented. PySide6 migration, full redesign, Supabase, licensing, installer construction, Phase 2B, and Phase 3 were not started.

## Feature-preservation confirmation

Browser integration, authentication, secure multi-origin pairing, media detection, context-menu sending, history, numeric progress, downloader/resume, conversion, safe opening, tray behavior, extension packaging, and all previously working security controls remain. No product feature was intentionally removed.
