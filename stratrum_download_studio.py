import sys
import os
import uuid
import json
import http.server
import subprocess
import re
from datetime import datetime
import secrets
import tempfile
import traceback
import urllib.parse
import string
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
import yt_dlp

APP_NAME = "Stratrum Download Studio"
MAX_REQUEST_BODY = 16 * 1024
CONVERSION_TIMEOUT_SECONDS = 30 * 60
CHROME_STORE_URL = "https://chromewebstore.google.com/"
EDGE_STORE_URL = "https://microsoftedge.microsoft.com/addons/"
_conversion_name_lock = threading.Lock()


def generate_safe_filename(save_dir, title, ext):
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}

    title = re.sub(r'[\x00-\\/:*?"<>|]', '_', title)
    title = title.strip('. ')
    if not title:
        title = "download"
    elif title.upper() in reserved:
        title = title + "_file"

    if len(title) > 200:
        title = title[:200]

    filename = f"{title}.{ext}"
    out_path = os.path.join(save_dir, filename)

    counter = 1
    while os.path.exists(out_path):
        filename = f"{title}_{counter}.{ext}"
        out_path = os.path.join(save_dir, filename)
        counter += 1

    return out_path


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QToolBar,
    QDialog, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QProgressBar, QSystemTrayIcon, QMenu, QStyle, QSpinBox, QVBoxLayout,
    QHBoxLayout, QHeaderView, QSplitter, QTreeWidget, QTreeWidgetItem,
    QPushButton, QComboBox, QMenuBar, QFormLayout, QGroupBox, QTabWidget,
    QWidget, QGridLayout, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QEvent, QTimer, QUrl
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QPixmap, QDesktopServices

# ==========================================
# MODERN UI STYLESHEET
# ==========================================
MODERN_STYLE = """
QMainWindow, QDialog { background-color: #f0f0f0; color: #000000; }
QTableWidget { background-color: #ffffff; border: 1px solid #a0a0a0; gridline-color: #e0e0e0; color: #000000; }
QTableWidget::item:selected { background-color: #0078d7; color: #ffffff; }
QHeaderView::section { background-color: #f0f0f0; padding: 4px; border: 1px solid #a0a0a0; color: #000000; }
QPushButton { background-color: #e1e1e1; color: black; border-radius: 2px; padding: 5px 15px; border: 1px solid #adadad; }
QPushButton:hover { background-color: #e5f1fb; border: 1px solid #0078d7; }
QPushButton:pressed { background-color: #cce4f7; border: 1px solid #005499; }
QLineEdit, QComboBox { padding: 4px; border: 1px solid #a0a0a0; background-color: white; color: black; }
QProgressBar { text-align: center; border: 1px solid #a0a0a0; background-color: #e6e6e6; color: black; }
QProgressBar::chunk { background-color: #06b025; }
QTreeWidget { border: 1px solid #a0a0a0; background-color: white; color: black; }
QTreeWidget::item:selected { background-color: #0078d7; color: white; }
QTabWidget::pane { border: 1px solid #a0a0a0; background: #f0f0f0; }
"""

def get_ffmpeg_path():
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, 'ffmpeg.exe')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_ffmpeg = os.path.join(base_dir, 'ffmpeg.exe')
    if os.path.exists(local_ffmpeg): return local_ffmpeg
    return 'ffmpeg'

def validate_token(token):
    return isinstance(token, str) and len(token) == 64 and all(c in string.hexdigits for c in token)

class RateLimiter:
    def __init__(self, rate, per):
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.monotonic()
        self.lock = threading.Lock()

    def allow(self):
        with self.lock:
            current = time.monotonic()
            time_passed = current - self.last_check
            self.last_check = current
            self.allowance += time_passed * (self.rate / self.per)
            if self.allowance > self.rate:
                self.allowance = self.rate
            if self.allowance < 1.0:
                return False
            self.allowance -= 1.0
            return True

def default_app_data_root():
    local_app_data = os.environ.get('LOCALAPPDATA')
    if not local_app_data:
        local_app_data = str(Path.home() / 'AppData' / 'Local')
    return Path(local_app_data) / 'Stratrum' / 'DownloadStudio'


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f"{path.stem}_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


@dataclass
class AppConfig:
    app_data_root: Path
    config_path: Path
    history_path: Path
    auth_token: str
    allowed_origin: str
    rate_limiter: RateLimiter
    extension_prompt_preference: str = 'ask'
    state_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def persisted_values(self):
        return {
            'auth_token': self.auth_token,
            'allowed_origin': self.allowed_origin,
            'extension_prompt_preference': self.extension_prompt_preference,
        }

    def persist(self):
        with self.state_lock:
            atomic_write_json(self.config_path, self.persisted_values())

    def pair_origin(self, origin):
        if not validate_extension_origin(origin):
            raise ValueError("Malformed extension origin")
        with self.state_lock:
            if self.allowed_origin and self.allowed_origin != origin:
                raise ValueError("A different browser origin is already paired")
            if self.allowed_origin == origin:
                return
            previous = self.allowed_origin
            self.allowed_origin = origin
            try:
                self.persist()
            except Exception:
                self.allowed_origin = previous
                raise

    def reset_pairing(self):
        with self.state_lock:
            previous = self.allowed_origin
            self.allowed_origin = ''
            try:
                self.persist()
            except Exception:
                self.allowed_origin = previous
                raise

    def set_extension_prompt_preference(self, preference):
        if preference not in {'ask', 'later', 'never'}:
            raise ValueError("Invalid extension prompt preference")
        previous = self.extension_prompt_preference
        self.extension_prompt_preference = preference
        try:
            self.persist()
        except Exception:
            self.extension_prompt_preference = previous
            raise


