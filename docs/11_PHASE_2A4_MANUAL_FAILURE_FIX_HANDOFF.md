# Phase 2A.4 Manual-Failure Fix Handoff

## Root causes

1. The desktop constructor scheduled an extension-install prompt during normal startup even though no consumer store listing or installer workflow existed.
2. The original content script had been removed during an earlier security correction, leaving only context-menu integration and no secure automatic media button replacement.
3. Configuration stored one scalar `allowed_origin`, so installing the extension in a second Chromium browser or Firefox displaced or conflicted with the first browser.
4. Download progress depended primarily on formatted yt-dlp strings and did not propagate downloaded bytes, total bytes, or real filenames through one coherent signal/slot path.
5. Extension connection failures were console-only, packaging covered only Chromium, and Firefox signing/manifest requirements were undocumented.

## Files changed

- `stratrum_download_studio.py`
- `test_security.py`
- `browser_extension/manifest.json`
- `browser_extension/background.js`
- `browser_extension/content.js` (new secure implementation; historical code was inspected but not restored)
- `browser_extension/options.html`
- `browser_extension/options.js`
- `browser_extension/package_extension.ps1`
- `browser_extension/README.md`
- `firefox_extension/manifest.json`
- `firefox_extension/README.md`
- `docs/09_PHASE_2A3_MANUAL_TEST.md`
- `docs/11_PHASE_2A4_MANUAL_FAILURE_FIX_HANDOFF.md`

## Desktop and pairing corrections

- Normal desktop startup no longer schedules or displays extension-store/install dialogs. Browser Integration remains a deliberate manual Options action.
- Configuration atomically persists a backward-compatible `allowed_origins` list and migrates a valid legacy `allowed_origin` value.
- Up to six unique, strictly validated Chrome/Edge/Firefox origins can coexist. Duplicates are ignored, the maximum is enforced, and malformed origins are discarded.
- Token authentication, complete request validation, rate limiting, and URL validation still occur before a new origin is paired.
- Browser Integration lists origins, supports **Remove Selected**, and provides **Reset All Pairings**.

## Media integration and connection UX

- Chromium injects one production content script only on HTTP/HTTPS pages. One MutationObserver handles existing and dynamically added video/audio elements; the per-element map prevents duplicate buttons.
- No download starts automatically. A URL is selected and sent only after the user clicks the Stratrum button.
- Direct HTTP/HTTPS media sources are sent directly. Blob, `srcObject`, MediaSource-style, HLS/DASH/fragmented, unavailable, and malformed sources fall back to the authorized page URL.
- The default-enabled **Show download button on detected media** option can remove and restore buttons at runtime.
- The content script does not read cookies, forms, browser history, or unrelated page text and sends no telemetry.
- Missing token, desktop-unavailable, unauthorized-token, and pairing-rejected conditions produce visible, token-free guidance. Existing right-click link/video/audio behavior remains.

## Progress correction

- Progress uses numeric `downloaded_bytes`, `total_bytes` or `total_bytes_estimate`, `speed`, and `eta` when present.
- Percentage is calculated from bytes and clamped to 0-100. ANSI/formatted-string parsing is retained only as a defensive fallback.
- Real filename, percentage, downloaded/total bytes, speed, ETA, and current status flow through one typed progress signal to the main table and popup.
- The popup updates its stored filename and title when metadata arrives. Malformed progress data safely degrades instead of crashing.
- Finished hooks and successful completion set 100%; no timer-generated or fake percentage was added.

## Automated verification

- Existing Phase 2A tests retained: `71`
- New production-focused cases: `31`
- Total: `102 passed`
- `python -m py_compile stratrum_download_studio.py` — exit `0`
- `python -m pytest -q` — exit `0`
- `git diff --check` — exit `0`
- Chromium manifest JSON validation — exit `0`
- Firefox manifest JSON validation — exit `0`
- `node --check` for background, content, and options scripts — exit `0`

## Package verification

`browser_extension/package_extension.ps1` produced three separate archives with exit `0` in two consecutive runs. Corresponding first/second hashes matched, proving reproducibility for unchanged sources. Each archive listed with exit `0`, contained exactly `manifest.json`, `background.js`, `content.js`, `options.html`, `options.js`, and `README.md`, and contained no token, log, configuration, debug script, or absolute local path.

- Chrome SHA-256: `DC0EF531B25C06D124FC3363C3CF78989BEA7AD6393B482CD5BA20F48F14E26F`
- Edge SHA-256: `DC0EF531B25C06D124FC3363C3CF78989BEA7AD6393B482CD5BA20F48F14E26F`
- Firefox SHA-256: `B162BF20F212D5EF48ADB6DF6A8F7AA3F3789EB0CBF4D8892B5782DB1A0FD777`

Generated packages were deleted after inspection and remain ignored/untracked.

## Browser-installation limitations

- Chrome consumer release requires Chrome Web Store publication.
- Edge consumer release requires Microsoft Edge Add-ons publication.
- Firefox self-distribution requires a Mozilla-signed XPI. The unsigned development ZIP is not customer-ready. Mozilla requires an extension ID for signing Manifest V3 and documents signed XPI requirements for self-distribution.
- Enterprise force-install policies apply to managed organizations, not normal customers.
- Chromium development loads `browser_extension/` once with **Load unpacked**; developers must not install that source and an extracted submission package simultaneously.
- A dormant Manifest V3 service worker normally sleeps until an event wakes it; this is not a connection failure.
- A future installer may show a user-confirmed browser-extension suggestion after installation. Silent consumer installation is not claimed or implemented.

Mozilla references: [Manifest V3 Gecko settings](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/browser_specific_settings), [background scripts](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Background_scripts), and [self-distribution/signing](https://extensionworkshop.com/documentation/publish/self-distribution/).

## Manual tests still pending

The authorized-content Windows/browser checklist in `docs/09_PHASE_2A3_MANUAL_TEST.md` remains unperformed. Chrome/Edge unpacked loading, dynamic media buttons, direct/fallback URL behavior, visible errors, simultaneous three-browser pairing, Firefox temporary loading, real transfer progress, restart/reset, tray exit, and port closure still require manual execution.

## Feature-preservation confirmation

No downloader, resume, conversion, current app-data history, token security, rate limiting, safe file opening, tray, or context-menu feature was removed. The right-click workflow remains alongside the restored opt-out media button. PyQt6 migration, redesign, installer construction, Supabase, licensing implementation, obfuscation, and Phase 3 work were not started.
