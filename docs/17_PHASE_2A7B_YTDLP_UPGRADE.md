# Phase 2A.7B Controlled yt-dlp Upgrade

Date: 2026-07-12

Baseline: `3c7f8d71b1bc8b3814fd18d1059ea35ed58f1506`

Target: official stable release `2026.07.04` / PyPI package `2026.7.4`

## Approved provenance

- Official release: <https://github.com/yt-dlp/yt-dlp/releases/tag/2026.07.04>
- Official PyPI release: <https://pypi.org/project/yt-dlp/2026.7.4/>
- Artifact: `yt_dlp-2026.7.4-py3-none-any.whl`
- SHA-256: `f11f2b11d5a8ac4059f9bdf29fa4407dc7c6bb00c5097e95ca22a7a9db518266`
- Licence form: upstream states that its Git repository, PyPI source distribution and PyPI wheel contain Unlicense code. No standalone PyInstaller yt-dlp executable is used.

GitHub identifies the immutable stable release as `2026.07.04`; verified PyPI metadata identifies the same July 4, 2026 release as `2026.7.4`. The repository accepts only that explicit mapping.

## Controlled installation and verification

Run from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap_ytdlp.ps1
```

The bootstrap performs an isolated, official-PyPI-only, wheel-only, no-dependency, no-cache installation with pip hash enforcement into `.deps-staging/`. `stratum_dependency_policy.py` verifies exact package metadata and every hashed wheel `RECORD` entry before replacing ignored `.deps/`.

At source startup, Stratum resolves `yt_dlp` only from `.deps/`, verifies package `2026.7.4`, module `2026.07.04`, path containment and wheel contents, and disables ambient plugins. It hides user/system site packages while yt-dlp inventories optional dependencies, preventing Phase B capabilities from leaking into development or tests.

The PyInstaller specification independently fails closed unless the same `.deps/` distribution passes verification. It searches that root first, copies metadata only from that root, and excludes all unapproved optional yt-dlp modules. Rollback is commit-based: check out the prior approved phase and regenerate its controlled dependency state; never mutate a customer binary or run `yt-dlp -U`.

## Verification evidence

- Official wheel acquisition and hash-locked bootstrap: passed.
- Installed package metadata/module/path/RECORD verification: passed (`2026.7.4` / `2026.07.04`).
- Focused dependency-policy tests: 6 passed.
- Focused metadata, format-selection, download, cancellation and final-media verification regression: 36 passed.
- Clean PyInstaller build: passed with PyInstaller 6.20.0 and Python 3.14.4.
- Recursive frozen-archive inspection: pinned yt-dlp module and `yt_dlp-2026.7.4.dist-info` present; zero excluded ambient optional-module entries.
- Built development artifact: 45,338,979 bytes; SHA-256 `CC6C80CA2BDC6A5F6898DC667C0E44F91A489B5A748CDE9A1966D301E2405A71`. This is local build evidence, not a signed release or a cross-machine reproducibility claim.
- Full automated suite after generated build cleanup: 260 passed.

No live website/manual compatibility test was performed, and no such claim is made. Missing optional dependencies, new extraction behavior, routing/picker work, gallery-dl, Poppler, Phase 2B and UI changes remain outside this phase.
