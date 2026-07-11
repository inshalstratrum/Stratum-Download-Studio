# 06 EVIDENCE APPENDIX (Phase 2A Checkpoint)

## 1. Exact Vulnerable File and Line References
- **`inshal_dm.py` line 606 & 711:** `os.startfile(d['final_path'])` (Allows executing downloaded arbitrary `.exe`/`.bat` files).
- **`inshal_dm.py` line 611 & 712:** `subprocess.Popen(f'explorer /select,"{os.path.normpath(d["final_path"])}"')` (Command injection via unescaped string formatting).
- **`inshal_dm.py` line 52-54:** `Access-Control-Allow-Origin: *` in `IDMServerHandler` (Cross-Origin resource sharing vulnerability).

## 2. Dependency Names and Detected Versions
- **Python Runtime**
- **PyQt6** (GUI framework)
- **yt-dlp** (Download extraction library)
*(Note: No `requirements.txt` was found, relying on system environment imports).*

## 3. All subprocess and os.startfile Usages
- `inshal_dm.py:106`: `subprocess.run([get_ffmpeg_path(), '-y', '-i', ...])` (Safe argument list usage).
- `inshal_dm.py:606`: `os.startfile(d['final_path'])`
- `inshal_dm.py:611`: `subprocess.Popen(f'explorer /select,"{os.path.normpath(d["final_path"])}"')`
- `inshal_dm.py:711`: `os.startfile(filepath)`
- `inshal_dm.py:712`: `subprocess.Popen(f'explorer /select,"{os.path.normpath(filepath)}"')`

## 4. All Network Listeners and External Requests
- **Listener:** `socketserver.TCPServer(("127.0.0.1", 8000), IDMServerHandler)` in `inshal_dm.py`.
- **Extension Request:** `fetch("http://127.0.0.1:8000/add_download")` in `background.js`.
- **External Requests:** Internal `yt-dlp` requests to various video host endpoints.

## 5. All File-Write Locations
- **History File:** `inshaldm_history.json` written to Current Working Directory (`inshal_dm.py:482`).
- **Download Files:** Resolved dynamic paths using `os.path.join(save_dir, '%(title)s.%(ext)s')`. Fallback save directory is `~\Downloads`.
- **Converted Files:** `{base}_converted.{ext}` in the same directory as the input file (`inshal_dm.py:105`).

## 6. SHA-256 Hashes of Bundled FFmpeg
- `ffmpeg.exe`: `228D7A8556258DE907FDB55F36850078EBC7680B84EC30D84EA02E99BEC1D1EB`
- `ffprobe.exe`: `0FDE260F5ABD35C9CAFD96F594CC76365A780C1B73A90E35B6A3409EA1DB1BF0`

### 2. FFmpeg Bundling (GPL / x264 / x265)

**Finding:** The provided binaries `ffmpeg.exe` and `ffprobe.exe` are built with `--enable-gpl`, `--enable-libx264`, and `--enable-libx265`.
- **Evidence:** Running `ffmpeg.exe -version` outputs the GPL build configuration.
- **Risk:** Distributing a GPL-licensed FFmpeg binary within a closed-source commercial product requires careful GPL compliance. While the interaction method between the Python app and FFmpeg affects the exact licensing requirements, relying on a GPL build in a proprietary product carries significant compliance risk.
- **Remediation:** Replacement with a verified LGPL FFmpeg build (which excludes GPL components like x264/x265) is the recommended release path for commercial distribution.

### 3. PyQt6 Licensing

**Finding:** The application currently runs on PyQt6.
- **Risk:** PyQt6 is licensed under the GPL. Commercial proprietary distribution using PyQt6 requires purchasing a commercial license from Riverbank Computing, otherwise the source code must be released under the GPL.
- **Remediation:** An unresolved release blocker for Phase 3 is the migration of the UI from PyQt6 to PySide6 (LGPL) or acquiring a commercial PyQt6 license.

## 9. `main.py` References
A repository-wide search confirms `main.py` is entirely unreferenced. It is an abandoned FastAPI test file.

## 10. Usage of History JSON Files
A repository-wide search confirms `idm_history.json` is not referenced by any running code. `inshaldm_history.json` is actively used by `inshal_dm.py` for state management.