def initialize_runtime(app_data_root=None, auth_token=None, allowed_origin=None,
                       history_path=None, rate_limiter=None):
    root = Path(app_data_root) if app_data_root is not None else default_app_data_root()
    config_path = root / 'config' / 'config.json'
    for directory in ('config', 'history', 'logs', 'temp'):
        (root / directory).mkdir(parents=True, exist_ok=True)

    stored = {}
    if config_path.exists():
        try:
            with config_path.open('r', encoding='utf-8') as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                stored = loaded
        except (OSError, json.JSONDecodeError):
            stored = {}

    selected_token = auth_token if auth_token is not None else stored.get('auth_token', '')
    if not validate_token(selected_token):
        selected_token = secrets.token_hex(32)

    selected_origin = allowed_origin if allowed_origin is not None else stored.get('allowed_origin', '')
    if selected_origin and not validate_extension_origin(selected_origin):
        selected_origin = ''

    prompt_preference = stored.get('extension_prompt_preference', 'ask')
    if prompt_preference not in {'ask', 'later', 'never'}:
        prompt_preference = 'ask'

    runtime = AppConfig(
        app_data_root=root,
        config_path=config_path,
        history_path=Path(history_path) if history_path is not None else root / 'history' / 'history.json',
        auth_token=selected_token,
        allowed_origin=selected_origin,
        rate_limiter=rate_limiter or RateLimiter(5, 1.0),
        extension_prompt_preference=prompt_preference,
    )
    runtime.history_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.persist()
    return runtime


def should_show_extension_prompt(app_config):
    return not app_config.allowed_origin and app_config.extension_prompt_preference != 'never'


def apply_extension_prompt_choice(app_config, choice):
    if choice == 'later':
        app_config.set_extension_prompt_preference('later')
    elif choice == 'never':
        app_config.set_extension_prompt_preference('never')
    elif choice != 'install':
        raise ValueError("Invalid extension prompt choice")


def browser_extension_guide_path(base_directory=None):
    base = Path(base_directory) if base_directory is not None else Path(__file__).resolve().parent
    extension_directory = base / 'browser_extension'
    readme_path = extension_directory / 'README.md'
    if readme_path.is_file():
        return readme_path.resolve()
    if extension_directory.is_dir():
        return extension_directory.resolve()
    raise FileNotFoundError("Browser extension guide is unavailable")


def open_browser_extension_guide(opener=None, base_directory=None):
    guide_path = browser_extension_guide_path(base_directory)
    if opener is not None:
        opener(guide_path)
        return True
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide_path)))


def validate_extension_origin(origin):
    if not isinstance(origin, str) or not origin or len(origin) > 200:
        return False
    try:
        parsed = urllib.parse.urlsplit(origin)
        port = parsed.port
    except ValueError:
        return False
    if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or port:
        return False
    host = parsed.hostname or ''
    if parsed.scheme == 'chrome-extension':
        return bool(re.fullmatch(r'[a-p]{32}', host))
    if parsed.scheme == 'moz-extension':
        try:
            return str(uuid.UUID(host)) == host.lower()
        except (ValueError, AttributeError):
            return False
    return False

def validate_url(url):
    if not url or len(url) > 2048:
        return False, "URL missing or too long"
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False, "Invalid URL scheme"
        if not parsed.hostname:
            return False, "Hostname required"
        if parsed.username or parsed.password:
            return False, "Embedded credentials not allowed"
        return True, ""
    except Exception:
        return False, "Malformed URL"

def validate_request(headers, rfile, runtime):
    auth_header = headers.get('X-Stratrum-Auth', '')
    if not isinstance(auth_header, str) or not secrets.compare_digest(auth_header, runtime.auth_token):
        return 401, b'{"error": "Unauthorized"}'

    origin = headers.get('Origin', '')
    if not validate_extension_origin(origin):
        return 403, b'{"error": "Origin not allowed"}'
    with runtime.state_lock:
        if runtime.allowed_origin and origin != runtime.allowed_origin:
            return 403, b'{"error": "Origin not allowed"}'

    content_type = headers.get('Content-Type', '')
    media_type = content_type.split(';', 1)[0].strip().lower()
    parameters = content_type.split(';')[1:]
    if media_type != 'application/json':
        return 415, b'{"error": "Unsupported Media Type"}'
    if any(parameter.strip().lower() not in {'charset=utf-8', 'charset="utf-8"'} for parameter in parameters):
        return 415, b'{"error": "Unsupported Media Type"}'

    content_length_header = headers.get('Content-Length')
    if content_length_header is None:
        return 400, b'{"error": "Missing Content-Length"}'
    try:
        content_length = int(content_length_header)
    except (TypeError, ValueError):
        return 400, b'{"error": "Invalid Content-Length"}'

    if content_length < 0:
        return 400, b'{"error": "Negative Content-Length"}'
    if content_length > MAX_REQUEST_BODY:
        return 413, b'{"error": "Payload too large"}'

    try:
        post_data = rfile.read(content_length)
        if len(post_data) != content_length:
            return 400, b'{"error": "Incomplete request body"}'
        data = json.loads(post_data.decode('utf-8'))
    except UnicodeDecodeError:
        return 400, b'{"error": "Invalid UTF-8"}'
    except json.JSONDecodeError:
        return 400, b'{"error": "Malformed JSON"}'

    if not isinstance(data, dict):
        return 400, b'{"error": "JSON object required"}'

    url = data.get('url', '')
    is_valid, err_msg = validate_url(url)
    if not is_valid:
        return 400, json.dumps({"error": err_msg}).encode('utf-8')

    if not runtime.rate_limiter.allow():
        return 429, b'{"error": "Too many requests"}'

    try:
        runtime.pair_origin(origin)
    except ValueError:
        return 403, b'{"error": "Origin not allowed"}'
    except OSError:
        return 500, b'{"error": "Unable to persist browser pairing"}'

    return 200, url


def recorded_save_directory(download_record):
    configured = download_record.get('save_dir')
    if configured:
        return Path(configured)
    outtmpl = download_record.get('outtmpl', '')
    if outtmpl:
        return Path(outtmpl).parent
    raise ValueError("Download record has no configured save directory")


def resolve_recorded_file(download_record, path=None):
    raw_path = path if path is not None else download_record.get('final_path', '')
    if not raw_path:
        raise ValueError("Download record has no completed file path")
    save_directory = recorded_save_directory(download_record).resolve(strict=True)
    candidate = Path(raw_path).resolve(strict=True)
    if not candidate.is_file():
        raise ValueError("Completed path is not a file")
    try:
        candidate.relative_to(save_directory)
    except ValueError as exc:
        raise ValueError("Completed file is outside its recorded download directory") from exc
    return candidate


