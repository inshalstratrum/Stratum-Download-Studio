# 03 DEPENDENCY AND LICENCE AUDIT

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
