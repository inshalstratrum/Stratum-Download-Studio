# Current State

- Phase: 2A.6C — broad secure browser media detection restored.
- Branch: `phase-2a6c-media-detection`.
- Commit: `Phase 2A.6C: Restore broad secure media detection` (this phase commit; use `git rev-parse HEAD` for its immutable hash).
- Entry points: `StratumDownloadStudio.pyw` (Windows development launcher) and `stratum_download_studio.py` (`main()`).
- Test command: `python -m pytest -q`; current expected count: 248 passed.
- Working features: Phase 2A.6B desktop-controlled default action and one-token authenticated delivery remain intact. Chromium/Firefox MV3 content scripts now run in permitted frames and use event-driven HTML5/source/iframe/SPA/resource detection plus non-blocking media-response evidence. Candidates are stable, deduplicated, frame-aware, bounded, expiring, and routed as safe page, direct media, HLS, or DASH choices through a small picker when needed.
- Safety boundaries: segment and Google Video fragment floods, unsupported schemes, tiny/tracking media, credentials in URLs, oversized URLs, and DRM/EME media are suppressed. No cookies, authorization headers, request bodies, or private page contents are sent to the desktop. General files and Phase 2B behavior remain out of scope.
- Unresolved blockers: no automated blockers. Manual Chrome/Edge/Firefox checks on representative local deterministic pages and authorized live media remain required; no live-site or DRM-bypass testing was performed.
- Next task: Phase 2B only when explicitly authorized.

## Roadmap — record only

- Phase 2A.6B: Popup completion, foreground activation, source URL and Quick Download.
- Phase 2A.6C: Broad secure browser media detection.
- Phase 2B — General download engine: HTTP/HTTPS files, images, documents, ZIP/RAR, installers and ISOs; resume, redirects, filenames, checksums and browser interception.
- Phase 2B.1 — Queue and performance: priorities, concurrency, per-host limits, real speed limiting, bounded retry and multi-connection segmented downloads.
- Phase 2B.2 — Link collector: collect detected links into a review screen, group into packages, choose files and destination, then move them into the queue.
- Phase 2C — Advanced tools: scheduler, archive extraction, clipboard monitoring, authenticated sites, proxy support and restricted site grabbing.
- Phase 3 — Commercial UI and packaging: PySide6 migration, original modern responsive interface, installer, console-free executable, extension onboarding, licensing and accessibility.