DANGEROUS_EXTENSIONS = {
    '.exe', '.com', '.bat', '.cmd', '.msi', '.msp', '.mst', '.scr', '.pif', '.cpl',
    '.hta', '.jar', '.js', '.jse', '.vbs', '.vbe', '.wsf', '.wsh', '.ps1', '.psm1',
    '.psd1', '.py', '.pyw', '.reg', '.lnk', '.url', '.scf', '.application',
    '.appref-ms', '.gadget', '.chm', '.ahk'
}


def is_dangerous_file(filepath):
    return Path(filepath).suffix.lower() in DANGEROUS_EXTENSIONS


def open_download_file(download_record, opener=None):
    path = resolve_recorded_file(download_record)
    if is_dangerous_file(path):
        raise PermissionError("Opening dangerous downloaded file types is disabled")
    opener = opener or os.startfile
    opener(str(path))
    return path


def open_download_folder(download_record, popen=None, path=None):
    selected_path = resolve_recorded_file(download_record, path=path)
    popen = popen or subprocess.Popen
    popen(['explorer', '/select,', str(selected_path)])
    return selected_path


def store_conversion_output(download_record, output_path):
    converted_path = resolve_recorded_file(download_record, path=output_path)
    download_record['converted_output_path'] = str(converted_path)
    return converted_path

# ==========================================
# 1. LOCAL SERVER
# ==========================================
class DownloadServerHandler(http.server.BaseHTTPRequestHandler):
    def send_cors_headers(self):
        origin = self.headers.get('Origin', '')
        runtime = self.server.app_config
        if origin == runtime.allowed_origin or (not runtime.allowed_origin and validate_extension_origin(origin)):
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Stratrum-Auth')

    def do_OPTIONS(self):
        self.send_response(200); self.send_cors_headers(); self.end_headers()

    def do_POST(self):
        if self.path != '/add_download':
            self.send_response(404); self.end_headers(); return

        status_code, result = validate_request(self.headers, self.rfile, self.server.app_config)

        self.send_response(status_code); self.send_cors_headers(); self.end_headers()

        if status_code == 200:
            self.wfile.write(b'{"status": "success"}')
            self.server.url_signal.emit(result)
        else:
            self.wfile.write(result)

    def log_message(self, format, *args):
        pass

class ServerThread(QThread):
    url_received = pyqtSignal(str)
    def __init__(self, app_config):
        super().__init__()
        self.app_config = app_config
    def run(self):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 8000), DownloadServerHandler)
        self.httpd.app_config = self.app_config
        self.httpd.url_signal = self.url_received
        self.httpd.serve_forever()
    def stop(self):
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
            self.httpd.server_close()

# ==========================================
# 2. ASYNC FORMAT FETCHER
# ==========================================
class FormatFetcherThread(QThread):
    formats_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    def __init__(self, url):
        super().__init__(); self.url = url
    def run(self):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
                self.formats_ready.emit(ydl.extract_info(self.url, download=False))
        except Exception as e:
            self.error_occurred.emit(str(e))

class ConvertThread(QThread):
    finished = pyqtSignal(str, bool, str, str)
    def __init__(self, row_id, input_file, target_ext):
        super().__init__()
        self.row_id = row_id; self.input_file = input_file; self.target_ext = target_ext
    def run(self):
        claim_path = None
        try:
            input_path = Path(self.input_file)
            if not input_path.is_file():
                self.finished.emit(self.row_id, False, "Input file does not exist", "")
                return

            valid_exts = {'mp4', 'mkv', 'avi', 'mov', 'webm', 'mp3', 'wav', 'flac', 'm4a'}
            target_ext = self.target_ext.lower()
            if target_ext not in valid_exts:
                self.finished.emit(self.row_id, False, f"Unsupported target format: {self.target_ext}", "")
                return

            title = input_path.stem + "_converted"
            with _conversion_name_lock:
                counter = 0
                while True:
                    suffix = '' if counter == 0 else f'_{counter}'
                    output_path = input_path.parent / f'{title}{suffix}.{target_ext}'
                    claim_path = output_path.with_name(output_path.name + '.claim')
                    if output_path.exists():
                        counter += 1
                        continue
                    try:
                        claim_fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    except FileExistsError:
                        counter += 1
                        continue
                    os.close(claim_fd)
                    break

            command = [get_ffmpeg_path(), '-n', '-i', str(input_path), str(output_path)]
            run_kwargs = {
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'timeout': CONVERSION_TIMEOUT_SECONDS,
            }
            creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            if creation_flags:
                run_kwargs['creationflags'] = creation_flags
            process = subprocess.run(command, **run_kwargs)
            if process.returncode != 0:
                self.finished.emit(self.row_id, False, "Conversion failed", "")
            elif not output_path.is_file():
                self.finished.emit(self.row_id, False, "Conversion produced no output file", "")
            else:
                self.finished.emit(self.row_id, True, "Conversion complete", str(output_path))
        except subprocess.TimeoutExpired:
            self.finished.emit(self.row_id, False, "Conversion timed out and was cancelled", "")
        except Exception as e:
            self.finished.emit(self.row_id, False, str(e), "")
        finally:
            if claim_path is not None:
                try:
                    claim_path.unlink()
                except FileNotFoundError:
                    pass

# ==========================================
# 3. DOWNLOAD ENGINE ("THE SPEED GRABBER")
# ==========================================
class PauseException(Exception): pass

