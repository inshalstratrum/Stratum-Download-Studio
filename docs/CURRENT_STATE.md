# Current State

- Phase: 2A.6C.1 — manifest selection and player-scoped candidate quality corrected.
- Branch: `phase-2a6c1-candidate-quality`.
- Commit: `Phase 2A.6C.1: Fix manifest selection and player-scoped candidates` (this phase commit; use `git rev-parse HEAD` for its immutable hash).
- Entry points: `StratumDownloadStudio.pyw` (Windows development launcher) and `stratum_download_studio.py` (`main()`).
- Test command: `python -m pytest -q`; current expected count: 251 passed.
- Working features: Phase 2A.6B one-token delivery and desktop-controlled default action remain intact. Direct media documents are detected from URL, document type, or verified response evidence. Extractor pages and HLS/DASH manifests deterministically outrank direct/network/page fallbacks; adaptive segments are removed or suppressed once the owning frame has a manifest. Trusted sender tab/frame identity scopes player buttons, including separate embedded YouTube frames.
- Candidate quality: canonical IDs discard transient signed parameters while preserving public identifiers; labels identify media kind, route type, format, reliable resolution/bitrate, and a query-safe hostname or filename. Duplicate labels receive a stable safe distinction, and candidate storage remains bounded and expiring.
- Safety boundaries: unsupported schemes, Google Video/adaptive fragments, tiny/tracking media, credential-bearing or oversized URLs, and DRM/EME media remain suppressed. No desktop/converter or Phase 2B general-file code changed.
- Unresolved blockers: no automated blockers. Manual retesting remains required for direct top-level MP4, DASH-IF, Shaka, two-iframe ownership, and representative Chrome/Edge/Firefox media pages.
- Next task: Phase 2B only when explicitly authorized.

## Roadmap — record only

- Phase 2A.6B: Popup completion, foreground activation, source URL and Quick Download.
- Phase 2A.6C: Broad secure browser media detection.
- Phase 2B — General download engine: HTTP/HTTPS files, images, documents, ZIP/RAR, installers and ISOs; resume, redirects, filenames, checksums and browser interception.
- Phase 2B.1 — Queue and performance: priorities, concurrency, per-host limits, real speed limiting, bounded retry and multi-connection segmented downloads.
- Phase 2B.2 — Link collector: collect detected links into a review screen, group into packages, choose files and destination, then move them into the queue.
- Phase 2C — Advanced tools: scheduler, archive extraction, clipboard monitoring, authenticated sites, proxy support and restricted site grabbing.
- Phase 3 — Commercial UI and packaging: PySide6 migration, original modern responsive interface, installer, console-free executable, extension onboarding, licensing and accessibility.
