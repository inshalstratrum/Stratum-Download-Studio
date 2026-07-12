# Current State

- Phase: 2A.7C — controlled modern yt-dlp capability dependencies complete on 2026-07-12.
- Branch: `phase-2a7c-ytdlp-capabilities`; baseline `054dabf1360089d814f40a60ef88728cd7bfc845` preserved.
- Commit: `Phase 2A.7C: Add controlled yt-dlp capability dependencies` (this phase commit; use `git rev-parse HEAD` for its immutable hash).
- Backend: yt-dlp `2026.07.04` remains pinned. Eighteen exact official PyPI wheels, including `yt-dlp-ejs 0.8.0`, are hash-locked and RECORD-verified under `.deps/`; Deno `2.8.3` is ZIP/executable-hash-verified under `.tools/`.
- Runtime: metadata and downloads pass only `{'deno': {'path': <controlled deno.exe>}}`; remote EJS components remain disabled, ambient PATH runtimes/plugins cannot be selected, and curl impersonation is available but never globally forced.
- Bootstrap: isolated wheel-only official-PyPI install and exact official GitHub Deno download occur in separate staging roots. Both bundles must verify before promotion; a failed promotion restores prior local bundles. Global Python, PATH, registry and pip are unchanged.
- Packaging: clean PyInstaller 6.20.0/Python 3.14.4 build passed. Recursive inspection found approved metadata, EJS/CA/native data and controlled Deno; excluded alternatives/plugins/self-tests had zero entries. Frozen startup stayed healthy and embedded Deno executed as `2.8.3`. Development EXE: 116,325,205 bytes, +70,986,226 bytes over 2A.7B.
- Regression: 14 dependency/capability tests, 20 focused existing contracts, and the one-time full suite of 267 tests passed. Python compilation, lock/policy verification and frozen inspection passed.
- Scope: gallery-dl, Poppler, canonical routing, picker redesign, social-site fixes, Phase 2B, UI work and extension files were not started or changed; extension packaging was not rerun.
- Remaining: listed live-site/manual checks, routing-phase failures, FFmpeg/FFprobe provenance, Mutagen GPL-2.0-or-later and complete release SBOM/licence/legal review remain release gates. This was not a commercial release build.
- Detail: `docs/18_PHASE_2A7C_YTDLP_CAPABILITIES.md`.

## Roadmap — record only

- B–C: modern yt-dlp dependency completion and normalized video/audio selection.
- D–H: separate gallery and PDF/Poppler proofs of concept, licensing decisions and bounded engines.
- I–M: unified router, Windows-safe output planning, canonical social routing, player-local ownership and simple presentation.
- N–P: lawful fixtures/manual certification, later governed authenticated support and the release regression matrix.
- Phase 2B remains a later, separately authorized general download engine phase.