class DownloadThread(QThread):
    progress = pyqtSignal(str, str, float, str, str)
    status = pyqtSignal(str, str)
    finished = pyqtSignal(str, bool, str, str)
    size_updated = pyqtSignal(str, str, str)

    def __init__(self, id, url, outtmpl, format_str, target_ext):
        super().__init__()
        self.id = id; self.url = url; self.outtmpl = outtmpl
        self.format_str = format_str; self.target_ext = target_ext.lower()
        self.paused = False; self.final_filename = ""

    def format_size(self, bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0: return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} TB"

    def progress_hook(self, d):
        if self.paused: raise PauseException("Paused")
        if d['status'] == 'downloading':
            filename = os.path.basename(d['filename'])
            percent_clean = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%').strip('%'))
            try: percent = float(percent_clean)
            except ValueError: percent = 0.0

            speed = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', 'N/A'))
            eta = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', 'N/A'))

            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total_bytes: self.size_updated.emit(self.id, filename, self.format_size(total_bytes))
            self.progress.emit(self.id, filename, percent, speed, eta)
            self.status.emit(self.id, 'Downloading')
        elif d['status'] == 'finished':
            self.final_filename = d.get('info_dict', {}).get('_filename', d['filename'])

    def run(self):
        try:
            ydl_opts = {
                'outtmpl': self.outtmpl,
                'format': self.format_str,
                'progress_hooks': [self.progress_hook],
                'quiet': True, 'no_warnings': True, 'noplaylist': True,
                'ffmpeg_location': get_ffmpeg_path(),
                # --- THE SPEED GRABBER MULTIPLEXING ---
                'concurrent_fragment_downloads': 10,
                'buffersize': 1024 * 32,
            }

            audio_formats = ['mp3', 'wav', 'flac', 'm4a']
            if self.target_ext in audio_formats:
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': self.target_ext, 'preferredquality': '192'}]
            else:
                ydl_opts['merge_output_format'] = self.target_ext

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                title = info.get('title', 'download')

            safe_final_path = generate_safe_filename(os.path.dirname(self.outtmpl), title, self.target_ext)

            if self.final_filename and os.path.exists(self.final_filename):
                os.replace(self.final_filename, safe_final_path)
                self.final_filename = safe_final_path

            if os.path.exists(self.final_filename):
                self.size_updated.emit(self.id, os.path.basename(self.final_filename), self.format_size(os.path.getsize(self.final_filename)))

            self.status.emit(self.id, 'Completed')
            self.finished.emit(self.id, True, '', self.final_filename)

        except PauseException: self.status.emit(self.id, 'Paused')
        except Exception as e: self.status.emit(self.id, 'Error'); self.finished.emit(self.id, False, str(e), "")

# ==========================================
# 4. STRATRUM DOWNLOAD STUDIO UI
# ==========================================
class DownloadFileInfoDialog(QDialog):
    def __init__(self, parent=None, prefill_url=""):
        super().__init__(parent)
        self.setWindowTitle("Download File Info")
        self.setFixedSize(650, 300)

        layout = QVBoxLayout()

        # Grid layout for exact spacing
        grid = QGridLayout()

        # 1. URL
        grid.addWidget(QLabel("URL"), 0, 0)
        self.url_edit = QLineEdit(prefill_url)
        grid.addWidget(self.url_edit, 0, 1, 1, 4)

        # 2. Category & Format
        grid.addWidget(QLabel("Category"), 1, 0)
        self.category_combo = QComboBox()
        self.category_combo.addItems(["General", "Compressed", "Documents", "Music", "Programs", "Video"])
        grid.addWidget(self.category_combo, 1, 1, 1, 2)

        grid.addWidget(QLabel("Format:"), 1, 3, alignment=Qt.AlignmentFlag.AlignRight)
        self.ext_combo = QComboBox()
        self.ext_combo.addItems(["MP4", "MKV", "AVI", "MOV", "WEBM", "MP3", "WAV", "FLAC", "M4A"])
        grid.addWidget(self.ext_combo, 1, 4)

        # 3. Save As
        grid.addWidget(QLabel("Save As"), 2, 0)
        self.save_dir_edit = QLineEdit(os.path.join(os.path.expanduser('~'), 'Downloads'))
        grid.addWidget(self.save_dir_edit, 2, 1, 1, 3)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self.browse_dir)
        grid.addWidget(browse_btn, 2, 4)

        # 4. Remember Path Checkbox
        self.remember_cb = QCheckBox("Remember this path for category")
        self.remember_cb.setChecked(True)
        grid.addWidget(self.remember_cb, 3, 1, 1, 4)

        # 5. Description
        grid.addWidget(QLabel("Description"), 4, 0)
        self.desc_edit = QLineEdit()
        grid.addWidget(self.desc_edit, 4, 1, 1, 4)

        layout.addLayout(grid)

        # Size Preview
        self.info_lbl = QLabel("Fetching File Data...")
        self.info_lbl.setStyleSheet("color: #0078d7; font-weight: bold; margin-top: 10px;")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_lbl)

        # Buttons (Bottom)
        btn_layout = QHBoxLayout()
        self.dl_later_btn = QPushButton("Download Later")
        self.dl_later_btn.clicked.connect(self.reject)
        self.start_btn = QPushButton("Start Download")
        self.start_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.dl_later_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        self.ext_combo.currentTextChanged.connect(self.on_ext_changed)
        if prefill_url: self.fetch_formats()
        self.url_edit.textChanged.connect(self.fetch_formats)
        self.on_ext_changed("MP4")

    def on_ext_changed(self, text):
        if text in ["MP3", "WAV", "FLAC", "M4A"]: self.category_combo.setCurrentText("Music")
        elif text in ["MP4", "MKV", "AVI", "MOV", "WEBM"]: self.category_combo.setCurrentText("Video")

    def fetch_formats(self):
        url = self.url_edit.text().strip()
        if not url: return
        self.info_lbl.setText("Connecting to server...")
        self.start_btn.setEnabled(False)
        self.fetcher = FormatFetcherThread(url)
        self.fetcher.formats_ready.connect(self.on_formats_ready)
        self.fetcher.error_occurred.connect(self.on_fetch_error)
        self.fetcher.start()

    def on_formats_ready(self, info):
        size = info.get('filesize_approx') or info.get('filesize')
        size_str = f" | Size: {round(size/1024/1024, 2)} MB" if size else ""
        self.info_lbl.setText(f"File Ready{size_str}")
        self.start_btn.setEnabled(True)

    def on_fetch_error(self, error_msg):
        self.info_lbl.setText("Ready to Download (Dynamic Size)")
        self.start_btn.setEnabled(True)

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if directory: self.save_dir_edit.setText(directory)

    def get_data(self):
        return self.url_edit.text().strip(), self.save_dir_edit.text().strip(), 0, self.ext_combo.currentText()


