# Current State

- Phase: 2A.7D — resilient player-local browser routing and desktop handoff complete on 2026-07-13.
- Branch: `phase-2a7d-browser-routing`; baseline `a9818c0644bf88354eaa8b32993949c0daf85900` remains in the branch ancestry.
- Commit: `Phase 2A.7D: Build resilient player-local media capture` (use `git rev-parse HEAD` for its immutable hash).
- Ownership: `PlayerRegistry` assigns extension-owned player IDs and binds short activity leases, candidates and authorization to tab, frame, document generation and player. DOM reuse, navigation, removal, frame/tab closure, TTL and size bounds clear stale state; ambiguous evidence is quarantined instead of shared.
- Correlation: element/source URLs, nearest post permalink, canonical/OG/JSON-LD metadata, request frame/document URL, initiator, timing, visibility and active lease contribute provenance. Sibling players never inherit candidates; NLM/YouTube iframe isolation remains frame-local.
- Routing: player-specific public Dailymotion, Facebook, Instagram, TikTok and X post URLs normalize to canonical yt-dlp routes. Complete top-level files and safe signed master manifests remain eligible and retain their full operational URLs internally.
- Compatibility: Brightcove/Al Jazeera, Shaka, DASH-IF, CNBC, ordinary signed-master, direct MP4 and single-visible-player article fallback paths are preserved; ABC CMAF fragments, ads, renditions, components and init requests remain suppressed.
- Handoff: the background revalidates tab/frame/document/player/candidate ownership and sends structured operational URL, canonical source page, content type and allowlisted Referer/Origin/User-Agent context. Customer errors and logs redact credentials and query secrets.
- Desktop: request context is used by yt-dlp/manifest handling; Windows output names remove query-derived extensions, control/reserved names and overlong paths while preserving real media extensions and deterministic collision suffixes. Final FFprobe verification is unchanged.
- UI: simple mode exposes one preferred combined page/master/file candidate when possible, with only title and trustworthy Best quality/resolution labels; component formats are never described as complete video.
- Regression: 41 deterministic offline JS tests and the one-time full pytest collection of 287 tests pass. Modified JS/Python syntax checks and `git diff --check` pass.
- Scope: history persistence, dependencies, yt-dlp pins, gallery-dl, Poppler, Phase 2B, extension manifests and packaging were not changed; packaging was not rerun.
- Manual retests: live social-feed downloads, multi-player SPA navigation/DOM reuse, embedded players, signed-master refresh and NLM iframe behavior remain required before release.
