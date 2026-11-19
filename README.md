# I-DS — I.os Download Support

**Tool by InShaLIve.os** · Open-source Windows downloader · Python / PyQt6

> Active development. Media downloading and direct HTTP file downloading now work in a Phase 2B beta, but the extension and network recovery still need real-world acceptance before this replaces IDM.

![I-DS download mark](stratum-download-studio-logo.svg)

## What works today

- **Desktop media URLs:** Add a supported video/audio URL, choose a real output format and available resolution, and start downloading through the controlled yt-dlp engine.
- **Direct file downloads (Phase 2B beta):** Desktop **File Download** supports HTTP/HTTPS PDFs, ZIPs, images, installers and other files, with progress, safe unique filenames and resumable partials when the server provides validators. Interruption, validator changes and parallel files passed recovery tests. The installed Edge executable with an isolated extension profile preserved its native download when I-DS was absent; when connected, Edge cancelled its copy and I-DS saved a verified public PDF (13,264 bytes). Real owner-profile Chrome/Edge acceptance remains pending.
- **Chrome/Edge browser companion:** Detect supported on-page media, show an in-player I-DS button, right-click a file link, or opt in to automatic handoff of supported general-file downloads.
- **Download management:** Status, pause/cancel, queue history/recovery logic, speed controls, and completion actions are implemented. Reliability still needs live long-session testing.
- **Media converter:** FFmpeg-based conversions with format validation, progress/cancellation and **Video size** presets (Original, up to 1080p / 720p / 480p / 360p / 240p). Resizing preserves aspect ratio and never upscales. A real FFmpeg 640×480 to 480×360 conversion passed FFprobe and frame decoding.
- **Local pairing:** The extension sends authenticated requests to a loopback-only desktop endpoint. Pairing tokens stay local.

The underlying source and compatibility filenames still use the historical Stratum names to preserve existing configurations and tooling. **On Windows, use `00 - OPEN I-DS` to start the GUI with the I-DS product icon and no persistent command window.** A broken old Start Stratum shortcut was moved to a reversible local backup; do not remove the internal source files.

## Still in development

- Manual Chrome/Edge installed-extension acceptance of opt-in PDF/ZIP/installer handoff and correct resume-to-browser fallback after failed desktop acceptance. Chrome downloads requiring session cookies may not transfer successfully.
- Extended HTTP retry/recovery stress testing, especially large authenticated or expiring signed links (**Phase 2B.1**).
- Further video-detection and site compatibility checks, particularly **YouTube HTTP 403**. The one-time Android-client retry completed both a verified MP4 and a **5.05 MiB MP3** through the actual I-DS worker. FFmpeg lookup was repaired for Windows WinGet links and frozen builds. Other websites/videos and owner-profile downloads remain unverified. DRM-protected content is not supported.
- A private unsigned **I-DS-Setup.exe** installer has been built and passed sandbox installation, startup, shortcut and uninstall tests without Python or FFmpeg on the test PATH. **Code signing, bundled third-party license/source compliance review, a separate clean Windows PC, Chrome owner-profile acceptance and browser-store publication** remain pending.

**Do not install from unrelated websites.** GitHub currently provides the source, not a signed public installer. The tested private setup candidate is deliberately not attached to a release until the remaining acceptance checks pass.

## Quick start on Windows

1. Install **Python 3.14** (recommended; Python 3.10+ is supported where compatible wheels exist) and **FFmpeg** for media conversions.
2. Download this branch using **Code → Download ZIP** and extract it, or clone the repository.
3. Double-click **`SETUP I-DS.cmd`** once (internet required). It checks the desktop GUI and installs verified, isolated media dependencies if needed.
4. Double-click **`00 - OPEN I-DS`** (product logo, no persistent terminal). Setup creates the shortcut. The older `START I-DS.cmd` and `START STRATUM DOWNLOADER.cmd` remain available for compatibility.

To download supported media, select **Add media**. For a direct PDF, ZIP or installer URL, select **Download file**, paste the link and choose the save folder. Existing files are not overwritten.

**New interface:** The first screen offers **Media**, **Files** and **Convert**. The header shows Active / Waiting / Finished jobs. Use the header sidebar icon to collapse or reopen categories, the small sidebar width controls to adjust it, and the **100% / 115% / 130%** control to enlarge text. These preferences are saved.

## Chrome / Edge extension

1. Open `chrome://extensions` (or `edge://extensions`), enable **Developer mode**, and choose **Load unpacked**.
2. Select the repository's **`browser_extension`** folder.
3. In I-DS desktop, open **Options → Browser Integration → Copy Token**.
4. Click the I-DS browser icon and choose **Connect with copied token**. If browser clipboard access is unavailable, expand the manual section and paste the token normally.

The on-video **I-DS** button opens **Download with Options**. Its grip lets you drag it; **−/+** compacts or expands it, and **×** dismisses it for that player. Right-click **Quick Download with I-DS** remains the fast-start alternative. Use **Download file with I-DS** on ordinary links. Under extension settings, optionally enable **Automatically use I-DS for supported browser files**. It is off by default; a failed desktop handoff resumes Chrome. Avoid enabling it for private downloads that depend on browser cookies until live compatibility testing is complete.

The extension requests broad HTTP/HTTPS site access to detect media; browser-side request observations do not copy passwords, cookies, or authorization headers.

## Windows installer development

- Repeatable local build: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows_installer.ps1` (PyInstaller, locked dependencies and FFmpeg/FFprobe required on the builder). Generated executables stay inside ignored `dist/`; nothing is published automatically.
- The staged `I-DS-Setup.exe` installs to the current Windows user's Programs folder, adds Start Menu shortcuts, and preserves user downloads/settings during uninstall. The branded executable includes FFmpeg/FFprobe and Deno; source-mode setup remains separate.
- Windows SmartScreen may warn about unsigned builds. Complete code signing, license checks and owner acceptance before creating a public release.

## Developer checks

- Python regressions: `python -m pytest -q`
- Browser tests: `node --test browser_extension/*.test.js`
- Read project ownership rules in [AGENTS.md](AGENTS.md) and current verified status in [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md).

## Community

Reports, ideas, and tested site compatibility improvements are welcome through GitHub Issues and pull requests. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and do not post passwords, private links, tokens, or personal download histories.

Licensed under [MIT](LICENSE). Download only content you own or have permission to save.
