# 01 CURRENT ARCHITECTURE

## Overview
The application is a desktop download manager designed as a clone of Internet Download Manager (IDM), built using Python and PyQt6 for the graphical interface. It interfaces with a custom Chrome/Edge browser extension to intercept media and inject download buttons.

## Core Components
- **Language & Framework:** Python 3, PyQt6 (Desktop UI), JavaScript (Browser Extension).
- **Entry Points:** 
  - `inshal_dm.py` - The primary GUI desktop application.
  - `main.py` - An alternative/legacy FastAPI backend server (seems obsolete compared to the built-in PyQt server).
- **Download Engine:** Uses `yt-dlp` to resolve formats and download media streams. Handles HTTP/HTTPS and extraction from various media platforms.
- **Conversion Engine:** Bundles `ffmpeg.exe` and `ffprobe.exe` for post-processing downloaded streams and converting files on demand.

## Browser Integration
- **Extension Path:** `IDM_Extension` (Manifest V3).
- **Mechanism:** Injects a "Download this video" hover button over `<video>` tags and adds a right-click context menu.
- **Communication:** Sends HTTP POST requests with `{ "url": "..." }` to a local TCP server running on `http://127.0.0.1:8000`. 
- **Desktop Receiver:** `inshal_dm.py` spins up a local `socketserver.TCPServer` on port 8000 to listen for URLs pushed from the browser.

## Data & Configuration
- **State Management:** Downloads history is serialized to `inshaldm_history.json` and `idm_history.json` in the current working directory.
- **No Database:** No robust SQL or local database is used; relies purely on JSON flat files.

## Build System
- **Packager:** PyInstaller, configured via `IDM_Clone.spec`.
- **Bloat Analysis:** The ~299MB size is largely attributed to bundling `ffmpeg.exe` (101MB) and `ffprobe.exe` (101MB), alongside the PyQt6 framework and Python runtime binaries.