class DownloadProgressPopup(QDialog):
    def __init__(self, filename, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"0% {filename}")
        self.setFixedSize(500, 280) # Closed details state
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.details_open = False
        self.filename = filename

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Tabs
        self.tabs = QTabWidget()
        status_tab = QWidget()
        speed_tab = QWidget()
        options_tab = QWidget()
        self.tabs.addTab(status_tab, "Download status")
        self.tabs.addTab(speed_tab, "Speed Limiter")
        self.tabs.addTab(options_tab, "Options on completion")

        # Status Tab Layout
        status_layout = QFormLayout()
        status_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        url_lbl = QLineEdit(url)
        url_lbl.setReadOnly(True)
        url_lbl.setStyleSheet("border: none; background: transparent;")
        status_layout.addRow("", url_lbl)

        self.status_lbl = QLabel("Receiving data...")
        self.status_lbl.setStyleSheet("color: blue;")
        status_layout.addRow("Status", self.status_lbl)

        self.size_lbl = QLabel("Calculating...")
        status_layout.addRow("File size", self.size_lbl)

        self.downloaded_lbl = QLabel("0 MB (0%)")
        status_layout.addRow("Downloaded", self.downloaded_lbl)

        self.speed_lbl = QLabel("0 MB/sec")
        status_layout.addRow("Transfer rate", self.speed_lbl)

        self.time_lbl = QLabel("Calculating...")
        status_layout.addRow("Time left", self.time_lbl)

        status_layout.addRow("Resume capability", QLabel("Yes"))
        status_tab.setLayout(status_layout)

        main_layout.addWidget(self.tabs)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(15)
        main_layout.addWidget(self.progress_bar)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.details_btn = QPushButton("Show details >>")
        self.details_btn.clicked.connect(self.toggle_details)

        self.pause_btn = QPushButton("Pause")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.details_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

        # Details Panel (Connections Table)
        self.details_widget = QWidget()
        det_layout = QVBoxLayout()
        det_layout.addWidget(QLabel("Start positions and download progress by connections"))

        self.conn_table = QTableWidget(4, 3) # Dummy 4 connections to mimic UI
        self.conn_table.setHorizontalHeaderLabels(["N.", "Downloaded", "Info"])
        self.conn_table.verticalHeader().setVisible(False)
        self.conn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.conn_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.conn_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        # Populate dummy multiplexing lines
        for i in range(4):
            self.conn_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.conn_table.setItem(i, 1, QTableWidgetItem("Receiving..."))
            self.conn_table.setItem(i, 2, QTableWidgetItem("Downloading data"))

        det_layout.addWidget(self.conn_table)
        self.details_widget.setLayout(det_layout)
        self.details_widget.hide()

        main_layout.addWidget(self.details_widget)
        self.setLayout(main_layout)

    def toggle_details(self):
        if self.details_open:
            self.details_widget.hide()
            self.details_btn.setText("Show details >>")
            self.setFixedSize(500, 280)
            self.details_open = False
        else:
            self.details_widget.show()
            self.details_btn.setText("<< Hide details")
            self.setFixedSize(500, 450)
            self.details_open = True

    def update_stats(self, percent, speed, eta, total_size=""):
        self.setWindowTitle(f"{int(percent)}% {self.filename}")
        self.progress_bar.setValue(int(percent))
        self.speed_lbl.setText(speed)
        self.time_lbl.setText(eta)
        self.downloaded_lbl.setText(f"({percent}%)")
        if total_size: self.size_lbl.setText(total_size)

