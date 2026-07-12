# Current State

- Phase: 2A.6C.2 — adaptive manifest routing and duplicate player overlays corrected.
- Branch: `phase-2a6c2-manifest-routing`.
- Commit: `Phase 2A.6C.2: Fix adaptive manifest routing and duplicate player overlays` (this phase commit; use `git rev-parse HEAD` for its immutable hash).
- Entry points: `StratumDownloadStudio.pyw` (Windows development launcher) and `stratum_download_studio.py` (`main()`).
- Test command: `python -m pytest -q`; current expected count: 254 passed.
- Working features: Phase 2A.6B one-token delivery and desktop-controlled Quick Download/Options routing remain intact. Supported extractor pages, complete HLS/DASH manifests (with required query strings), explicit video/audio/source URLs, strong attachment responses, and verified top-level media documents are the only candidate routes. DASH-IF, Shaka, Brightcove-style and ordinary HLS traffic use trusted tab/frame ownership and manifest-first selection.
- Candidate quality: network `.mp4`/`.m4a`/`.webm` extensions alone are not complete-file evidence. CMAF init/media segments, byte ranges, adaptive representations, Google Video fragments, generic page fallbacks, and unstored download requests are rejected. Frame-local video/audio elements are the only automatic overlay targets, preventing parent iframe duplicates.
- Safety boundaries: DRM/EME blocks and clears the owning frame with a clear unsupported message. Existing scheme, credential, payload, origin, token and rate controls remain unchanged; FFprobe, desktop/converter and Phase 2B code were not changed.
- Unresolved blockers: no automated blockers. Manual retesting remains required for DASH-IF, Shaka, top-level MP4, NLM two-iframe ownership, Al Jazeera/Brightcove, ABC CMAF, CNBC and representative Chrome/Edge/Firefox media pages.
- Next task: Phase 2B only when explicitly authorized.

## Roadmap — record only

- Phase 2A.6B: Popup completion, foreground activation, source URL and Quick Download.
- Phase 2A.6C: Broad secure browser media detection.
- Phase 2B — General download engine: HTTP/HTTPS files, images, documents, ZIP/RAR, installers and ISOs; resume, redirects, filenames, checksums and browser interception.
- Phase 2B.1 — Queue and performance: priorities, concurrency, per-host limits, real speed limiting, bounded retry and multi-connection segmented downloads.
- Phase 2B.2 — Link collector: collect detected links into a review screen, group into packages, choose files and destination, then move them into the queue.
- Phase 2C — Advanced tools: scheduler, archive extraction, clipboard monitoring, authenticated sites, proxy support and restricted site grabbing.
- Phase 3 — Commercial UI and packaging: PySide6 migration, original modern responsive interface, installer, console-free executable, extension onboarding, licensing and accessibility.
