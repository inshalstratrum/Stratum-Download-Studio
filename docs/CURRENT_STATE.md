# Current State

- Phase: 2A.7A — documentation-only media backend capability audit complete; yt-dlp stable-target correction verified on 2026-07-12.
- Branch: `phase-2a7a-media-backend-audit`.
- Baseline preserved: `898e949fb6a04ee439acc555a29b03fe0b54df77`.
- Commit: `Phase 2A.7A: Correct yt-dlp stable target` (this correction commit; use `git rev-parse HEAD` after commit for the immutable hash).
- Audit documents: `docs/14_MEDIA_BACKEND_CAPABILITY_AUDIT.md`, `docs/15_WEBSITE_COMPATIBILITY_MATRIX.md`, and `docs/16_MEDIA_ENGINE_UPGRADE_AND_BACKEND_PLAN.md`.
- Detected backend: Stratum imports the user-site pip `yt_dlp` module, version `2026.03.17`; it does not invoke the `yt-dlp.exe` subprocess. There is no repository lock or pin. Proposed controlled stable target is `2026.07.04`, verified from official GitHub release metadata on 2026-07-12 and not installed in this phase; reconfirm the latest approved stable immediately before implementation.
- Dependency gaps: `yt-dlp-ejs`, Deno/another governed enabled JS runtime, Brotli, `curl_cffi`, and `pycryptodomex` are missing. System Node 24.14.1 exists but is not enabled by Stratum. Repo-local FFmpeg/FFprobe 8.1.1 remain GPL-enabled development binaries and release blockers.
- Engine decisions: evaluate gallery-dl 1.32.6 only as a version-pinned, optional, isolated subprocess PoC after GPL review; evaluate Poppler 26.07.0 only from verified official source through a reproducible minimal Windows-build PoC after GPL review. Neither was installed or executed.
- Compatibility matrix: all 161 numbered entries were classified by source type, access/protection, upstream extractor evidence, likely engine, fixture, priority and risk. Zero sites were newly tested or certified compatible.
- Current implementation evidence: URL/browser security controls and final FFprobe verification remain intact. The browser recognizes extractor pages only for YouTube, Vimeo and CNBC, while candidate selection is frame-wide rather than player/element-local; these are documented causes/likely causes only and were not changed.
- Scope confirmation: no application, extension, test, dependency, binary, requirements/lock, specification/build, or packaging file changed; no research artifact was stored; yt-dlp was not updated; gallery-dl and Poppler were not installed; packaging was not run.
- Unresolved release blockers: unpinned ambient dependency collection, missing modern yt-dlp support components, unproven frozen binary inclusion, GPL-enabled FFmpeg provenance/distribution, gallery-dl/Poppler GPL decisions, canonical social routing, player-local ownership, and lawful manual certification.
- Next task: only a separately authorized phase from `docs/16_MEDIA_ENGINE_UPGRADE_AND_BACKEND_PLAN.md`; browser-picker UX work and Phase 2B remain unstarted.

## Roadmap — record only

- A–C: controlled yt-dlp upgrade/dependencies and normalized video/audio selection.
- D–H: separate gallery and PDF/Poppler proofs of concept, licensing decisions and bounded engines.
- I–M: unified router, Windows-safe output planning, canonical social routing, player-local ownership and simple presentation.
- N–P: lawful fixtures/manual certification, later governed authenticated support and the release regression matrix.
- Phase 2B remains a later, separately authorized general download engine phase.
