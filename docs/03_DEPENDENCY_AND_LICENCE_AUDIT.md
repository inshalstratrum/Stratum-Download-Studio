# 03 DEPENDENCY AND LICENCE AUDIT

## 2026-11-19 — Current private Windows release-candidate check

- **Verified local build:** Gyan FFmpeg **9.0-full_build-www.gyan.dev**, static, `--enable-gpl --enable-version3`; installed `LICENSE` contains the full **GPLv3 text (35,147 bytes)**, and its `README.txt` identifies the reported source at [FFmpeg commit d32b387f2b](https://github.com/FFmpeg/FFmpeg/commit/d32b387f2b). Earlier build script incorrectly captured `ffmpeg -L` from stdout and could bundle an empty license file. The revised builder copies and validates the license supplied with the actual FFmpeg binary, and embeds the compact `THIRD_PARTY_NOTICES.txt`.
- **Public redistribution is still blocked:** GPLv3 binary distribution requires exact corresponding source and relevant dependent-library notices; a source commit link and license text alone do **not** establish complete compliance. Read [FFmpeg's official legal guidance](https://ffmpeg.org/legal.html) and [Gyan's build provenance](https://www.gyan.dev/ffmpeg/builds/) before distributing. The app is open-source MIT but that does **not** waive its bundled dependencies' obligations.
- **PyQt6:** GPLv3/commercial dual-license. Open-source distribution must respect applicable GPLv3 conditions. The 2026-07 report below discusses *closed-source commercial* distribution; it is historical, **not** a current determination that this open-source app requires an immediate PySide6 migration.
- **Signing:** The private Windows setup was verified as **NotSigned**. Three SignTool candidates were found, but **zero usable code-signing certificates** were present in the inspected Windows certificate stores. Signing, Windows reputation tests, source-provenance/notice review and owner/browser acceptance remain release blockers. Do not publish the unsigned setup or represent it as release-ready.
- **Packaging evidence:** The Windows installer passed sandbox setup/upgrade/uninstall and starts the bundled application without Python or FFmpeg on PATH. The private corrected setup was rebuilt and independently inspected: embedded GPLv3 license **35,147 bytes** matched the supplier license byte-for-byte, notices and exact prior tested app were present, and sandbox installation/uninstallation passed. Public redistribution compliance remains unverified.
- **Existing controls:** Keep the browser loopback token, no DRM bypass, safe outputs and all compatible source/runtime functionality. This section updates licensing *facts only*, not source ownership or the application's architecture.

---

## Legal & Licensing Overview
Transforming this project into a commercial closed-source product (Stratrum Download Studio) requires strict adherence to third-party licenses.

### 1. PyQt6 (GUI Framework)
- **License:** GPLv3 or Commercial.
- **Risk:** CRITICAL. You cannot distribute a closed-source commercial application using PyQt6 under the GPLv3 license. You must either:
  a) Purchase a commercial license from Riverbank Computing.
  b) Migrate the UI to PySide6 (which is LGPL and allows dynamic linking in closed-source commercial applications).

### 2. FFmpeg & FFprobe (Media Processing)
- **License:** LGPLv2.1+ / GPLv2+ (depending on build configuration).
- **Risk:** HIGH. If the bundled `ffmpeg.exe` was compiled with GPL flags (e.g., libx264, libx265), the entire application might be considered a combined work if not carefully isolated.
- **Remediation:** Ensure you bundle an LGPL-only build of FFmpeg, or instruct the user to download FFmpeg themselves. Command-line execution of FFmpeg is generally considered safe if properly isolated, but you must include FFmpeg's license and source code offer in the EULA.

### 3. yt-dlp (Download Engine)
- **License:** Unlicense (Public Domain).
- **Risk:** LOW. It can be freely used in commercial software.
- **Policy Risk:** `yt-dlp` contains extractors for DRM/copyrighted platforms. To comply with the rule of "not bypassing DRM", ensure you do not explicitly market the tool for copyright infringement, and append the required legal disclaimer in the UI.

### 4. Python (Runtime)
- **License:** Python Software Foundation (PSF) License.
- **Risk:** LOW. Allowed in commercial products. Include the PSF license notice.

### 5. UIUX Reference Images
- **Risk:** HIGH. The `uiux_reference` folder contains screenshots and icons directly ripped from Internet Download Manager (IDM).
- **Remediation:** Delete these images from the repository to avoid copyright and trademark infringement claims from Tonec Inc.

### Summary of Actions Required
- Switch to PySide6 to avoid PyQt6 GPL violations (or buy a commercial license).
- Verify FFmpeg build flags and include appropriate notices.
- Remove IDM clone assets entirely.
# Phase 2A FFmpeg Distribution Blocker

The repository-retained `ffmpeg.exe` and `ffprobe.exe` are GPL development binaries. They are kept temporarily for local development testing only. Before any commercial distribution, both files must be replaced with provenance-verified LGPL-compatible builds and the corresponding license/source-offer obligations must be reviewed and documented. This replacement is a release blocker, not a completed licensing decision.