# ==========================================
# 5. MAIN APP: STRATRUM DOWNLOAD STUDIO
# ==========================================
class BrowserIntegrationDialog(QDialog):
    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self.setWindowTitle("Browser Integration")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Copy the local authentication token into the Chrome or Edge extension. "
            "The token is masked and must never be shared or logged."
        ))
        token_field = QLineEdit(app_config.auth_token)
        token_field.setReadOnly(True)
        token_field.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(token_field)

        actions = QHBoxLayout()
        copy_button = QPushButton("Copy Token")
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(app_config.auth_token))
        actions.addWidget(copy_button)
        reset_button = QPushButton("Reset Browser Pairing")
        reset_button.clicked.connect(self.reset_pairing)
        actions.addWidget(reset_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        paired = app_config.allowed_origin or "No browser extension is currently paired."
        self.pairing_label = QLabel(f"Paired origin: {paired}")
        layout.addWidget(self.pairing_label)

    def reset_pairing(self):
        answer = QMessageBox.question(
            self,
            "Reset Browser Pairing",
            "Reset the paired browser extension? The next fully valid authenticated request will create a new pairing.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.app_config.reset_pairing()
        except OSError:
            QMessageBox.warning(self, "Reset Failed", "The browser pairing could not be persisted.")
            return
        self.pairing_label.setText("Paired origin: No browser extension is currently paired.")


class StratrumDownloadStudio(QMainWindow):
    def __init__(self, app_config):
        super().__init__()
        self.app_config = app_config
        self.setWindowTitle("Stratrum Download Studio")
        self.setGeometry(100, 100, 1150, 680)
        self.downloads = []; self.popups = {}
        self.init_ui()
        self.init_tray_icon()
        self.load_downloads_from_file()
        self.init_server()
        if should_show_extension_prompt(self.app_config):
            QTimer.singleShot(0, self.show_extension_install_prompt)

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)

        tray_menu = QMenu()
        tray_menu.addAction("Show Stratrum Download Studio", self.show_normal)
        tray_menu.addSeparator()
        tray_menu.addAction("Exit", self.force_quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick: self.show_normal()

    def show_normal(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and self.windowState() & Qt.WindowState.WindowMinimized:
            event.accept(); self.hide()
            self.tray_icon.showMessage("Stratrum Download Studio", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 1500)
            return
        super().changeEvent(event)

    def closeEvent(self, event):
        event.ignore(); self.hide()

    def force_quit(self):
        self.save_downloads_to_file(); self.server_thread.stop(); self.server_thread.wait(); QApplication.quit()

    def save_downloads_to_file(self):
        save_data = []
        for row in range(self.table.rowCount()):
            bar = self.table.cellWidget(row, 3)
            status = bar.text() if bar else self.table.item(row, 3).text() if self.table.item(row, 3) else "Completed"
            if d_info := next((d for d in self.downloads if d['row'] == row), None):
                save_data.append({
                    'filename': self.table.item(row, 0).text(),
                    'size': self.table.item(row, 2).text() if self.table.item(row, 2) else "",
                    'status': status,
                    'eta': self.table.item(row, 4).text() if self.table.item(row, 4) else "",
                    'speed': self.table.item(row, 5).text() if self.table.item(row, 5) else "",
                    'date': self.table.item(row, 6).text() if self.table.item(row, 6) else "",
                    'url': self.table.item(row, 7).text() if self.table.item(row, 7) else "",
                    'id': d_info['id'], 'outtmpl': d_info['outtmpl'], 'save_dir': d_info.get('save_dir', ''),
                    'format': d_info['format'], 'ext': d_info['ext'], 'final_path': d_info.get('final_path', ''),
                    'converted_output_path': d_info.get('converted_output_path', '')
                })
        try:
            atomic_write_json(self.app_config.history_path, save_data)
        except Exception as e:
            print(f"Error saving history: {e}")

    def load_downloads_from_file(self):
        history_file = self.app_config.history_path
        if not history_file.exists(): return
        try:
            with history_file.open('r', encoding='utf-8') as f: save_data = json.load(f)
            for item in save_data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(item.get('filename', '')))
                self.table.setItem(row, 1, QTableWidgetItem(""))
                self.table.setItem(row, 2, QTableWidgetItem(item.get('size', '')))

                pb = QProgressBar(); pb.setRange(0, 100); status = item.get('status', '')
                if "Downloading" in status or "Paused" in status: pb.setValue(0); pb.setFormat("Paused")
                else: pb.setValue(100); pb.setFormat(status)

                self.table.setCellWidget(row, 3, pb)
                self.table.setItem(row, 4, QTableWidgetItem(item.get('eta', '')))
                self.table.setItem(row, 5, QTableWidgetItem(item.get('speed', '')))
                self.table.setItem(row, 6, QTableWidgetItem(item.get('date', '')))
                self.table.setItem(row, 7, QTableWidgetItem(item.get('url', '')))

                self.downloads.append({
                    'id': item.get('id', ''), 'url': item.get('url', ''), 'outtmpl': item.get('outtmpl', ''),
                    'save_dir': item.get('save_dir', str(Path(item.get('outtmpl', '.')).parent)),
                    'format': item.get('format', ''), 'ext': item.get('ext', ''), 'thread': None, 'row': row,
                    'final_path': item.get('final_path', ''),
                    'converted_output_path': item.get('converted_output_path', '')
                })
        except json.JSONDecodeError:
            print("History file is corrupted. Starting fresh.")
            os.replace(history_file, str(history_file) + ".corrupt")
        except Exception as e:
            print(f"Failed to load history: {e}")

    def show_dummy_msg(self, title):
        if title == "Options":
            BrowserIntegrationDialog(self.app_config, self).exec()
        else:
            QMessageBox.information(self, "Stratrum Download Studio", f"'{title}' feature coming soon!")

    def show_extension_install_prompt(self):
        prompt = QMessageBox(self)
        prompt.setWindowTitle("Browser Extension")
        prompt.setText(
            "Install the Stratrum extension for Chrome or Microsoft Edge? "
            "Official store listings are pending; the development build can be loaded unpacked."
        )
        install_button = prompt.addButton("Install Extension", QMessageBox.ButtonRole.AcceptRole)
        later_button = prompt.addButton("Remind Me Later", QMessageBox.ButtonRole.ActionRole)
        never_button = prompt.addButton("Do Not Ask Again", QMessageBox.ButtonRole.RejectRole)
        prompt.exec()
        clicked = prompt.clickedButton()
        if clicked == never_button:
            apply_extension_prompt_choice(self.app_config, 'never')
        elif clicked == later_button:
            apply_extension_prompt_choice(self.app_config, 'later')
        elif clicked == install_button:
            apply_extension_prompt_choice(self.app_config, 'install')
            chooser = QMessageBox(self)
            chooser.setWindowTitle("Install Browser Extension")
            chooser.setText(
                "Chrome Web Store and Edge Add-ons publishing is pending. Open an official store, "
                "or follow docs/09_PHASE_2A3_MANUAL_TEST.md to load the packaged extension unpacked."
            )
            chrome_button = chooser.addButton("Chrome Web Store", QMessageBox.ButtonRole.ActionRole)
            edge_button = chooser.addButton("Edge Add-ons", QMessageBox.ButtonRole.ActionRole)
            guide_button = chooser.addButton("Load Unpacked Guide", QMessageBox.ButtonRole.AcceptRole)
            chooser.exec()
            if chooser.clickedButton() == chrome_button:
                webbrowser.open(CHROME_STORE_URL)
            elif chooser.clickedButton() == edge_button:
                webbrowser.open(EDGE_STORE_URL)
            elif chooser.clickedButton() == guide_button:
                try:
                    if not open_browser_extension_guide():
                        raise OSError("The operating system did not open the guide")
                except (OSError, ValueError):
                    QMessageBox.warning(self, "Guide Unavailable", "The browser extension README could not be opened.")

    def init_ui(self):
        menubar = self.menuBar()
        tasks_menu = menubar.addMenu("Tasks")
        tasks_menu.addAction("Add new download").triggered.connect(lambda: self.open_add_dialog(""))
        tasks_menu.addAction("Add batch download").triggered.connect(lambda: self.show_dummy_msg("Batch Download"))
        tasks_menu.addAction("Run site grabber").triggered.connect(lambda: self.show_dummy_msg("Site Grabber"))
        tasks_menu.addSeparator(); tasks_menu.addAction("Exit").triggered.connect(self.force_quit)

        file_menu = menubar.addMenu("File")
        file_menu.addAction("Stop Download").triggered.connect(self.pause_download)
        file_menu.addAction("Remove").triggered.connect(self.delete_download)
        file_menu.addAction("Download Now").triggered.connect(self.resume_download)

        dl_menu = menubar.addMenu("Downloads")
        dl_menu.addAction("Pause All").triggered.connect(self.pause_download)
        dl_menu.addAction("Delete All Completed").triggered.connect(self.delete_completed)

        menubar.addMenu("View"); menubar.addMenu("Help"); menubar.addMenu("Registration")

        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False); toolbar.setIconSize(toolbar.iconSize() * 1.5)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)

        toolbar.addAction("➕\nAdd URL").triggered.connect(lambda: self.open_add_dialog(""))
        toolbar.addAction("▶\nResume").triggered.connect(self.resume_download)
        toolbar.addAction("⏹\nStop").triggered.connect(self.pause_download)
        toolbar.addAction("🛑\nStop All").triggered.connect(self.pause_download)
        toolbar.addAction("❌\nDelete").triggered.connect(self.delete_download)
        toolbar.addAction("🗑\nClear Done").triggered.connect(self.delete_completed)
        toolbar.addAction("⚙\nOptions").triggered.connect(lambda: self.show_dummy_msg("Options"))
        toolbar.addAction("🔗\nShare").triggered.connect(self.share_link)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        root_all = QTreeWidgetItem(["All Downloads"])
        QTreeWidgetItem(root_all, ["Video"]); QTreeWidgetItem(root_all, ["Audio"]); QTreeWidgetItem(root_all, ["Compressed"]); QTreeWidgetItem(root_all, ["Documents"])
        self.tree.addTopLevelItem(root_all); self.tree.addTopLevelItem(QTreeWidgetItem(["Unfinished"])); self.tree.addTopLevelItem(QTreeWidgetItem(["Finished"]))
        root_all.setExpanded(True)
        self.tree.itemClicked.connect(self.filter_by_category)
        splitter.addWidget(self.tree)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["File Name", "Q", "Size", "Status", "Time Left", "Transfer Rate", "Last Try Date", "Description"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        splitter.addWidget(self.table)
        splitter.setSizes([200, 950])

    def filter_by_category(self, item, column):
        category = item.text(0)
        for row in range(self.table.rowCount()):
            if category == "All Downloads": self.table.setRowHidden(row, False); continue
            filename = self.table.item(row, 0).text().lower()
            bar = self.table.cellWidget(row, 3)
            status = bar.text() if bar else self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            hidden = True
            if category == "Video" and filename.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')): hidden = False
            elif category == "Audio" and filename.endswith(('.mp3', '.wav', '.flac', '.m4a')): hidden = False
            elif category == "Compressed" and filename.endswith(('.zip', '.rar', '.7z')): hidden = False
            elif category == "Documents" and filename.endswith(('.pdf', '.docx', '.txt')): hidden = False
            elif category == "Finished" and "Complete" in status: hidden = False
            elif category == "Unfinished" and "Complete" not in status: hidden = False
            self.table.setRowHidden(row, hidden)

    def show_context_menu(self, position):
        menu = QMenu()
        menu.addAction("Open").triggered.connect(self.open_selected_file)
        menu.addAction("Open folder").triggered.connect(self.open_selected_folder)
        menu.addSeparator()
        cv_menu = menu.addMenu("Convert Format...")
        cv_menu.addAction("To MP4").triggered.connect(lambda: self.trigger_conversion("mp4"))
        cv_menu.addAction("To MP3").triggered.connect(lambda: self.trigger_conversion("mp3"))
        cv_menu.addAction("To WAV").triggered.connect(lambda: self.trigger_conversion("wav"))
        menu.addSeparator()
        menu.addAction("Resume Download").triggered.connect(self.resume_download)
        menu.addAction("Stop Download").triggered.connect(self.pause_download)
        menu.addSeparator()
        menu.addAction("Remove").triggered.connect(self.delete_download)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def is_dangerous_file(self, filepath):
        return is_dangerous_file(filepath)

    def open_selected_file(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                try:
                    open_download_file(d)
                except PermissionError:
                    QMessageBox.warning(self, "Security Warning", "Execution of downloaded dangerous file types is disabled for your safety. Use 'Open Folder' instead.")
                except (OSError, ValueError):
                    QMessageBox.warning(self, "Error", "The recorded file is missing or outside its configured download directory.")

    def open_selected_folder(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                try:
                    open_download_folder(d)
                except (OSError, ValueError):
                    QMessageBox.warning(self, "Error", "The recorded file is missing or outside its configured download directory.")

    def share_link(self):
        if selected := self.table.selectionModel().selectedRows():
            QApplication.clipboard().setText(self.table.item(selected[0].row(), 7).text())
            QMessageBox.information(self, "Link Copied", "URL copied to clipboard!")

    def delete_completed(self):
        for row in range(self.table.rowCount() - 1, -1, -1):
            bar = self.table.cellWidget(row, 3)
            if "Complete" in (bar.text() if bar else self.table.item(row, 3).text() if self.table.item(row, 3) else ""):
                if d := next((d for d in self.downloads if d['row'] == row), None): self.downloads.remove(d)
                self.table.removeRow(row)
                for other in self.downloads:
                    if other['row'] > row: other['row'] -= 1

    def init_server(self):
        self.server_thread = ServerThread(self.app_config)
        self.server_thread.url_received.connect(self.open_add_dialog)
        self.server_thread.start()

    def open_add_dialog(self, url=""):
        if isinstance(url, bool): url = ""
        self.show_normal()
        dialog = DownloadFileInfoDialog(self, prefill_url=url)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            final_url, save_dir, quality_idx, target_ext = dialog.get_data()
            if final_url: self.start_new_download(final_url, save_dir, quality_idx, target_ext)

    def start_new_download(self, url, save_dir, quality_idx, target_ext):
        download_id = uuid.uuid4().hex

        if target_ext in ["MP3", "WAV", "FLAC", "M4A"]: format_str = 'bestaudio/best'
        elif target_ext == "MP4": format_str = {0: 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 1: 'bestvideo[height<=1080][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 2: 'bestvideo[height<=720][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 3: 'bestvideo[height<=480][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best'}.get(quality_idx, 'best')
        else: format_str = {0: 'bestvideo+bestaudio/best', 1: 'bestvideo[height<=1080]+bestaudio/best', 2: 'bestvideo[height<=720]+bestaudio/best', 3: 'bestvideo[height<=480]+bestaudio/best'}.get(quality_idx, 'best')

        outtmpl = os.path.join(save_dir, '%(title)s.%(ext)s') # yt-dlp will handle template, but we post-process filename

        row = self.table.rowCount()
        self.table.insertRow(row)

        pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(0)
        self.table.setItem(row, 0, QTableWidgetItem("Connecting..."))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem("Calculating"))
        self.table.setCellWidget(row, 3, pb)
        self.table.setItem(row, 4, QTableWidgetItem("--:--"))
        self.table.setItem(row, 5, QTableWidgetItem("0 B/s"))
        self.table.setItem(row, 6, QTableWidgetItem(datetime.now().strftime("%b %d %H:%M:%S %Y")))
        self.table.setItem(row, 7, QTableWidgetItem(url))

        thread = DownloadThread(download_id, url, outtmpl, format_str, target_ext)
        thread.progress.connect(self.update_progress)
        thread.status.connect(self.update_status)
        thread.finished.connect(self.download_finished)
        thread.size_updated.connect(self.update_size)

        self.downloads.append({
            'id': download_id, 'url': url, 'outtmpl': outtmpl, 'save_dir': save_dir,
            'format': format_str, 'ext': target_ext, 'thread': thread, 'row': row,
            'final_path': '', 'converted_output_path': ''
        })
        thread.start()

        popup = DownloadProgressPopup("Connecting...", url, self)
        popup.show()
        self.popups[download_id] = popup

    def get_download_by_id(self, id): return next((d for d in self.downloads if d['id'] == id), None)

    def update_progress(self, id, filename, percent, speed, eta):
        if d := self.get_download_by_id(id):
            if self.table.item(d['row'], 0).text() == "Connecting...":
                self.table.setItem(d['row'], 0, QTableWidgetItem(filename))

            self.table.setItem(d['row'], 4, QTableWidgetItem(eta))
            self.table.setItem(d['row'], 5, QTableWidgetItem(speed))
            if bar := self.table.cellWidget(d['row'], 3): bar.setValue(int(percent)); bar.setFormat(f"{int(percent)}%")

            if id in self.popups: self.popups[id].update_stats(percent, speed, eta, self.table.item(d['row'], 2).text())

    def update_size(self, id, filename, size):
        if d := self.get_download_by_id(id): self.table.setItem(d['row'], 2, QTableWidgetItem(size))

    def update_status(self, id, status):
        if d := self.get_download_by_id(id):
            if bar := self.table.cellWidget(d['row'], 3): bar.setFormat(status)

    def download_finished(self, id, success, error_msg, filepath):
        if d := self.get_download_by_id(id):
            bar = self.table.cellWidget(d['row'], 3)
            if success:
                d['final_path'] = filepath
                try:
                    safe_path = resolve_recorded_file(d)
                except (OSError, ValueError):
                    if bar: bar.setFormat("Error: unsafe completed path")
                    d['final_path'] = ''
                    d['thread'] = None
                    return
                if bar: bar.setValue(100); bar.setFormat("Complete")
                if id in self.popups: self.popups[id].close(); del self.popups[id]

                dlg = QMessageBox(self)
                dlg.setWindowTitle("Download Complete")
                dlg.setText(f"Download Complete!\n\n{safe_path.name}")
                open_btn = None
                if not self.is_dangerous_file(safe_path):
                    open_btn = dlg.addButton("Open", QMessageBox.ButtonRole.ActionRole)
                folder_btn = dlg.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
                dlg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
                dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                dlg.exec()

                if open_btn and dlg.clickedButton() == open_btn:
                    try:
                        open_download_file(d)
                    except (OSError, ValueError, PermissionError):
                        QMessageBox.warning(self, "Error", "The completed file can no longer be opened safely.")
                elif dlg.clickedButton() == folder_btn:
                    try:
                        open_download_folder(d)
                    except (OSError, ValueError):
                        QMessageBox.warning(self, "Error", "The completed file can no longer be located safely.")
            else:
                if bar: bar.setFormat(f"Error: {error_msg}")
            d['thread'] = None

    def pause_download(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                if d['thread'] and d['thread'].isRunning(): d['thread'].paused = True

    def resume_download(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                bar = self.table.cellWidget(d['row'], 3)
                if bar and "Paused" in bar.text():
                    thread = DownloadThread(d['id'], d['url'], d['outtmpl'], d['format'], d['ext'])
                    thread.progress.connect(self.update_progress)
                    thread.status.connect(self.update_status)
                    thread.finished.connect(self.download_finished)
                    thread.size_updated.connect(self.update_size)
                    d['thread'] = thread
                    thread.start()

    def delete_download(self):
        for idx in sorted(self.table.selectionModel().selectedRows(), key=lambda x: x.row(), reverse=True):
            row = idx.row()
            if d := next((d for d in self.downloads if d['row'] == row), None):
                if d['thread'] and d['thread'].isRunning(): d['thread'].paused = True
                self.table.removeRow(row); self.downloads.remove(d)
                for other in self.downloads:
                    if other['row'] > row: other['row'] -= 1

    def trigger_conversion(self, target_ext):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                bar = self.table.cellWidget(d['row'], 3)
                if bar and bar.text() == "Complete" and d.get('final_path'):
                    bar.setFormat("Converting...")
                    self.converter = ConvertThread(d['id'], d['final_path'], target_ext)
                    self.converter.finished.connect(self.conversion_done)
                    self.converter.start()

    def conversion_done(self, row_id, success, msg, output_path):
        if d := self.get_download_by_id(row_id):
            bar = self.table.cellWidget(d['row'], 3)
            if not success:
                if bar: bar.setFormat(msg)
                return
            try:
                converted_path = store_conversion_output(d, output_path)
            except (OSError, ValueError):
                if bar: bar.setFormat("Conversion output missing or unsafe")
                return
            if bar: bar.setFormat("Complete")
            self.save_downloads_to_file()

            dialog = QMessageBox(self)
            dialog.setWindowTitle("Conversion Complete")
            dialog.setText(f"Converted output:\n\n{converted_path}")
            folder_button = dialog.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
            dialog.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            dialog.exec()
            if dialog.clickedButton() == folder_button:
                try:
                    open_download_folder(d, path=converted_path)
                except (OSError, ValueError):
                    QMessageBox.warning(self, "Error", "The converted output can no longer be located safely.")

if __name__ == "__main__":
    runtime_config = initialize_runtime()
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLE)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    window = StratrumDownloadStudio(runtime_config)
    window.show()
    sys.exit(app.exec())
