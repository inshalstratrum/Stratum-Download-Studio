# Current State

- Phase: 2A.7D — canonical page routing and player-local browser selection complete on 2026-07-13.
- Branch: `phase-2a7d-browser-routing`; baseline `a9818c0644bf88354eaa8b32993949c0daf85900` preserved.
- Commit: `Phase 2A.7D: Add canonical player-local browser routing` (this phase commit; use `git rev-parse HEAD` for its immutable hash).
- Ownership: every media element receives an extension-generated player ID. Candidate observation, listing, removal and download authorization are bound to tab, frame, canonical page and player; navigation, DOM reuse, frame blocking and tab closure clear stale ownership.
- Routing: public Dailymotion, Facebook, Instagram, TikTok and X post URLs normalize to canonical yt-dlp page routes. Operational Facebook identifiers and full signed media URLs are preserved; customer-visible labels and errors do not expose tokens or transport details.
- Selection: simple mode prefers a complete top-level file, safe master manifest or canonical page and suppresses audio-only, video-only, renditions, fragments and stale candidates. A single remaining choice is sent directly.
- Isolation: sibling players do not share candidates. Network evidence is player-bound only for a sole owner and is purged if ownership becomes ambiguous; NLM/YouTube iframe isolation remains frame-local.
- Storage: candidate and player-owner stores are TTL/size bounded, and background requests reject mismatched tab, frame, page, player or candidate IDs.
- Regression: 36 deterministic offline JS tests and 26 focused Python extension/security contracts pass. The one-time full suite recorded 267 passes and one unrelated Qt 10 ms timing failure; that exact test passed immediately in isolation. Syntax and diff validation pass.
- Scope: desktop filename logic, history persistence, dependencies, yt-dlp pins, gallery-dl, Poppler, Phase 2B, extension manifests and packaging were not changed; packaging was not rerun.
- Manual retests: live Dailymotion/Facebook/Instagram/TikTok/X downloads, multi-player feeds, SPA navigation/DOM reuse, signed master refresh and NLM iframe behavior remain required before release.
