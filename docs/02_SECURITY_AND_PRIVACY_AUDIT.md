# 02 SECURITY AND PRIVACY AUDIT

## Network Security Risks
- **CORS Vulnerability (Critical):** The local server (`http.server.BaseHTTPRequestHandler` in `stratrum_download_studio.py`) sets `Access-Control-Allow-Origin: *`. Any malicious website the user visits can send POST requests to `127.0.0.1:8000` and arbitrarily start downloads or exhaust system resources.
- **Browser Extension Permissions (High):** The extension requests `<all_urls>` host permissions, which triggers strict reviews on Chrome Web Store and is a privacy concern.

## Local Execution Risks
- **Command Injection (High):** Opening a folder uses `subprocess.Popen(f'explorer /select,"{os.path.normpath(d["final_path"])}"')`. If a downloaded filename contains double quotes, it could allow arbitrary command execution on the host Windows machine.
- **Arbitrary File Execution (High):** The "Open" button uses `os.startfile(d['final_path'])`. If the user downloads a malicious `.exe`, `.bat`, or `.scr` file, the application executes it without a Windows SmartScreen prompt or warning.
- **Unsafe File Writes / Path Traversal (Medium):** The app trusts the filename provided by `yt-dlp`. While `yt-dlp` does sanitize, manual input or unexpected server responses could lead to unintended overwrites.

## Data Storage & Privacy
- **Hardcoded File Paths (Medium):** `inshaldm_history.json` is saved in the application directory. If installed in `C:\Program Files`, this will crash due to lack of write permissions, or it will write to VirtualStore. It must be moved to `%APPDATA%`.
- **Sensitive Data Logging:** The application currently prints/stores raw URLs which could contain session tokens, passwords, or personal identifiers in query strings.

## Obsolete & Suspicious Code
- `main.py` is an unused FastAPI implementation that exposes similar functionality. It should be removed to reduce the attack surface.
- Unsafe exception swallowing (e.g., `except: pass` in `load_downloads_from_file`).
