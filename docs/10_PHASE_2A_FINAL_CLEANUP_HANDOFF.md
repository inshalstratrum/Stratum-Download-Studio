# Phase 2A Final Naming and Repository Cleanup Handoff

## Renames

- `inshal_dm.py` -> `stratrum_download_studio.py`
- `InshalDM` -> `StratrumDownloadStudio`
- `IDMServerHandler` -> `DownloadServerHandler`
- `IDM_Clone.spec` -> `StratrumDownloadStudio.spec`
- `IDM_Extension/` -> `browser_extension/`
- Final executable name: `StratrumDownloadStudio`
- Historical screenshot `gemini ask ss/right click buttons are visible but they are not functional.png` -> `docs/internal/evidence/context-menu-actions-historical.png`

## Deletions

The rewrite utilities, pre-Phase-2 archive, cloned UI references, caches, build outputs, old executable, generated extension ZIPs, working-directory history, debug snippet, and generated tree were removed. Git history and tag `pre-phase-2a-final-cleanup` preserve the pre-cleanup state.

<!-- deleted-paths:start -->
inshal_dm.py
IDM_Clone.spec
IDM_Extension
rewrite_inshal.py
_archive/development_scripts/rewrite_inshal.py
_archive
build
dist
docs.zip
inshaldm_history.json
tree.txt
downloads
extension_packages
browser_extension/debug-snippet.js
gemini ask ss
<!-- deleted-paths:end -->

## Concise retained tree

```text
.
|-- .gitignore
|-- StratrumDownloadStudio.spec
|-- browser_extension/
|   |-- README.md
|   |-- background.js
|   |-- manifest.json
|   |-- options.html
|   |-- options.js
|   `-- package_extension.ps1
|-- docs/
|   |-- internal/evidence/context-menu-actions-historical.png
|   `-- phase and audit documentation
|-- ffmpeg.exe
|-- ffprobe.exe
|-- stratrum_download_studio.py
`-- test_security.py
```

## Active-source forbidden patterns

These literals are intentionally recorded in documentation so regression tests can load them without hiding or splitting the search terms in executable source.

<!-- active-forbidden:start -->
inshal_dm
InshalDM
IDM_Clone
IDM Clone
IDM_Extension
rewrite_inshal
Exact IDM
IDM replica
Access-Control-Allow-Origin: *
shell=True
os.system
<!-- active-forbidden:end -->

## Verification

- `python -m py_compile stratrum_download_studio.py` — exit `0`
- `python -m pytest -q` — exit `0`; `71 passed`
- `git diff --check` — exit `0`
- Active code/config/extension forbidden-pattern scan — wrapper exit `0`; every raw `rg` search returned the expected no-match exit `1`

The original 60 Phase 2A.3 tests remain, with 11 focused final-naming, prompt, guide-action, deletion, spec, ignore, and active-source checks added.

## Extension package verification

`browser_extension/package_extension.ps1` ran with exit `0`. Both Chrome and Edge archives listed successfully with exit `0` and contained exactly five files:

- `manifest.json`
- `background.js`
- `options.html`
- `options.js`
- `README.md`

Each archive had SHA-256 `E78B02AD928660FBF5999117CF44238837FE3FF7A6B570E1D8E3523C9A2FDC24`. No debug script, token, log, configuration, absolute local path, or other file was present. Both generated ZIPs and the `extension_packages/` directory were deleted after inspection; the directory is ignored and untracked.

## FFmpeg replacement blocker

The retained `ffmpeg.exe` and `ffprobe.exe` are GPL development binaries for local testing only. They must be replaced by provenance-verified LGPL-compatible builds, with licensing obligations reviewed and documented, before commercial distribution.

## Manual Windows testing

The Windows smoke checklist in `docs/09_PHASE_2A3_MANUAL_TEST.md` remains pending. No manual browser, download, conversion, tray-exit, or port-closure result is claimed by this cleanup.

## Feature preservation

No downloader, resume, conversion, browser-integration, current app-data history, tray, or context-menu feature was removed. An AST symbol audit compared the tagged source with the final module after applying the required class renames: all 80 mapped classes/functions remained, no required feature symbol was missing, and only four prompt/guide helpers were added. The obsolete working-directory history migration was removed together with its explicitly retired legacy history artifact; current `%LOCALAPPDATA%` history persistence remains intact.

## Remaining boundary

Phase 3, PySide6 migration, redesign, licensing implementation, Supabase integration, obfuscation, and desktop-installer work were not started.
