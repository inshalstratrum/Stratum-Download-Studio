# Current State

- Phase: 2A.6C.3 — audio-only manifest classification and master-manifest preference corrected.
- Branch: `phase-2a6c2-manifest-routing`.
- Commit: `Phase 2A.6C.3: Prefer master manifests and classify audio variants` (this phase commit; use `git rev-parse HEAD` for its immutable hash).
- Entry points: `StratumDownloadStudio.pyw` (Windows development launcher) and `stratum_download_studio.py` (`main()`).
- Test command: `python -m pytest -q`; current expected count: 254 passed.
- Working features: Phase 2A.6B one-token delivery and desktop-controlled Quick Download/Options routing remain intact. Supported extractor pages, complete HLS/DASH manifests with signed operational queries, explicit video/audio/source URLs, strong attachment responses, and verified top-level media documents remain the only candidate routes.
- Candidate quality: strong playlist naming/MIME evidence identifies audio-only HLS variants as audio. A recognised same-family HLS master suppresses inferior audio/video/unknown children in either observation order; deterministic player identifiers, frame identity and path families prevent cross-player suppression. Labels remain query-safe while the latest signed URL is retained for delivery.
- Safety boundaries: DRM/EME blocks and clears the owning frame with a clear unsupported message. Existing scheme, credential, payload, origin, token and rate controls remain unchanged; FFprobe, desktop/converter and Phase 2B code were not changed.
- Unresolved blockers: no automated blockers. Manual retesting remains required for Shaka master/audio variants and Al Jazeera/Brightcove master preference; the previously passed DASH-IF, MP4, NLM, ABC CMAF, CNBC and browser compatibility cases should receive a regression spot-check.
- Next task: Phase 2B only when explicitly authorized.

## Roadmap — record only

- Phase 2A.6B: Popup completion, foreground activation, source URL and Quick Download.
- Phase 2A.6C: Broad secure browser media detection.
- Phase 2B — General download engine: HTTP/HTTPS files, images, documents, ZIP/RAR, installers and ISOs; resume, redirects, filenames, checksums and browser interception.
- Phase 2B.1 — Queue and performance: priorities, concurrency, per-host limits, real speed limiting, bounded retry and multi-connection segmented downloads.
- Phase 2B.2 — Link collector: collect detected links into a review screen, group into packages, choose files and destination, then move them into the queue.
- Phase 2C — Advanced tools: scheduler, archive extraction, clipboard monitoring, authenticated sites, proxy support and restricted site grabbing.
- Phase 3 — Commercial UI and packaging: PySide6 migration, original modern responsive interface, installer, console-free executable, extension onboarding, licensing and accessibility.
