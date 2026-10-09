# ⚡ Stratum Download Studio

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![GUI: PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![yt--dlp](https://img.shields.io/badge/Media%20Engine-yt--dlp-red.svg)](https://github.com/yt-dlp/yt-dlp)
[![Browser Support](https://img.shields.io/badge/Extensions-Chrome%20%7C%20Firefox-orange.svg)](#-browser-integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An advanced, open-source **desktop Internet Download Manager (IDM)** alternative built with Python and PyQt6. Features native Chrome & Firefox browser extensions, multi-segmented accelerated downloading, media stream sniffing, and integrated FFmpeg format transcoding.

---

## 🌟 Key Capabilities

### 1. 🚀 Accelerated Multi-Connection Engine
* **Segmented Chunk Downloading**: Splits files into parallel chunks to saturate available bandwidth.
* **Resilient Pause & Resume**: Seamlessly resumes broken or interrupted downloads without losing data.
* **Automatic Retry & Reconnection**: Handles network dropouts gracefully with exponential backoff.

### 2. 🌐 Native Browser Integration
* **Chrome / Edge Extension** (`browser_extension/`): Manifest V3 extension capturing file downloads and web video streams directly from your browser.
* **Firefox Extension** (`firefox_extension/`): Native Firefox add-on with web media detection hooks.
* **Local WebSocket Bridge**: Instant, low-latency communication between browser tabs and the desktop application on `127.0.0.1`.

### 3. 🎥 Universal Video & Audio Extraction
* **Powered by yt-dlp**: Extracts high-resolution streams from thousands of websites (YouTube, Vimeo, TikTok, Facebook, Twitter/X, Instagram, and more).
* **Format & Quality Picker**: Select video resolutions (4K, 1440p, 1080p, 720p) or extract audio tracks directly.
* **Cookie & Session Authentication**: Seamlessly authenticates with logged-in browser sessions for private or member-only media.

### 4. 🎛️ Post-Download Media Converter
* Automatically transcodes completed downloads using FFmpeg:
  * **Video**: MP4 (H.264/AAC), MKV, WebM (VP9/Opus)
  * **Audio**: MP3, M4A, FLAC, WAV
* **Faststart Optimization**: Automatically injects MP4 `+faststart` moov flags for immediate web playback.

---

## 📂 Repository Structure

```
Stratum-Download-Studio/
├── stratum_download_studio.py     # Main PyQt6 desktop application (3,800+ lines)
├── stratum_dependency_policy.py   # Secure dependency isolation and yt-dlp bridge
├── StratumDownloadStudio.pyw      # Windowless launcher entrypoint
├── START STRATUM DOWNLOADER.cmd   # Windows 1-Click launcher
├── browser_extension/             # Chrome / Chromium Manifest V3 extension
├── firefox_extension/             # Mozilla Firefox extension
├── docs/                          # Architecture documentation & design handoffs
├── test_*.py                      # Automated test suite (security, converter, detection)
├── requirements.txt               # Python dependencies
├── .gitignore
├── LICENSE                        # MIT License
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* **Windows 10 / 11**, macOS, or Linux
* **Python 3.10+**
* **FFmpeg**: Installed on system PATH (or placed in application folder) for video remuxing and conversions.

### 2. Installation
Clone the repository and install requirements:

```bash
git clone https://github.com/inshalstratrum/Stratum-Download-Studio.git
cd Stratum-Download-Studio
pip install -r requirements.txt
```

### 3. Launching Application
Double-click `START STRATUM DOWNLOADER.cmd`, or run:

```bash
python stratum_download_studio.py
```

---

## 🧩 Browser Extension Setup

### Google Chrome / Microsoft Edge / Brave
1. Open `chrome://extensions` in your browser.
2. Enable **Developer mode** (toggle in top right).
3. Click **Load unpacked** and select the `browser_extension/` folder from this repository.
4. Pin the Stratum extension to your toolbar.

### Mozilla Firefox
1. Open `about:debugging#/runtime/this-firefox` in Firefox.
2. Click **Load Temporary Add-on...**.
3. Select `manifest.json` inside the `firefox_extension/` folder.

---

## 🧪 Running Automated Tests

Run the test suite to verify media detection, converter controls, and security sandboxing:

```bash
python -m unittest test_media_detection.py
python -m unittest test_converter_controls.py
python -m unittest test_security.py
```

---

## 📄 License

This software is released under the [MIT License](LICENSE).
Built with the open-source power of [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [PyQt6](https://riverbankcomputing.com/software/pyqt/).
