# Current State

- Phase: 2A.7B — controlled yt-dlp upgrade and reproducible version pinning complete on 2026-07-12.
- Branch: `phase-2a7b-ytdlp-upgrade`.
- Baseline preserved: `3c7f8d71b1bc8b3814fd18d1059ea35ed58f1506`.
- Commit: `Phase 2A.7B: Pin and upgrade yt-dlp to 2026.07.04` (this phase commit; use `git rev-parse HEAD` after commit for its immutable hash).
- Approved backend: official stable GitHub release `2026.07.04`, corresponding to official PyPI package metadata `2026.7.4`. The official universal wheel is locked by SHA-256 `f11f2b11d5a8ac4059f9bdf29fa4407dc7c6bb00c5097e95ca22a7a9db518266`.
- Controlled development resolution: `scripts/bootstrap_ytdlp.ps1` uses isolated pip, the official PyPI index, wheel-only/no-dependency installation, `--require-hashes`, and a clean staging directory. It promotes the verified package into ignored repo-local `.deps/`; Stratum refuses an absent, ambient, wrong-version, wrong-path, or wheel-RECORD-invalid module.
- Runtime policy: Python-module integration remains `import yt_dlp` through `load_controlled_yt_dlp()`. Package version, module release, controlled path and installed wheel contents are verified. Ambient yt-dlp plugins and unapproved Phase B optional modules are disabled/excluded.
- Packaging gate: `StratumDownloadStudio.spec` validates `.deps`, searches it first, copies only its `yt-dlp` metadata, and excludes ambient optional backends. A clean PyInstaller build completed; recursive archive inspection found the pinned module/metadata and zero excluded optional-module entries. Generated `build/` and `dist/` artifacts remain ignored.
- Regression: 6 dependency-policy tests, 36 focused metadata/format-selection/download/cancellation/verification tests, and the final full suite of 260 tests passed.
- Scope confirmation: no new extraction feature, website routing, browser-picker change, gallery-dl, Poppler, EJS/runtime/network optional dependency, Phase 2B work, UI redesign, extension file, FFmpeg binary, or media behavior was added. Extension packaging was not rerun because extension files were unchanged.
- Remaining blockers: Phase B must separately govern `yt-dlp-ejs`, one approved JavaScript runtime, and optional network/media dependencies. Repo-local FFmpeg/FFprobe remain GPL-enabled development binaries; wider engine routing, lawful site certification and release dependency/SBOM work remain pending.
- Next task: only a separately authorized later phase from `docs/16_MEDIA_ENGINE_UPGRADE_AND_BACKEND_PLAN.md`; Phase 2B and UI redesign remain unstarted.

## Roadmap — record only

- B–C: modern yt-dlp dependency completion and normalized video/audio selection.
- D–H: separate gallery and PDF/Poppler proofs of concept, licensing decisions and bounded engines.
- I–M: unified router, Windows-safe output planning, canonical social routing, player-local ownership and simple presentation.
- N–P: lawful fixtures/manual certification, later governed authenticated support and the release regression matrix.
- Phase 2B remains a later, separately authorized general download engine phase.
