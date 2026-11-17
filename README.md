# I-DS — I.os Download Support

**Tool by InShaLIve.os** · Open-source Windows downloader · Python / PyQt6

> Active development. The program is a media downloader and converter today; it is **not yet** a drop-in replacement for all IDM browser-file interception features.

![I-DS download mark](stratum-download-studio-logo.svg)

## What works today

- **Desktop media URLs:** Add a supported video/audio URL, choose a real output format and available resolution, and start downloading through the controlled yt-dlp engine.
- **Chrome/Edge browser companion:** Detect supported on-page media, show an in-player I-DS button, or right-click a link/video/audio and send it to the local desktop app.
- **Download management:** Status, pause/cancel, queue history/recovery logic, speed controls, and completion actions are implemented. Reliability still needs live long-session testing.
- **Media converter:** FFmpeg-based conversions with format validation and progress/cancellation controls where supported.
- **Local pairing:** The extension sends authenticated requests to a loopback-only desktop endpoint. Pairing tokens stay local.

The underlying source and compatibility filenames still use the historical Stratum names to preserve existing configurations and tooling.

## Still in development

- Automatic takeover of ordinary Chrome/Edge downloads such as PDF, ZIP, installers, images, and other non-media files (**Phase 2B**).
- Reliable interruption/reconnection/resume tests for large general HTTP files (**Phase 2B.1**).
- Further video-detection and site compatibility checks, including live YouTube testing. Site access and formats can change; DRM-protected content is not supported.
- Polished installer, signed releases, a published browser store extension, and full accessibility/manual desktop acceptance tests.

**Do not install from unrelated websites.** This repository's launcher uses the Python source; it is not a signed Windows installer.

## Quick start on Windows

1. Install Python 3.10 or newer and FFmpeg.
2. Clone this repository, or choose **Code → Download ZIP** above and extract it.
3. In the extracted folder, run `python -m pip install -r requirements.txt` once.
4. Double-click **`START I-DS.cmd`**. The historical `START STRATUM DOWNLOADER.cmd` remains supported.

To download supported media, select **Add URL** in I-DS and choose the desired save folder and output.

## Chrome / Edge extension

1. Open `chrome://extensions` (or `edge://extensions`), enable **Developer mode**, and choose **Load unpacked**.
2. Select the repository's **`browser_extension`** folder.
3. In I-DS desktop, open **Options → Browser Integration → Copy Token**.
4. Click the **I-DS browser toolbar icon**, paste the token into Settings, and save it.

Use the on-video **I-DS** button or right-click **Quick Download with I-DS**. Your normal browser-file downloads still use Chrome/Edge until Phase 2B is completed.

The extension requests broad HTTP/HTTPS site access to detect media; browser-side request observations do not copy passwords, cookies, or authorization headers.

## Developer checks

- Python regressions: `python -m pytest -q`
- Browser candidate tests: `node --test browser_extension/media_candidates.test.js`
- Read project ownership rules in [AGENTS.md](AGENTS.md) and current verified status in [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md).

## Community

Reports, ideas, and tested site compatibility improvements are welcome through GitHub Issues and pull requests. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and do not post passwords, private links, tokens, or personal download histories.

Licensed under [MIT](LICENSE). Download only content you own or have permission to save.
