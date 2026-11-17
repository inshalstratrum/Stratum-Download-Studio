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
import math
import signal
import webbrowser
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from stratum_dependency_policy import controlled_yt_dlp_options, load_controlled_yt_dlp
from ids_http_qt import FileDownloadThread
from ids_http_engine import check_public_url, FileTransferError, safe_file_name
from ids_handoff import HandoffReceipt

yt_dlp = load_controlled_yt_dlp()

APP_NAME = "I-DS | I.os Download Support"
BROWSER_BRIDGE_PORT = 18765
EXTENSION_ACTIONS = {'default', 'quick', 'options', 'quick_download', 'download_with_options', 'http_download'}
DESKTOP_BROWSER_ACTIONS = {'quick_download', 'download_with_options'}
MAX_REQUEST_BODY = 16 * 1024
MAX_OPERATIONAL_URL = 8192
CONVERSION_TIMEOUT_SECONDS = 30 * 60
MAX_PAIRED_ORIGINS = 6
MAX_RECENT_FOLDERS = 10
DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS = 2
MAX_RETRY_ATTEMPTS = 3
AUTHENTICATED_BROWSERS = {'chrome', 'edge', 'firefox'}
AUTHENTICATED_SITE_DOMAINS = {'facebook.com', 'instagram.com', 'tiktok.com'}
AUTHENTICATION_ERROR_RE = re.compile(
    r'(?i)(?:login|required to log in|sign[ -]?in|authentication|authenticated|cookies?|empty (?:media|response)|'
    r'no (?:video )?formats?|no media|content is not available|requested content is not available|private (?:post|video))'
)
_conversion_name_lock = threading.Lock()


WINDOWS_RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
MEDIA_EXTENSIONS = {'mp4', 'mkv', 'webm', 'avi', 'mov', 'mp3', 'm4a', 'aac', 'wav', 'flac', 'ogg', 'opus'}
WINDOWS_SAFE_PATH_LIMIT = 240


def normalize_media_extension(ext):
    value = str(ext or '').split('?', 1)[0].split('#', 1)[0].strip().lower().lstrip('.')
    if not re.fullmatch(r'[a-z0-9]{2,10}', value) or value not in MEDIA_EXTENSIONS:
        raise ValueError('Unsupported media extension')
    return value


def sanitize_windows_filename_component(value):
    cleaned = re.sub(r'[\x00-\x1f\x7f\\/:*?"<>|]', '_', str(value or '')).strip('. ')
    cleaned = re.sub(r'\s+', ' ', cleaned) or 'download'
    if cleaned.split('.', 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        cleaned += '_file'
    return cleaned


def generate_safe_filename(save_dir, title, ext, path_limit=WINDOWS_SAFE_PATH_LIMIT):
    extension = normalize_media_extension(ext)
    root = os.path.abspath(os.fspath(save_dir))
    if len(root) + len(extension) + 4 >= int(path_limit):
        raise ValueError('Save folder path is too long for a safe media filename')
    base = sanitize_windows_filename_component(title)
    with _conversion_name_lock:
        counter = 0
        while True:
            collision = '' if counter == 0 else f'_{counter}'
            available = max(1, int(path_limit) - len(root) - 1 - len(extension) - 1 - len(collision))
            stem = base[:min(200, available)].rstrip('. ') or 'download'
            out_path = os.path.join(root, f'{stem}{collision}.{extension}')
            if not os.path.exists(out_path):
                return out_path
            counter += 1


def build_safe_output_template(save_dir, job_id, path_limit=WINDOWS_SAFE_PATH_LIMIT):
    root = Path(save_dir).resolve()
    suffix = f' [%(id).40B]-{str(job_id)[:8]}.%(ext)s'
    if len(str(root)) + len(suffix) + 33 >= int(path_limit):
        raise ValueError('Save folder path is too long for a safe media output')
    title_bytes = max(32, min(160, int(path_limit) - len(str(root)) - len(suffix) - 12))
    return str(root / f'%(title).{title_bytes}B{suffix}')


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QToolBar,
    QDialog, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QProgressBar, QSystemTrayIcon, QMenu, QStyle, QSpinBox, QVBoxLayout,
    QHBoxLayout, QHeaderView, QSplitter, QTreeWidget, QTreeWidgetItem,
    QPushButton, QComboBox, QMenuBar, QFormLayout, QGroupBox, QTabWidget,
    QWidget, QGridLayout, QCheckBox, QTextEdit, QInputDialog,
    QHBoxLayout, QVBoxLayout, QStackedWidget, QFrame, QSizePolicy, QToolButton
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QEvent, QUrl, QObject, QTimer, QStandardPaths, QSize
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QPixmap, QDesktopServices, QCursor
from ids_ui_components import icon as ids_icon, make_banner, make_empty_state, UI_POLISH_QSS

# ==========================================
# MODERN UI STYLESHEET
# ==========================================
MODERN_STYLE = """
QMainWindow, QDialog { background: #f5f8fc; color: #172b45; }
QLabel, QGroupBox, QCheckBox { color: #172b45; }
QMenuBar, QMenu, QToolBar { background: #ffffff; color: #172b45; border: none; }
QMenuBar { border-bottom: 1px solid #dce5ef; padding: 3px 7px; }
QMenuBar::item { padding: 7px 10px; border-radius: 6px; }
QMenuBar::item:selected, QMenu::item:selected { background: #e5f3fb; color: #133d61; }
QMenu::item { padding: 7px 26px; }
QToolBar { spacing: 5px; padding: 8px; border-bottom: 1px solid #dce5ef; }
QToolButton { min-height: 42px; min-width: 56px; border: 1px solid transparent;
              border-radius: 8px; padding: 7px 9px; color: #172b45; background: transparent; }
QToolButton:hover { background: #e6f3fc; border-color: #c2ddec; }
QToolButton:pressed, QToolButton:checked { background: #d5eaf7; }
QToolButton:focus { border: 2px solid #2865da; }
QTableWidget, QTreeWidget { background: #ffffff; color: #172b45; border: 1px solid #dce5ef;
                           border-radius: 8px; selection-background-color: #d6f0ef; selection-color: #153d53; }
QTableWidget { gridline-color: #ebeff5; alternate-background-color: #f9fbfd; }
QTableWidget::item { padding: 5px; }
QTableWidget::item:selected, QTreeWidget::item:selected { background: #d6f0ef; color: #153d53; }
QTreeWidget::item { padding: 7px 9px; }
QTreeWidget::item:hover { background: #eef5fa; }
QHeaderView::section { background: #edf3fa; color: #2a405a; padding: 9px 7px;
                       border: none; border-right: 1px solid #dce5ef; font-weight: 600; }
QSplitter::handle { background: #e4ebf4; width: 6px; }
QSplitter::handle:hover { background: #8dc4d6; }
QPushButton { background: #ffffff; color: #173954; border-radius: 8px;
              padding: 9px 15px; min-height: 21px; border: 1px solid #bfd0e0; font-weight: 600; }
QPushButton:hover { background: #e7f3fb; border-color: #569cc0; }
QPushButton:pressed { background: #d5eaf7; }
QPushButton:focus { border: 2px solid #2865da; }
QPushButton:disabled { background: #edf1f5; color: #77899c; border-color: #dce4ed; }
QLineEdit, QComboBox, QTextEdit, QSpinBox { padding: 8px; border: 1px solid #c5d4e3;
              border-radius: 7px; background: #ffffff; color: #172b45; selection-background-color: #c4e9e5; }
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus { border: 2px solid #2865da; }
QProgressBar { text-align: center; border: 1px solid #c4d5e2; border-radius: 6px;
               background: #eaf0f7; color: #173954; min-height: 18px; font-weight: 600; }
QProgressBar::chunk { background: #18aa93; border-radius: 5px; }
QTabWidget::pane { border: 1px solid #dce5ef; border-radius: 8px; background: #ffffff; }
QTabBar::tab { padding: 9px 15px; background: #eaf0f7; color: #42546b; }
QTabBar::tab:selected { background: #ffffff; color: #163f63; }
"""
MODERN_STYLE += UI_POLISH_QSS

def get_ffmpeg_path():
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, 'ffmpeg.exe')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_ffmpeg = os.path.join(base_dir, 'ffmpeg.exe')
    if os.path.exists(local_ffmpeg): return local_ffmpeg
    return 'ffmpeg'


def get_ffprobe_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'ffprobe.exe')
    local_ffprobe = Path(__file__).resolve().parent / 'ffprobe.exe'
    return str(local_ffprobe) if local_ffprobe.exists() else 'ffprobe'

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
    allowed_origins: list[str]
    rate_limiter: RateLimiter
    recent_folders: list[str] = field(default_factory=list)
    preferred_format: str = 'MP4'
    preferred_resolution: int | None = None
    max_simultaneous_downloads: int = DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS
    speed_limit_bps: int = 0
    completion_action: str = 'keep_open'
    keep_completed_window_open: bool = False
    primary_browser_action: str = 'quick_download'
    authenticated_retry_enabled: bool = False
    authenticated_retry_browser: str = 'chrome'
    authenticated_retry_profile: str = ''
    stop_after_current: bool = False
    window_size: list[int] = field(default_factory=lambda: [1150, 680])
    splitter_sizes: list[int] = field(default_factory=lambda: [200, 950])
    column_widths: list[int] = field(default_factory=list)
    hidden_columns: list[int] = field(default_factory=list)
    sidebar_visible: bool = True
    ui_text_scale: int = 100
    state_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def allowed_origin(self):
        return self.allowed_origins[0] if self.allowed_origins else ''

    @allowed_origin.setter
    def allowed_origin(self, origin):
        self.allowed_origins = [origin] if origin else []

    def persisted_values(self):
        return {
            'auth_token': self.auth_token,
            'allowed_origins': list(self.allowed_origins),
            'recent_folders': list(self.recent_folders),
            'preferred_format': self.preferred_format,
            'preferred_resolution': self.preferred_resolution,
            'max_simultaneous_downloads': self.max_simultaneous_downloads,
            'speed_limit_bps': self.speed_limit_bps,
            'completion_action': self.completion_action,
            'keep_completed_window_open': self.keep_completed_window_open,
            'primary_browser_action': self.primary_browser_action,
            'authenticated_retry_enabled': self.authenticated_retry_enabled,
            'authenticated_retry_browser': self.authenticated_retry_browser,
            'authenticated_retry_profile': self.authenticated_retry_profile,
            'stop_after_current': self.stop_after_current,
            'window_size': list(self.window_size),
            'splitter_sizes': list(self.splitter_sizes),
            'column_widths': list(self.column_widths),
            'hidden_columns': list(self.hidden_columns),
            'sidebar_visible': bool(self.sidebar_visible),
            'ui_text_scale': int(self.ui_text_scale),
        }

    def persist(self):
        with self.state_lock:
            atomic_write_json(self.config_path, self.persisted_values())

    def pair_origin(self, origin):
        if not validate_extension_origin(origin):
            raise ValueError("Malformed extension origin")
        with self.state_lock:
            if origin in self.allowed_origins:
                return False
            if len(self.allowed_origins) >= MAX_PAIRED_ORIGINS:
                raise PairingLimitError("Maximum paired browser origins reached")
            previous = list(self.allowed_origins)
            self.allowed_origins.append(origin)
            try:
                self.persist()
            except Exception:
                self.allowed_origins = previous
                raise
            return True

    def reset_pairing(self):
        self.reset_all_origins()

    def reset_all_origins(self):
        with self.state_lock:
            previous = list(self.allowed_origins)
            self.allowed_origins.clear()
            try:
                self.persist()
            except Exception:
                self.allowed_origins = previous
                raise

    def remove_origin(self, origin):
        with self.state_lock:
            if origin not in self.allowed_origins:
                return False
            previous = list(self.allowed_origins)
            self.allowed_origins.remove(origin)
            try:
                self.persist()
            except Exception:
                self.allowed_origins = previous
                raise
            return True

    def add_recent_folder(self, folder):
        candidate = Path(folder).expanduser()
        if not candidate.is_dir():
            return False
        resolved = str(candidate.resolve())
        with self.state_lock:
            updated = [resolved] + [item for item in self.recent_folders if item != resolved and Path(item).is_dir()]
            self.recent_folders = updated[:MAX_RECENT_FOLDERS]
            self.persist()
        return True

    def clear_recent_folders(self):
        with self.state_lock:
            self.recent_folders.clear()
            self.persist()


class PairingLimitError(ValueError):
    pass


def normalize_allowed_origins(origins):
    normalized = []
    if not isinstance(origins, (list, tuple)):
        return normalized
    for origin in origins:
        if validate_extension_origin(origin) and origin not in normalized:
            normalized.append(origin)
        if len(normalized) == MAX_PAIRED_ORIGINS:
            break
    return normalized


def normalize_recent_folders(folders):
    normalized = []
    if not isinstance(folders, list):
        return normalized
    for folder in folders:
        if not isinstance(folder, str):
            continue
        candidate = Path(folder).expanduser()
        if not candidate.is_dir():
            continue
        resolved = str(candidate.resolve())
        if resolved not in normalized:
            normalized.append(resolved)
        if len(normalized) == MAX_RECENT_FOLDERS:
            break
    return normalized


def bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_browser_profile(value):
    if not isinstance(value, str):
        return ''
    value = value.strip()
    return value if len(value) <= 1024 and not re.search(r'[\r\n\0]', value) else ''


def normalize_authenticated_browser(value):
    return value if isinstance(value, str) and value in AUTHENTICATED_BROWSERS else 'chrome'


def initialize_runtime(app_data_root=None, auth_token=None, allowed_origin=None,
                       history_path=None, rate_limiter=None, allowed_origins=None):
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

    if allowed_origins is not None:
        selected_origins = normalize_allowed_origins(allowed_origins)
    elif allowed_origin is not None:
        selected_origins = normalize_allowed_origins([allowed_origin])
    elif isinstance(stored.get('allowed_origins'), list):
        selected_origins = normalize_allowed_origins(stored['allowed_origins'])
    else:
        selected_origins = normalize_allowed_origins([stored.get('allowed_origin', '')])

    runtime = AppConfig(
        app_data_root=root,
        config_path=config_path,
        history_path=Path(history_path) if history_path is not None else root / 'history' / 'history.json',
        auth_token=selected_token,
        allowed_origins=selected_origins,
        rate_limiter=rate_limiter or RateLimiter(5, 1.0),
        recent_folders=normalize_recent_folders(stored.get('recent_folders', [])),
        preferred_format=stored.get('preferred_format', 'MP4') if stored.get('preferred_format', 'MP4') in OUTPUT_PROFILES else 'MP4',
        preferred_resolution=stored.get('preferred_resolution') if stored.get('preferred_resolution') in {None, 240, 360, 480, 720, 1080, 1440, 2160, 4320} else None,
        max_simultaneous_downloads=bounded_int(stored.get('max_simultaneous_downloads'), DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS, 1, 8),
        speed_limit_bps=bounded_int(stored.get('speed_limit_bps'), 0, 0, 1024 * 1024 * 1024),
        completion_action=stored.get('completion_action', 'keep_open'),
        keep_completed_window_open=bool(stored.get('keep_completed_window_open', False)),
        primary_browser_action=stored.get('primary_browser_action', 'quick_download') if stored.get('primary_browser_action', 'quick_download') in DESKTOP_BROWSER_ACTIONS else 'quick_download',
        authenticated_retry_enabled=bool(stored.get('authenticated_retry_enabled', False)),
        authenticated_retry_browser=normalize_authenticated_browser(stored.get('authenticated_retry_browser', 'chrome')),
        authenticated_retry_profile=normalize_browser_profile(stored.get('authenticated_retry_profile', '')),
        stop_after_current=bool(stored.get('stop_after_current', False)),
        window_size=stored.get('window_size', [1150, 680]) if isinstance(stored.get('window_size', [1150, 680]), list) else [1150, 680],
        splitter_sizes=stored.get('splitter_sizes', [200, 950]) if isinstance(stored.get('splitter_sizes', [200, 950]), list) else [200, 950],
        column_widths=stored.get('column_widths', []) if isinstance(stored.get('column_widths', []), list) else [],
        hidden_columns=stored.get('hidden_columns', []) if isinstance(stored.get('hidden_columns', []), list) else [],
        sidebar_visible=bool(stored.get('sidebar_visible', True)),
        ui_text_scale=int(stored.get('ui_text_scale', 100)) if stored.get('ui_text_scale') in (100, 115, 130) else 100,
    )
    runtime.history_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.persist()
    return runtime


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
    if not isinstance(url, str) or not url or len(url) > MAX_OPERATIONAL_URL:
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


def site_domain(url):
    valid, _ = validate_url(url)
    if not valid:
        return ''
    host = (urllib.parse.urlsplit(url).hostname or '').lower().removeprefix('www.').removeprefix('m.')
    return next((domain for domain in AUTHENTICATED_SITE_DOMAINS if host == domain or host.endswith('.' + domain)), '')


def site_extractor_options(url):
    if site_domain(url) == 'instagram.com':
        return {'extractor_args': {'instagram': {'app_id': ['web']}}}
    return {}


def extraction_options_for_url(base_options, url):
    options = dict(base_options)
    site_options = site_extractor_options(url)
    if site_options:
        merged_args = dict(options.get('extractor_args') or {})
        merged_args.update(site_options['extractor_args'])
        options['extractor_args'] = merged_args
    return options


def is_authentication_extraction_error(error):
    return bool(AUTHENTICATION_ERROR_RE.search(str(error or '')))


def authenticated_retry_options(base_options, url, app_config):
    if not app_config or not app_config.authenticated_retry_enabled or not site_domain(url):
        return None
    browser = normalize_authenticated_browser(app_config.authenticated_retry_browser)
    profile = normalize_browser_profile(app_config.authenticated_retry_profile)
    options = extraction_options_for_url(base_options, url)
    options['cookiesfrombrowser'] = (browser, profile or None, None, None)
    return options


def should_retry_authenticated_extraction(error, url, app_config):
    return is_authentication_extraction_error(error) and authenticated_retry_options({}, url, app_config) is not None


def validate_browser_handoff(data, operational_url):
    source_page = data.get('sourcePage', '')
    content_type = data.get('contentType', '')
    raw_context = data.get('requestContext', {})
    if source_page:
        valid, _ = validate_url(source_page)
        if not valid:
            raise ValueError('Invalid source page')
    if not isinstance(content_type, str) or len(content_type) > 120 or re.search(r'[\r\n\0]', content_type):
        raise ValueError('Invalid content type')
    if not isinstance(raw_context, dict) or set(raw_context) - {'referer', 'origin', 'userAgent'}:
        raise ValueError('Invalid request context')
    headers = {}
    if source_page:
        source = urllib.parse.urlsplit(source_page)
        referer = raw_context.get('referer', '')
        origin = raw_context.get('origin', '')
        if referer:
            valid, _ = validate_url(referer)
            if not valid or urllib.parse.urlsplit(referer).netloc.lower() != source.netloc.lower():
                raise ValueError('Invalid Referer provenance')
            headers['Referer'] = referer
        if origin:
            expected_origin = f'{source.scheme}://{source.netloc}'
            if origin != expected_origin:
                raise ValueError('Invalid Origin provenance')
            headers['Origin'] = origin
    elif raw_context.get('referer') or raw_context.get('origin'):
        raise ValueError('Request context requires a source page')
    user_agent = raw_context.get('userAgent', '')
    if user_agent:
        if not isinstance(user_agent, str) or len(user_agent) > 512 or re.search(r'[\r\n\0]', user_agent):
            raise ValueError('Invalid User-Agent')
        headers['User-Agent'] = user_agent
    return {
        'source_page': source_page,
        'content_type': content_type,
        'http_headers': headers,
        'operational_url': operational_url,
    }

def validate_request(headers, rfile, runtime):
    auth_header = headers.get('X-Stratrum-Auth', '')
    if not isinstance(auth_header, str) or not secrets.compare_digest(auth_header, runtime.auth_token):
        return 401, b'{"error": "Unauthorized"}'

    origin = headers.get('Origin', '')
    if not validate_extension_origin(origin):
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
    action = data.get('action')
    if action not in EXTENSION_ACTIONS:
        return 400, b'{"error": "Invalid action"}'
    is_valid, err_msg = validate_url(url)
    if not is_valid:
        return 400, json.dumps({"error": err_msg}).encode('utf-8')
    try:
        handoff = validate_browser_handoff(data, url)
    except ValueError:
        return 400, b'{"error": "Invalid browser media context"}'

    if not runtime.rate_limiter.allow():
        return 429, b'{"error": "Too many requests"}'

    try:
        runtime.pair_origin(origin)
    except PairingLimitError:
        return 403, b'{"error": "Pairing limit reached; reset browser pairing"}'
    except ValueError:
        return 403, b'{"error": "Origin not allowed"}'
    except OSError:
        return 500, b'{"error": "Unable to persist browser pairing"}'

    file_name_hint = data.get('fileName', '')
    if not isinstance(file_name_hint, str) or len(file_name_hint) > 240:
        return 400, b'{"error": "Invalid file name hint"}'
    result = {'url': url, 'action': action, 'context': handoff}
    # Keep historical response contracts byte-for-byte compatible for media.
    if action == 'http_download':
        result['file_name_hint'] = safe_file_name(file_name_hint) if file_name_hint else ''
    return 200, result


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


VIDEO_EXTENSIONS = {'mp4', 'mkv', 'webm', 'avi', 'mov'}
AUDIO_EXTENSIONS = {'mp3', 'm4a', 'aac', 'wav', 'flac', 'ogg', 'opus'}
THUMBNAIL_EXTENSIONS = {'.webp', '.jpg', '.jpeg', '.png', '.gif'}
RESOLUTION_LABELS = {
    4320: '4320p / 8K (7680x4320)',
    2160: '2160p / 4K (3840x2160)',
    1440: '1440p (2560x1440)',
    1080: '1080p / Full HD (1920x1080)',
    720: '720p / HD (1280x720)',
    480: '480p / SD (854x480)',
    360: '360p (640x360)',
    240: '240p (426x240)',
}


@dataclass(frozen=True)
class OutputProfile:
    extension: str
    media_kind: str
    container: str
    audio_codec: str | None = None
    explicit_conversion: bool = False
    ffmpeg_video_args: tuple = ()
    ffmpeg_audio_args: tuple = ()
    expected_formats: tuple = ()


OUTPUT_PROFILES = {
    'MP4': OutputProfile('mp4', 'video', 'mp4', ffmpeg_video_args=('-c:v', 'libx264', '-c:a', 'aac', '-movflags', '+faststart'), ffmpeg_audio_args=('-vn', '-c:a', 'aac', '-movflags', '+faststart'), expected_formats=('mp4', 'mov')),
    'MKV': OutputProfile('mkv', 'video', 'matroska', ffmpeg_video_args=('-c:v', 'libx264', '-c:a', 'aac'), expected_formats=('matroska',)),
    'WEBM': OutputProfile('webm', 'video', 'webm', ffmpeg_video_args=('-c:v', 'libvpx-vp9', '-c:a', 'libopus'), expected_formats=('webm', 'matroska')),
    'AVI': OutputProfile('avi', 'video', 'avi', explicit_conversion=True, ffmpeg_video_args=('-c:v', 'mpeg4', '-c:a', 'libmp3lame'), expected_formats=('avi',)),
    'MOV': OutputProfile('mov', 'video', 'mov', explicit_conversion=True, ffmpeg_video_args=('-c:v', 'libx264', '-c:a', 'aac'), expected_formats=('mp4', 'mov')),
    'MP3': OutputProfile('mp3', 'audio', 'mp3', 'mp3', ffmpeg_audio_args=('-vn', '-c:a', 'libmp3lame'), expected_formats=('mp3',)),
    'M4A': OutputProfile('m4a', 'audio', 'm4a', 'm4a', ffmpeg_audio_args=('-vn', '-c:a', 'aac'), expected_formats=('mp4', 'mov', 'm4a')),
    'AAC': OutputProfile('aac', 'audio', 'aac', 'aac', ffmpeg_audio_args=('-vn', '-c:a', 'aac', '-f', 'adts'), expected_formats=('aac',)),
    'WAV': OutputProfile('wav', 'audio', 'wav', 'wav', ffmpeg_audio_args=('-vn', '-c:a', 'pcm_s16le'), expected_formats=('wav',)),
    'FLAC': OutputProfile('flac', 'audio', 'flac', 'flac', ffmpeg_audio_args=('-vn', '-c:a', 'flac'), expected_formats=('flac',)),
    'OGG': OutputProfile('ogg', 'audio', 'ogg', 'vorbis', ffmpeg_audio_args=('-vn', '-c:a', 'libvorbis'), expected_formats=('ogg',)),
    'OPUS': OutputProfile('opus', 'audio', 'opus', 'opus', ffmpeg_audio_args=('-vn', '-c:a', 'libopus'), expected_formats=('opus', 'ogg')),
}


def output_profile(name):
    try:
        return OUTPUT_PROFILES[str(name).upper()]
    except KeyError as exc:
        raise ValueError(f"Unsupported output profile: {name}") from exc


def format_resolution_detail(option):
    size = format_bytes(option.get('estimated_size')) if option.get('estimated_size') else 'size unknown'
    return (
        f"{RESOLUTION_LABELS.get(option['height'], str(option['height']) + 'p')} — "
        f"video {option.get('vcodec') or 'unknown'} / audio {option.get('acodec') or 'separate'} / "
        f"{option.get('container') or 'unknown'} / {size}"
    )


def available_resolution_options(info):
    formats = info.get('formats', []) if isinstance(info, dict) else []
    best_audio = next((fmt for fmt in reversed(formats) if fmt.get('acodec') not in {None, 'none'}), {})
    by_height = {}
    for fmt in formats:
        height = fmt.get('height')
        if height not in RESOLUTION_LABELS or fmt.get('vcodec') in {None, 'none'}:
            continue
        size = fmt.get('filesize') or fmt.get('filesize_approx')
        current = by_height.get(height)
        if current is None or (size or 0) > (current.get('estimated_size') or 0):
            by_height[height] = {
                'height': height,
                'format_id': fmt.get('format_id'),
                'vcodec': fmt.get('vcodec'),
                'acodec': fmt.get('acodec') if fmt.get('acodec') not in {None, 'none'} else best_audio.get('acodec'),
                'container': fmt.get('ext'),
                'estimated_size': size,
            }
    return [by_height[height] for height in sorted(by_height, reverse=True)]


def choose_resolution(options, requested_height=None):
    if not options:
        return None
    ordered = sorted(options, key=lambda item: item['height'], reverse=True)
    if requested_height is None:
        return ordered[0]
    exact = next((item for item in ordered if item['height'] == requested_height), None)
    if exact:
        return exact
    return next((item for item in ordered if item['height'] < requested_height), ordered[-1])


def mp4_compatible_streams_available(info, height=None):
    formats = info.get('formats', []) if isinstance(info, dict) else []
    video = any(
        fmt.get('ext') == 'mp4'
        and str(fmt.get('vcodec', '')).lower().startswith(('avc', 'h264'))
        and (height is None or not fmt.get('height') or fmt.get('height') <= height)
        for fmt in formats
    )
    audio = any(
        fmt.get('ext') in {'m4a', 'mp4'} and str(fmt.get('acodec', '')).lower().startswith(('aac', 'mp4a'))
        for fmt in formats
    )
    return video and audio


def webm_compatible_streams_available(info, height=None):
    formats = info.get('formats', []) if isinstance(info, dict) else []
    video = any(
        fmt.get('ext') == 'webm'
        and str(fmt.get('vcodec', '')).lower().startswith(('vp8', 'vp9', 'av01', 'av1'))
        and (height is None or not fmt.get('height') or fmt.get('height') <= height)
        for fmt in formats
    )
    audio = any(
        fmt.get('ext') == 'webm' and str(fmt.get('acodec', '')).lower().startswith(('opus', 'vorbis'))
        for fmt in formats
    )
    return video and audio


def build_format_selector(profile_name, height=None):
    profile = output_profile(profile_name)
    if profile.media_kind == 'audio':
        return 'bestaudio/best'
    height_filter = f'[height<={int(height)}]' if height else ''
    if profile.extension == 'mp4':
        return (
            f'best{height_filter}[ext=mp4][vcodec^=avc][acodec^=mp4a]/'
            f'best{height_filter}[ext=mp4][vcodec^=h264][acodec^=aac]/'
            f'bestvideo{height_filter}[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a][acodec^=mp4a]/'
            f'bestvideo{height_filter}[ext=mp4][vcodec^=h264]+bestaudio[ext=m4a][acodec^=aac]/'
            f'bestvideo{height_filter}+bestaudio/best{height_filter}/best'
        )
    if profile.extension == 'webm':
        return (
            f'best{height_filter}[ext=webm][vcodec^=vp9][acodec^=opus]/'
            f'best{height_filter}[ext=webm][vcodec^=vp8][acodec^=vorbis]/'
            f'bestvideo{height_filter}[ext=webm][vcodec^=vp9]+bestaudio[ext=webm][acodec^=opus]/'
            f'bestvideo{height_filter}[ext=webm][vcodec^=vp8]+bestaudio[ext=webm][acodec^=vorbis]/'
            f'bestvideo{height_filter}[ext=webm][vcodec^=av01]+bestaudio[ext=webm][acodec^=opus]/'
            f'bestvideo{height_filter}+bestaudio/best{height_filter}/best'
        )
    return f'bestvideo{height_filter}+bestaudio/best{height_filter}/best'


def build_download_options(profile_name, outtmpl, height=None, metadata=None,
                           progress_hooks=None, postprocessor_hooks=None, speed_limit_bps=0,
                           request_context=None):
    profile = output_profile(profile_name)
    options = {
        **controlled_yt_dlp_options(),
        'outtmpl': outtmpl,
        'format': build_format_selector(profile_name, height),
        'progress_hooks': list(progress_hooks or []),
        'postprocessor_hooks': list(postprocessor_hooks or []),
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'continuedl': True,
        'overwrites': False,
        'ffmpeg_location': get_ffmpeg_path(),
        'concurrent_fragment_downloads': 10,
        'buffersize': 1024 * 32,
    }
    if speed_limit_bps:
        options['ratelimit'] = int(speed_limit_bps)
    headers = dict((request_context or {}).get('http_headers') or {})
    if headers:
        options['http_headers'] = headers
    if profile.media_kind == 'audio':
        options['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': profile.audio_codec,
            'preferredquality': '192',
        }]
    elif profile.extension in {'avi', 'mov'}:
        options['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': profile.extension}]
    elif profile.extension == 'mp4':
        options['merge_output_format'] = 'mp4'
        if not mp4_compatible_streams_available(metadata or {}, height):
            options['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
    elif profile.extension == 'webm':
        options['merge_output_format'] = 'webm'
        if not webm_compatible_streams_available(metadata or {}, height):
            options['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'webm'}]
    else:
        options['merge_output_format'] = profile.extension
        options['postprocessors'] = [{'key': 'FFmpegVideoRemuxer', 'preferedformat': profile.extension}]
    return options


def postprocessor_output_path(event):
    if not isinstance(event, dict) or event.get('status') != 'finished':
        return None
    info = event.get('info_dict') if isinstance(event.get('info_dict'), dict) else {}
    return event.get('filepath') or event.get('filename') or info.get('filepath') or info.get('_filename')


def collect_output_candidates(info, postprocessed_paths, save_dir, extension, preexisting=None, *,
                              output_tag=None):
    """Collect yt-dlp output hints; glob only using a proven per-job filename tag.

    Extractor IDs are not ownership: concurrent jobs can share them. Missing
    hints must fail closed instead of scanning another worker's output.
    """
    candidates = []
    candidates.extend(path for path in postprocessed_paths if path)
    if isinstance(info, dict):
        candidates.extend(info.get(key) for key in ('filepath', '_filename') if info.get(key))
        moves = info.get('__files_to_move') if isinstance(info.get('__files_to_move'), dict) else {}
        candidates.extend(moves.values())
        downloads = info.get('requested_downloads') if isinstance(info.get('requested_downloads'), list) else []
        for item in downloads:
            if isinstance(item, dict):
                candidates.extend(item.get(key) for key in ('filepath', '_filename') if item.get(key))
    before = {str(Path(path).resolve()) for path in (preexisting or set())}
    if output_tag:
        # The job-specific template puts the tag at the END of the output stem.
        candidates.extend(str(path) for path in Path(save_dir).glob(f'*{output_tag}.{extension}'))
    unique = []
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        try:
            path = Path(candidate)
            resolved = str(path.resolve())
        except (OSError, TypeError, ValueError):
            continue
        if resolved in before or resolved in seen:
            continue
        if output_tag and (path.suffix.lower() != f'.{extension}'.lower()
                           or not path.stem.endswith(output_tag)):
            continue
        seen.add(resolved)
        unique.append(str(candidate))
    return unique


def probe_media_file(path, runner=None):
    runner = runner or subprocess.run
    command = [
        get_ffprobe_path(), '-v', 'error', '-show_entries',
        'format=format_name,duration:format_tags=major_brand:stream=codec_type,codec_name,width,height',
        '-of', 'json', str(path),
    ]
    kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE, 'timeout': 30}
    creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if creation_flags:
        kwargs['creationflags'] = creation_flags
    result = runner(command, **kwargs)
    if result.returncode != 0:
        summary = clean_error_summary(result.stderr)
        raise ValueError(f"ffprobe validation failed: {summary}")
    try:
        payload = json.loads(result.stdout.decode('utf-8') if isinstance(result.stdout, bytes) else result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("ffprobe returned malformed metadata") from exc
    format_data = payload.get('format', {}) if isinstance(payload.get('format'), dict) else {}
    try:
        duration = float(format_data.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        'format_name': format_data.get('format_name', ''),
        'duration': max(0.0, duration),
        'major_brand': (format_data.get('tags') or {}).get('major_brand', ''),
        'streams': payload.get('streams', []),
    }


def validate_final_media(path, save_dir, profile_name, probe_runner=None, required_stream=None):
    profile = output_profile(profile_name)
    candidate = Path(path).resolve(strict=True)
    root = Path(save_dir).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Final output is outside the selected save directory") from exc
    if not candidate.is_file():
        raise ValueError("Final output is not a file")
    if candidate.suffix.lower() in THUMBNAIL_EXTENSIONS:
        raise ValueError("Thumbnail files cannot be completed media outputs")
    if candidate.suffix.lower() != f'.{profile.extension}':
        raise ValueError(f"Final output extension does not match requested {profile.extension.upper()} profile")
    if re.search(r'\.f\d+\.', candidate.name, re.IGNORECASE):
        raise ValueError("Intermediate media stream cannot be reported as final output")
    probe = probe_media_file(candidate, runner=probe_runner)
    stream_types = {stream.get('codec_type') for stream in probe['streams'] if isinstance(stream, dict)}
    required_stream = required_stream or ('video' if profile.media_kind == 'video' else 'audio')
    if required_stream not in stream_types:
        raise ValueError(f"Final {profile.media_kind} output has no {required_stream} stream")
    format_name = probe.get('format_name', '').lower()
    if not any(token in format_name.split(',') for token in profile.expected_formats):
        raise ValueError(f"ffprobe container does not match requested {profile.extension.upper()} profile")
    major_brand = str(probe.get('major_brand', '')).strip().lower()
    if profile.extension == 'mov' and major_brand != 'qt':
        raise ValueError("ffprobe container brand does not match requested MOV profile")
    if profile.extension == 'mp4' and (not major_brand or major_brand in {'qt', 'm4a'}):
        raise ValueError("ffprobe container brand does not match requested MP4 profile")
    if profile.extension == 'm4a' and major_brand == 'qt':
        raise ValueError("ffprobe container brand does not match requested M4A profile")
    return candidate, probe


def profile_codecs_compatible(probe, profile_name):
    profile = output_profile(profile_name)
    if profile.extension not in {'mp4', 'webm'}:
        return True
    streams = [stream for stream in probe.get('streams', []) if isinstance(stream, dict)] if isinstance(probe, dict) else []
    video_codecs = {str(stream.get('codec_name') or '').lower() for stream in streams if stream.get('codec_type') == 'video'}
    audio_codecs = {str(stream.get('codec_name') or '').lower() for stream in streams if stream.get('codec_type') == 'audio'}
    known_video = {codec for codec in video_codecs if codec}
    known_audio = {codec for codec in audio_codecs if codec}
    if not known_video:
        return True
    if profile.extension == 'mp4':
        video_ok = known_video <= {'h264', 'avc', 'avc1'}
        audio_ok = not known_audio or known_audio <= {'aac', 'mp4a'}
        return video_ok and audio_ok
    video_ok = known_video <= {'vp8', 'vp9', 'av1', 'av01'}
    audio_ok = not known_audio or known_audio <= {'opus', 'vorbis'}
    return video_ok and audio_ok


def resolve_final_media(info, postprocessed_paths, save_dir, profile_name, preexisting=None, probe_runner=None, *,
                        output_tag=None):
    profile = output_profile(profile_name)
    candidates = collect_output_candidates(
        info, postprocessed_paths, save_dir, profile.extension, preexisting, output_tag=output_tag,
    )
    valid = []
    errors = []
    for candidate in candidates:
        try:
            validated, probe = validate_final_media(candidate, save_dir, profile_name, probe_runner)
            valid.append((validated.stat().st_mtime_ns, validated, probe))
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    if not valid:
        summary = errors[-1] if errors else f"No postprocessed .{profile.extension} output was produced"
        raise ValueError(summary)
    _, path, probe = max(valid, key=lambda item: item[0])
    return path, probe


def cleanup_verified_intermediates(paths, final_path, save_dir):
    root = Path(save_dir).resolve(strict=True)
    final = Path(final_path).resolve(strict=True)
    removed = []
    for raw_path in paths:
        try:
            candidate = Path(raw_path).resolve(strict=True)
            candidate.relative_to(root)
            if candidate == final or not candidate.is_file():
                continue
            if re.search(r'\.f\d+\.', candidate.name, re.IGNORECASE) or '.part' in candidate.name or candidate.suffix.lower() == '.ytdl':
                candidate.unlink(); removed.append(candidate)
        except (OSError, ValueError):
            continue
    return removed


def clean_error_summary(value, limit=400):
    text = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value or '')
    text = ANSI_ESCAPE_RE.sub('', text) if 'ANSI_ESCAPE_RE' in globals() else re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = re.sub(r'https?://\S+', '[URL omitted]', text)
    text = re.sub(r'(?i)\b(?:referer|origin|user-agent|cookie|authorization)\s*:\s*[^\r\n]+', '[header omitted]', text)
    text = re.sub(r'(?i)(?:--cookies-from-browser|cookiesfrombrowser|browser profile|profile path)\s*[:=]?\s*[^\r\n,;]+', '[authentication details omitted]', text)
    text = re.sub(r'(?i)(?:(?:copy|read|load|decrypt)[^\r\n]{0,40}(?:cookie|profile)[^\r\n]{0,20})(?:[A-Z]:\\|/Users/|/home/)[^\r\n]+', '[authentication path omitted]', text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return (lines[-1] if lines else 'No diagnostic details available')[:limit]


def customer_extraction_error(error):
    if is_authentication_extraction_error(error):
        return (
            'This media requires sign-in or returned no public formats. '
            'You can enable the isolated browser-profile retry in Browser Integration.'
        )
    return clean_error_summary(error)


class JobState(str, Enum):
    QUEUED = 'queued'
    RESOLVING = 'resolving'
    CONNECTING = 'connecting'
    DOWNLOADING = 'downloading'
    PAUSED = 'paused'
    MERGING = 'merging'
    CONVERTING = 'converting'
    VERIFYING = 'verifying'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    RETRYING = 'retrying'
    FAILED = 'failed'


@dataclass
class DownloadJob:
    job_id: str
    source_url: str
    save_dir: str
    requested_format: str
    resolved_media_url: str = ''
    requested_resolution: int | None = None
    package_id: str | None = None
    final_output_path: str = ''
    temporary_paths: list[str] = field(default_factory=list)
    actual_format: str = ''
    actual_resolution: int | None = None
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed: float = 0.0
    eta: int | None = None
    priority: int = 0
    queue_name: str = 'Default'
    state: str = JobState.QUEUED.value
    retry_count: int = 0
    error_summary: str = ''
    resumable: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))
    started_at: str = ''
    completed_at: str = ''
    file_name_hint: str = ''

    def to_dict(self):
        payload = asdict(self)
        payload['original_source_url'] = self.source_url
        payload.pop('resolved_media_url', None)
        return payload

    @property
    def original_source_url(self):
        return self.source_url

    @classmethod
    def from_dict(cls, payload):
        payload = dict(payload)
        if 'source_url' not in payload and isinstance(payload.get('original_source_url'), str):
            payload['source_url'] = payload['original_source_url']
        allowed = cls.__dataclass_fields__.keys()
        values = {key: payload[key] for key in allowed if key in payload}
        job = cls(**values)
        if job.state not in {state.value for state in JobState}:
            job.state = JobState.FAILED.value
            job.error_summary = 'Recovered job had an invalid state'
        if job.state in {JobState.RESOLVING.value, JobState.CONNECTING.value, JobState.DOWNLOADING.value,
                         JobState.MERGING.value, JobState.CONVERTING.value, JobState.VERIFYING.value,
                         JobState.RETRYING.value}:
            job.state = JobState.PAUSED.value if job.resumable else JobState.QUEUED.value
            job.error_summary = 'Recovered after an unexpected application exit'
        return job


def job_capabilities(job):
    state = JobState(job.state)
    final_exists = bool(job.final_output_path and Path(job.final_output_path).is_file())
    supported_input = Path(job.final_output_path).suffix.lower().lstrip('.') in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
    return {
        'resume': state in {JobState.PAUSED, JobState.FAILED, JobState.RETRYING} and job.resumable,
        'pause': state == JobState.DOWNLOADING,
        'stop': state in {JobState.QUEUED, JobState.RESOLVING, JobState.CONNECTING, JobState.DOWNLOADING, JobState.RETRYING, JobState.CONVERTING},
        'convert': state == JobState.COMPLETED and final_exists and supported_input,
        'open': state == JobState.COMPLETED and final_exists,
        'open_folder': state == JobState.COMPLETED and final_exists,
        'delete': state not in {JobState.MERGING, JobState.CONVERTING, JobState.VERIFYING},
        'edit': state in {JobState.QUEUED, JobState.PAUSED, JobState.FAILED},
    }


class DownloadManager(QObject):
    job_changed = pyqtSignal(str, str)

    def __init__(self, app_config, queue_path=None):
        super().__init__()
        self.app_config = app_config
        self.queue_path = Path(queue_path) if queue_path else app_config.app_data_root / 'history' / 'queue.json'
        self.jobs = {}
        self.queue = []
        self.stop_after_current = app_config.stop_after_current
        self.load()

    def add_job(self, job):
        self.jobs[job.job_id] = job
        if job.job_id not in self.queue:
            self.queue.append(job.job_id)
        self.persist()
        self.job_changed.emit(job.job_id, job.state)
        return job

    def set_state(self, job_id, state, error=''):
        job = self.jobs[job_id]
        state_value = state.value if isinstance(state, JobState) else str(state)
        job.state = state_value
        if state_value == JobState.DOWNLOADING.value and not job.started_at:
            job.started_at = datetime.now().isoformat(timespec='seconds')
        if state_value == JobState.COMPLETED.value:
            job.completed_at = datetime.now().isoformat(timespec='seconds')
        if error:
            job.error_summary = clean_error_summary(error)
        self.persist()
        self.job_changed.emit(job_id, state_value)

    def update_progress(self, job_id, downloaded=0, total=0, speed=0, eta=None):
        job = self.jobs[job_id]
        job.downloaded_bytes = int(max(0, downloaded or 0))
        job.total_bytes = int(max(0, total or 0))
        job.speed = float(max(0, speed or 0))
        job.eta = int(eta) if eta is not None else None

    def move(self, job_id, offset):
        index = self.queue.index(job_id)
        target = max(0, min(len(self.queue) - 1, index + offset))
        self.queue.insert(target, self.queue.pop(index))
        self.persist()

    def active_count(self):
        active = {JobState.RESOLVING.value, JobState.CONNECTING.value, JobState.DOWNLOADING.value,
                  JobState.MERGING.value, JobState.CONVERTING.value, JobState.VERIFYING.value}
        return sum(job.state in active for job in self.jobs.values())

    def pending_jobs(self):
        return [self.jobs[job_id] for job_id in self.queue if self.jobs[job_id].state == JobState.QUEUED.value]

    def can_start_more(self):
        return not self.stop_after_current and self.active_count() < self.app_config.max_simultaneous_downloads

    def retry(self, job_id):
        job = self.jobs[job_id]
        if job.retry_count >= MAX_RETRY_ATTEMPTS:
            return False
        job.retry_count += 1
        self.set_state(job_id, JobState.RETRYING)
        return True

    def persist(self):
        recoverable_states = {
            JobState.QUEUED.value, JobState.RESOLVING.value, JobState.CONNECTING.value,
            JobState.DOWNLOADING.value, JobState.PAUSED.value, JobState.MERGING.value,
            JobState.CONVERTING.value, JobState.VERIFYING.value, JobState.RETRYING.value, JobState.FAILED.value,
        }
        recoverable = [job_id for job_id in self.queue if job_id in self.jobs and self.jobs[job_id].state in recoverable_states][-500:]
        payload = {'queue': recoverable, 'jobs': [self.jobs[job_id].to_dict() for job_id in recoverable]}
        atomic_write_json(self.queue_path, payload)

    def load(self):
        if not self.queue_path.exists():
            return
        if self.queue_path.stat().st_size > 2 * 1024 * 1024:
            os.replace(self.queue_path, self.queue_path.with_suffix(self.queue_path.suffix + '.oversize'))
            return
        try:
            payload = json.loads(self.queue_path.read_text(encoding='utf-8'))
            for item in payload.get('jobs', []):
                job = DownloadJob.from_dict(item)
                self.jobs[job.job_id] = job
            self.queue = [job_id for job_id in payload.get('queue', []) if job_id in self.jobs]
            for job_id in self.jobs:
                if job_id not in self.queue:
                    self.queue.append(job_id)
            self.persist()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            corrupt = self.queue_path.with_suffix(self.queue_path.suffix + '.corrupt')
            try:
                os.replace(self.queue_path, corrupt)
            except OSError:
                pass


def sanitize_source_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ''
        if parsed.port:
            host = f'{host}:{parsed.port}'
        sensitive = {'token', 'auth', 'authorization', 'password', 'credential', 'signature', 'sig', 'key',
                     'expires', 'expiry', 'exp', 'x-amz-signature', 'x-amz-credential', 'x-amz-expires'}
        query = []
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
            lowered = key.lower()
            if lowered in sensitive or any(marker in lowered for marker in ('token', 'signature', 'credential')):
                continue
            query.append((key, value))
        return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, urllib.parse.urlencode(query), ''))
    except (TypeError, ValueError):
        return '[invalid URL]'


def media_summary(probe):
    streams = probe.get('streams', []) if isinstance(probe, dict) else []
    codecs = [str(stream.get('codec_name') or 'unknown') for stream in streams if isinstance(stream, dict)]
    video = next((stream for stream in streams if isinstance(stream, dict) and stream.get('codec_type') == 'video'), None)
    resolution = f"{video.get('width')}x{video.get('height')}" if video and video.get('width') and video.get('height') else 'audio only'
    return {
        'container': str(probe.get('format_name') or 'unknown'),
        'codecs': ', '.join(codecs) or 'unknown',
        'resolution': resolution,
        'duration': float(probe.get('duration') or 0),
    }


def conversion_target_capabilities(probe):
    streams = probe.get('streams', []) if isinstance(probe, dict) else []
    has_video = any(isinstance(stream, dict) and stream.get('codec_type') == 'video' for stream in streams)
    has_audio = any(isinstance(stream, dict) and stream.get('codec_type') == 'audio' for stream in streams)
    capabilities = {}
    for name, profile in OUTPUT_PROFILES.items():
        if not (has_video or has_audio):
            enabled, reason = False, 'FFprobe found no audio or video streams.'
        elif has_video:
            enabled, reason = True, 'Available; conversion creates a new re-encoded file.'
        elif profile.media_kind == 'audio' or name == 'MP4':
            enabled, reason = True, 'Available for audio input; conversion creates a new file.'
        else:
            enabled, reason = False, f'{name} requires a video stream; this input is audio-only.'
        if profile.media_kind == 'audio' and not has_audio:
            enabled, reason = False, f'{name} requires an audio stream; none was detected.'
        capabilities[name] = {'enabled': enabled, 'reason': reason}
    return capabilities


def conversion_supported(input_path, target_ext, probe=None):
    try:
        actual_probe = probe if probe is not None else probe_media_file(input_path)
        return conversion_target_capabilities(actual_probe)[str(target_ext).upper()]['enabled']
    except (KeyError, OSError, ValueError, subprocess.SubprocessError):
        return False


def unique_conversion_destination(input_path, target_ext, output_dir=None, exists=None):
    source = Path(input_path).resolve(strict=True)
    output_root = Path(output_dir or source.parent).resolve(strict=True)
    if not output_root.is_dir():
        raise ValueError('Output folder does not exist')
    target = output_profile(target_ext).extension
    exists = exists or (lambda path: path.exists())
    stem = source.stem + '_converted'
    counter = 0
    while True:
        suffix = '' if counter == 0 else f'_{counter}'
        candidate = output_root / f'{stem}{suffix}.{target}'
        if candidate != source and not exists(candidate) and not exists(candidate.with_name(candidate.name + '.claim')):
            return candidate
        counter += 1


def conversion_destination_for_behavior(input_path, target_ext, output_dir=None, behavior='unique', confirm=None, reserved=None):
    source = Path(input_path).resolve(strict=True)
    root = Path(output_dir or source.parent).resolve(strict=True)
    profile = output_profile(target_ext)
    preferred = root / f'{source.stem}_converted.{profile.extension}'
    normalized = str(behavior).lower()
    if normalized == 'unique':
        reserved_paths = {str(Path(path).resolve()) for path in (reserved or set())}
        return unique_conversion_destination(source, target_ext, root, lambda path: path.exists() or str(path.resolve()) in reserved_paths)
    if normalized not in {'ask', 'skip'}:
        raise ValueError('Overwrite behavior must be unique, ask, or skip')
    if preferred == source:
        raise ValueError('Conversion cannot overwrite the source file')
    if not preferred.exists():
        return preferred
    if normalized == 'skip':
        raise FileExistsError(f'Skipped because destination exists: {preferred.name}')
    if confirm is None:
        raise PermissionError(f'Confirmation required to replace: {preferred.name}')
    if not confirm(preferred):
        raise FileExistsError(f'Skipped by user: {preferred.name}')
    return preferred


@dataclass(frozen=True)
class ConversionPlan:
    source: Path
    destination: Path
    temporary_output: Path
    target_name: str
    required_stream: str
    duration: float
    command: tuple


def build_conversion_plan(input_path, target_ext, output_dir=None, probe=None, destination=None):
    source = Path(input_path).resolve(strict=True)
    actual_probe = probe if probe is not None else probe_media_file(source)
    target_name = str(target_ext).upper()
    profile = output_profile(target_name)
    capability = conversion_target_capabilities(actual_probe)[target_name]
    if not capability['enabled']:
        raise ValueError(capability['reason'])
    final_path = Path(destination).resolve() if destination else unique_conversion_destination(source, target_name, output_dir)
    if final_path == source:
        raise ValueError('Conversion cannot overwrite the source file')
    has_video = any(stream.get('codec_type') == 'video' for stream in actual_probe.get('streams', []) if isinstance(stream, dict))
    required_stream = 'video' if profile.media_kind == 'video' and has_video else 'audio'
    codec_args = profile.ffmpeg_video_args if required_stream == 'video' else profile.ffmpeg_audio_args
    if not codec_args:
        raise ValueError(f'{target_name} is not compatible with this input')
    temporary = final_path.with_name(f'{final_path.stem}.partial-{uuid.uuid4().hex[:8]}.{profile.extension}')
    command = (
        get_ffmpeg_path(), '-y', '-v', 'error', '-i', str(source), *codec_args,
        '-progress', 'pipe:1', '-nostats', str(temporary),
    )
    return ConversionPlan(source, final_path, temporary, target_name, required_stream, float(actual_probe.get('duration') or 0), command)


def convert_incompatible_profile_output(input_path, profile_name, save_dir, probe=None, runner=None,
                                        cancel_check=None):
    source = Path(input_path).resolve(strict=True)
    actual_probe = probe if probe is not None else probe_media_file(source)
    if profile_codecs_compatible(actual_probe, profile_name):
        return source, actual_probe
    plan = build_conversion_plan(source, profile_name, save_dir, actual_probe)
    kwargs = {
        'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE,
        'timeout': CONVERSION_TIMEOUT_SECONDS,
    }
    creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if creation_flags:
        kwargs['creationflags'] = creation_flags

    def check_cancellation():
        if cancel_check is not None and cancel_check():
            raise CancelException("Cancelled")

    try:
        check_cancellation()
        if cancel_check is not None and runner is None:
            # The download worker must be able to interrupt FFmpeg mid-conversion.
            popen_options = {key: value for key, value in kwargs.items() if key != 'timeout'}
            process = subprocess.Popen(list(plan.command), **popen_options)
            try:
                deadline = time.monotonic() + CONVERSION_TIMEOUT_SECONDS
                while True:
                    check_cancellation()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ValueError("FFmpeg compatibility conversion timed out")
                    try:
                        stdout, stderr = process.communicate(timeout=min(0.2, remaining))
                        result = subprocess.CompletedProcess(plan.command, process.returncode, stdout, stderr)
                        break
                    except subprocess.TimeoutExpired:
                        continue
            finally:
                if process.returncode is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
        else:
            result = (runner or subprocess.run)(list(plan.command), **kwargs)
        check_cancellation()
        if result.returncode != 0:
            raise ValueError(f"FFmpeg compatibility conversion failed: {clean_error_summary(result.stderr)}")
        validate_final_media(plan.temporary_output, plan.destination.parent, plan.target_name, required_stream=plan.required_stream)
        check_cancellation()
        os.replace(plan.temporary_output, plan.destination)
        try:
            final_path, final_probe = validate_final_media(
                plan.destination, plan.destination.parent, plan.target_name,
                required_stream=plan.required_stream,
            )
            if not profile_codecs_compatible(final_probe, plan.target_name):
                raise ValueError(f"FFprobe found incompatible codecs in the final {plan.target_name} output")
            check_cancellation()
            # Source deletion is irreversible: only after successful validation and
            # a final cancellation check should we discard the original media.
            source.unlink()
        except CancelException:
            plan.destination.unlink(missing_ok=True)
            raise
        return final_path, final_probe
    finally:
        plan.temporary_output.unlink(missing_ok=True)


def parse_ffmpeg_progress(values, duration, started_at, now=None):
    now = time.monotonic() if now is None else now
    elapsed = max(0.0, now - started_at)
    raw_time = values.get('out_time_us') or values.get('out_time_ms')
    if raw_time is not None:
        try: media_seconds = max(0.0, float(raw_time) / 1_000_000)
        except (TypeError, ValueError): media_seconds = 0.0
    else:
        parts = str(values.get('out_time') or '0:0:0').split(':')
        try: media_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except (ValueError, IndexError): media_seconds = 0.0
    percent = 100.0 if values.get('progress') == 'end' else (media_seconds / duration * 100 if duration > 0 else 0.0)
    percent = max(0.0, min(100.0, percent))
    eta = (elapsed * (100.0 - percent) / percent) if 0 < percent < 100 else (0.0 if percent >= 100 else None)
    return {'state': 'converting', 'percent': percent, 'elapsed': elapsed, 'eta': eta, 'media_seconds': media_seconds}


def create_converter_jobs(paths, target_ext, output_dir=None, overwrite_behavior='unique', confirm=None):
    jobs = []
    reserved = set()
    for raw_path in paths:
        source = Path(raw_path).resolve(strict=True)
        probe = probe_media_file(source)
        destination = conversion_destination_for_behavior(source, target_ext, output_dir, overwrite_behavior, confirm, reserved)
        plan = build_conversion_plan(source, target_ext, output_dir, probe, destination)
        jobs.append({'job_id': uuid.uuid4().hex, 'source': str(source), 'probe': probe, 'plan': plan})
        reserved.add(str(plan.destination.resolve()))
    return jobs

# ==========================================
# 1. LOCAL SERVER
# ==========================================
class DownloadServerHandler(http.server.BaseHTTPRequestHandler):
    def send_cors_headers(self):
        origin = self.headers.get('Origin', '')
        runtime = self.server.app_config
        if origin in runtime.allowed_origins or validate_extension_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Stratrum-Auth')

    def do_OPTIONS(self):
        self.send_response(200); self.send_cors_headers(); self.end_headers()

    def do_POST(self):
        if self.path != '/add_download':
            self.send_response(404); self.end_headers(); return

        status_code, result = validate_request(self.headers, self.rfile, self.server.app_config)

        if status_code == 200 and result['action'] == 'http_download':
            receipt = HandoffReceipt()
            self.server.file_signal.emit(
                result['url'], result['context'], result['file_name_hint'], receipt
            )
            # Do not acknowledge until Qt has actually accepted the local job.
            accepted = receipt.wait(5)
            self.send_response(200 if accepted else 503)
            self.send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"success"}' if accepted else
                             b'{"error":"Desktop did not accept file handoff"}')
            return

        self.send_response(status_code); self.send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if status_code == 200:
            self.wfile.write(b'{"status": "success"}')
            self.server.url_signal.emit(result['url'], result['action'], result['context'])
        else:
            self.wfile.write(result)

    def log_message(self, format, *args):
        pass

class ServerThread(QThread):
    download_requested = pyqtSignal(str, str, dict)
    file_requested = pyqtSignal(str, dict, str, object)
    failed = pyqtSignal(str)
    def __init__(self, app_config):
        super().__init__()
        self.app_config = app_config
    def run(self):
        try:
            self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", BROWSER_BRIDGE_PORT), DownloadServerHandler)
        except OSError:
            self.failed.emit(f"Browser integration cannot start on 127.0.0.1:{BROWSER_BRIDGE_PORT}. Another app may be using the port.")
            return
        self.httpd.app_config = self.app_config
        self.httpd.url_signal = self.download_requested
        self.httpd.file_signal = self.file_requested
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
    def __init__(self, url, request_context=None, app_config=None):
        super().__init__(); self.url = url; self.request_context = request_context or {}; self.app_config = app_config
    def run(self):
        try:
            options = {**controlled_yt_dlp_options(), 'quiet': True, 'noplaylist': True}
            if self.request_context.get('http_headers'):
                options['http_headers'] = dict(self.request_context['http_headers'])
            anonymous_options = extraction_options_for_url(options, self.url)
            try:
                with yt_dlp.YoutubeDL(anonymous_options) as ydl:
                    info = ydl.extract_info(self.url, download=False)
            except Exception as first_error:
                if not should_retry_authenticated_extraction(first_error, self.url, self.app_config):
                    raise
                retry_options = authenticated_retry_options(options, self.url, self.app_config)
                with yt_dlp.YoutubeDL(retry_options) as ydl:
                    info = ydl.extract_info(self.url, download=False)
            self.formats_ready.emit(info)
        except Exception as e:
            self.error_occurred.emit(customer_extraction_error(e))

class ConvertThread(QThread):
    finished = pyqtSignal(str, bool, str, str)
    progress = pyqtSignal(str, dict)
    def __init__(self, row_id, input_file, target_ext, output_dir=None, destination=None):
        super().__init__()
        self.row_id = row_id; self.input_file = input_file; self.target_ext = target_ext
        self.output_dir = output_dir; self.destination = destination
        self.cancelled = False
        self.process = None
        self._process_lock = threading.Lock()
        self.paused = False

    def _change_process_suspension(self, pause):
        with self._process_lock:
            process = self.process
        if process is None or process.poll() is not None:
            return False
        try:
            if os.name == 'nt':
                import ctypes
                access = 0x0800
                kernel32 = ctypes.windll.kernel32
                kernel32.OpenProcess.restype = ctypes.c_void_p
                kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
                handle = kernel32.OpenProcess(access, False, process.pid)
                if not handle:
                    return False
                try:
                    operation = ctypes.windll.ntdll.NtSuspendProcess if pause else ctypes.windll.ntdll.NtResumeProcess
                    operation.argtypes = (ctypes.c_void_p,)
                    if operation(handle) != 0:
                        return False
                finally:
                    kernel32.CloseHandle(handle)
            else:
                os.kill(process.pid, signal.SIGSTOP if pause else signal.SIGCONT)
            self.paused = pause
            self.progress.emit(self.row_id, {'state': 'paused' if pause else 'converting'})
            return True
        except (OSError, AttributeError, TypeError):
            return False

    def pause(self):
        if self.cancelled or self.paused:
            return False
        return self._change_process_suspension(True)

    def resume(self):
        if self.cancelled or not self.paused:
            return False
        return self._change_process_suspension(False)

    def cancel(self):
        self.cancelled = True
        self.requestInterruption()
        if self.paused:
            self._change_process_suspension(False)
        with self._process_lock:
            process = self.process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    return False
        return process is None or process.poll() is not None

    def run(self):
        claim_path = None; temporary_path = None; stderr_log = None
        try:
            input_path = Path(self.input_file)
            if not input_path.is_file():
                self.finished.emit(self.row_id, False, "Input file does not exist", "")
                return

            if self.cancelled or self.isInterruptionRequested():
                self.finished.emit(self.row_id, False, "Conversion cancelled", "")
                return

            source_probe = probe_media_file(input_path)
            with _conversion_name_lock:
                plan = build_conversion_plan(input_path, self.target_ext, self.output_dir, source_probe, self.destination)
                output_path = plan.destination
                potential_claim_path = output_path.with_name(output_path.name + '.claim')
                claim_fd = os.open(potential_claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                claim_path = potential_claim_path
                os.close(claim_fd)
            temporary_path = plan.temporary_output
            self.progress.emit(self.row_id, {'source': str(plan.source), 'destination': str(output_path), 'target': plan.target_name, 'state': 'starting', 'percent': 0.0, 'elapsed': 0.0, 'eta': None})
            stderr_log = tempfile.TemporaryFile(mode='w+t', encoding='utf-8', errors='replace')
            run_kwargs = {'stdout': subprocess.PIPE, 'stderr': stderr_log, 'text': True, 'encoding': 'utf-8', 'errors': 'replace', 'bufsize': 1}
            creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            if creation_flags:
                run_kwargs['creationflags'] = creation_flags
            with self._process_lock:
                self.process = subprocess.Popen(list(plan.command), **run_kwargs)
            values = {}; started_at = time.monotonic()
            for raw_line in self.process.stdout:
                if self.cancelled or self.isInterruptionRequested():
                    self.cancel(); break
                key, separator, value = raw_line.strip().partition('=')
                if separator:
                    values[key] = value
                if key == 'progress':
                    snapshot = parse_ffmpeg_progress(values, plan.duration, started_at)
                    snapshot.update({'source': str(plan.source), 'destination': str(output_path), 'target': plan.target_name})
                    self.progress.emit(self.row_id, snapshot); values = {}
                if time.monotonic() - started_at > CONVERSION_TIMEOUT_SECONDS:
                    self.cancel(); raise subprocess.TimeoutExpired(plan.command, CONVERSION_TIMEOUT_SECONDS)
            return_code = self.process.wait()
            stderr_log.seek(0); stderr = stderr_log.read()
            if self.cancelled or self.isInterruptionRequested():
                self.finished.emit(self.row_id, False, "Conversion cancelled", "")
            elif return_code != 0:
                self.finished.emit(self.row_id, False, f"Conversion failed: {clean_error_summary(stderr)}", "")
            elif not temporary_path.is_file():
                self.finished.emit(self.row_id, False, "Conversion produced no output file", "")
            else:
                validate_final_media(temporary_path, output_path.parent, plan.target_name, required_stream=plan.required_stream)
                os.replace(temporary_path, output_path)
                validate_final_media(output_path, output_path.parent, plan.target_name, required_stream=plan.required_stream)
                self.finished.emit(self.row_id, True, "Conversion complete", str(output_path))
        except subprocess.TimeoutExpired:
            self.finished.emit(self.row_id, False, "Conversion timed out and was cancelled", "")
        except FileExistsError:
            self.finished.emit(self.row_id, False, "Destination is already reserved by another conversion", "")
        except Exception as e:
            self.finished.emit(self.row_id, False, clean_error_summary(e), "")
        finally:
            with self._process_lock:
                self.process = None
            if stderr_log is not None:
                stderr_log.close()
            if temporary_path is not None:
                try: temporary_path.unlink()
                except FileNotFoundError: pass
            if claim_path is not None:
                try:
                    claim_path.unlink()
                except FileNotFoundError:
                    pass


class ConversionJobController(QObject):
    progress = pyqtSignal(str, dict)
    finished = pyqtSignal(str, bool, str, str)
    state_changed = pyqtSignal(str, str)

    def __init__(self, parent=None, thread_factory=ConvertThread):
        super().__init__(parent)
        self.thread_factory = thread_factory
        self.jobs = {}

    def start(self, job_id, input_file, target_ext, output_dir=None, destination=None):
        if job_id in self.jobs:
            return False
        thread = self.thread_factory(job_id, input_file, target_ext, output_dir, destination)
        generation = uuid.uuid4().hex
        self.jobs[job_id] = {'thread': thread, 'generation': generation, 'state': 'starting', 'snapshot': {'state': 'starting'}}
        thread.progress.connect(lambda emitted_id, snapshot, token=generation: self._progress(emitted_id, snapshot, token))
        thread.finished.connect(lambda emitted_id, success, message, output, token=generation: self._finished(emitted_id, success, message, output, token))
        self.state_changed.emit(job_id, 'starting')
        thread.start()
        return True

    def _current(self, job_id, generation):
        job = self.jobs.get(job_id)
        return job if job and job['generation'] == generation else None

    def _progress(self, job_id, snapshot, generation):
        job = self._current(job_id, generation)
        if not job:
            return
        merged = dict(job.get('snapshot') or {})
        merged.update(snapshot)
        state = str(merged.get('state') or 'converting')
        merged['state'] = state
        job['snapshot'] = merged
        job['state'] = state
        self.state_changed.emit(job_id, state)
        self.progress.emit(job_id, merged)

    def _finished(self, job_id, success, message, output_path, generation):
        job = self._current(job_id, generation)
        if not job:
            return
        cancelled = job['state'] in {'cancelling', 'stop_failed'} or 'cancelled' in str(message).lower()
        if cancelled:
            success, message, output_path = False, 'Conversion cancelled', ''
        job['state'] = 'completed' if success else ('cancelled' if cancelled else 'failed')
        self.state_changed.emit(job_id, job['state'])
        self.finished.emit(job_id, success, message, output_path)
        self.jobs.pop(job_id, None)

    def pause(self, job_id):
        job = self.jobs.get(job_id)
        if not job or job['state'] not in {'starting', 'converting'} or not job['thread'].pause():
            return False
        self._progress(job_id, {'state': 'paused'}, job['generation'])
        return True

    def resume(self, job_id):
        job = self.jobs.get(job_id)
        if not job or job['state'] != 'paused' or not job['thread'].resume():
            return False
        self._progress(job_id, {'state': 'converting'}, job['generation'])
        return True

    def cancel(self, job_id, wait_ms=5000, remove=False):
        job = self.jobs.get(job_id)
        if not job or job['state'] in {'completed', 'failed', 'cancelled'}:
            return False
        job['state'] = 'cancelling'; self.state_changed.emit(job_id, 'cancelling')
        stopped = job['thread'].cancel()
        if job['thread'].isRunning():
            stopped = job['thread'].wait(wait_ms) and stopped
        if not stopped or job['thread'].isRunning():
            job['state'] = 'stop_failed'; self.state_changed.emit(job_id, 'stop_failed'); return False
        if remove:
            self.jobs.pop(job_id, None)
        return True

    def state(self, job_id):
        job = self.jobs.get(job_id)
        return job['state'] if job else None

# ==========================================
# 3. DOWNLOAD ENGINE ("THE SPEED GRABBER")
# ==========================================
class PauseException(Exception): pass


class CancelException(Exception): pass


ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*m')


def finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_bytes(byte_count):
    value = finite_number(byte_count)
    if value is None:
        return "N/A"
    value = max(0.0, value)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024.0 or unit == 'TB':
            return f"{value:.2f} {unit}"
        value /= 1024.0


def format_eta(seconds):
    value = finite_number(seconds)
    if value is None or value < 0:
        return "N/A"
    total_seconds = int(value)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def clean_progress_text(value, default="N/A"):
    if not isinstance(value, str):
        return default
    cleaned = ANSI_ESCAPE_RE.sub('', value).strip()
    return cleaned or default


def fallback_percent(value):
    cleaned = clean_progress_text(value, '')
    match = re.search(r'-?\d+(?:\.\d+)?', cleaned)
    if not match:
        return 0.0
    try:
        return float(match.group(0))
    except ValueError:
        return 0.0


def build_progress_snapshot(progress_data):
    data = progress_data if isinstance(progress_data, dict) else {}
    info_dict = data.get('info_dict') if isinstance(data.get('info_dict'), dict) else {}
    raw_filename = data.get('filename') or info_dict.get('_filename') or ''
    filename = os.path.basename(str(raw_filename)) if raw_filename else "Connecting..."

    downloaded = finite_number(data.get('downloaded_bytes'))
    downloaded = max(0.0, downloaded) if downloaded is not None else 0.0
    total = finite_number(data.get('total_bytes'))
    if total is None or total <= 0:
        total = finite_number(data.get('total_bytes_estimate'))
    total = total if total is not None and total > 0 else None

    if total is not None:
        percent = downloaded / total * 100.0
    else:
        percent = fallback_percent(data.get('_percent_str'))
    percent = min(100.0, max(0.0, percent))

    numeric_speed = finite_number(data.get('speed'))
    if numeric_speed is not None and numeric_speed >= 0:
        speed = f"{format_bytes(numeric_speed)}/s"
    else:
        speed = clean_progress_text(data.get('_speed_str'))

    numeric_eta = finite_number(data.get('eta'))
    eta = format_eta(numeric_eta) if numeric_eta is not None else clean_progress_text(data.get('_eta_str'))
    status = str(data.get('status') or 'downloading').capitalize()
    return {
        'filename': filename,
        'percent': percent,
        'downloaded': format_bytes(downloaded),
        'total': format_bytes(total) if total is not None else "N/A",
        'speed': speed,
        'eta': eta,
        'status': status,
    }


def format_transfer_size(downloaded, total):
    return f"{downloaded} / {total if total != 'N/A' else 'unknown total'}"


class DownloadThread(QThread):
    progress = pyqtSignal(str, str, float, str, str, str, str, str)
    status = pyqtSignal(str, str)
    finished = pyqtSignal(str, bool, str, str)
    size_updated = pyqtSignal(str, str, str)
    metrics = pyqtSignal(str, int, int, float, object)

    def __init__(self, id, url, outtmpl, format_str, target_ext, requested_height=None,
                 metadata=None, save_dir=None, speed_limit_bps=0, request_context=None, app_config=None):
        super().__init__()
        self.id = id; self.url = url; self.outtmpl = outtmpl
        self.profile_name = str(target_ext).upper()
        self.target_ext = output_profile(self.profile_name).extension
        self.requested_height = requested_height
        self.metadata = metadata or {}
        self.save_dir = str(Path(save_dir or os.path.dirname(outtmpl)).resolve())
        self.format_str = format_str or build_format_selector(self.profile_name, requested_height)
        self.speed_limit_bps = int(speed_limit_bps or 0)
        self.request_context = request_context or {}
        self.app_config = app_config
        self.paused = False
        self.cancelled = False
        self.final_filename = ""
        self.postprocessed_paths = []
        self.temporary_paths = set()
        self.ydl = None
        self.final_probe = {}
        self.resolved_media_url = ''
        self.current_stage = 'download'

    def set_speed_limit(self, bytes_per_second):
        self.speed_limit_bps = max(0, int(bytes_per_second or 0))
        if self.ydl is not None:
            self.ydl.params['ratelimit'] = self.speed_limit_bps or None

    def cancel(self):
        self.cancelled = True
        self.requestInterruption()

    def postprocessor_hook(self, event):
        status = event.get('status') if isinstance(event, dict) else None
        if status == 'started':
            profile = output_profile(self.profile_name)
            needs_conversion = profile.media_kind == 'audio' or profile.explicit_conversion or (
                profile.extension == 'mp4' and not mp4_compatible_streams_available(self.metadata, self.requested_height)
            ) or (
                profile.extension == 'webm' and not webm_compatible_streams_available(self.metadata, self.requested_height)
            )
            state = 'Converting' if needs_conversion else 'Merging streams'
            self.current_stage = 'conversion' if needs_conversion else 'merge'
            self.status.emit(self.id, state)
        path = postprocessor_output_path(event)
        if path:
            self.postprocessed_paths.append(path)

    def format_size(self, bytes):
        return format_bytes(bytes)

    def progress_hook(self, d):
        if self.paused: raise PauseException("Paused")
        if self.cancelled or self.isInterruptionRequested(): raise CancelException("Cancelled")
        status = d.get('status') if isinstance(d, dict) else None
        if status == 'downloading':
            snapshot = build_progress_snapshot(d)
            info_dict = d.get('info_dict') if isinstance(d.get('info_dict'), dict) else {}
            has_video = info_dict.get('vcodec') not in {None, 'none'}
            has_audio = info_dict.get('acodec') not in {None, 'none'}
            if has_video and not has_audio:
                download_status = 'Downloading video stream'
            elif has_audio and not has_video:
                download_status = 'Downloading audio stream'
            else:
                download_status = 'Downloading media'
            downloaded_value = int(max(0, finite_number(d.get('downloaded_bytes')) or 0))
            total_value = int(max(0, finite_number(d.get('total_bytes')) or finite_number(d.get('total_bytes_estimate')) or 0))
            speed_value = max(0.0, finite_number(d.get('speed')) or 0.0)
            eta_value = finite_number(d.get('eta'))
            self.metrics.emit(self.id, downloaded_value, total_value, speed_value, int(eta_value) if eta_value is not None else None)
            raw_path = d.get('filename') if isinstance(d, dict) else None
            if raw_path:
                self.temporary_paths.add(str(raw_path))
            if snapshot['total'] != "N/A":
                self.size_updated.emit(self.id, snapshot['filename'], snapshot['total'])
            self.status.emit(self.id, download_status)
            self.progress.emit(
                self.id, snapshot['filename'], snapshot['percent'], snapshot['downloaded'],
                snapshot['total'], snapshot['speed'], snapshot['eta'], snapshot['status']
            )
        elif status == 'finished':
            info_dict = d.get('info_dict') if isinstance(d.get('info_dict'), dict) else {}
            intermediate = info_dict.get('_filename') or d.get('filename', '')
            if intermediate:
                self.temporary_paths.add(str(intermediate))
            snapshot = build_progress_snapshot(d)
            self.status.emit(self.id, 'Postprocessing')
            self.progress.emit(
                self.id, snapshot['filename'], 100.0, snapshot['downloaded'],
                snapshot['total'], snapshot['speed'], snapshot['eta'], 'Postprocessing'
            )

    def run(self):
        try:
            profile = output_profile(self.profile_name)
            preexisting = {str(path.resolve()) for path in Path(self.save_dir).glob(f'*.{profile.extension}')}
            base_ydl_opts = build_download_options(
                self.profile_name, self.outtmpl, self.requested_height, self.metadata,
                [self.progress_hook], [self.postprocessor_hook], self.speed_limit_bps,
                self.request_context,
            )
            ydl_opts = extraction_options_for_url(base_ydl_opts, self.url)
            self.format_str = ydl_opts['format']
            self.status.emit(self.id, 'Connecting')
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self.ydl = ydl
                    info = ydl.extract_info(self.url, download=True)
            except Exception as first_error:
                if not should_retry_authenticated_extraction(first_error, self.url, self.app_config):
                    raise
                self.status.emit(self.id, 'Authentication required; retrying once')
                retry_base = build_download_options(
                    self.profile_name, self.outtmpl, self.requested_height, self.metadata,
                    [self.progress_hook], [self.postprocessor_hook], self.speed_limit_bps,
                    self.request_context,
                )
                retry_options = authenticated_retry_options(retry_base, self.url, self.app_config)
                with yt_dlp.YoutubeDL(retry_options) as ydl:
                    self.ydl = ydl
                    info = ydl.extract_info(self.url, download=True)
            if isinstance(info, dict) and isinstance(info.get('url'), str):
                self.resolved_media_url = info['url']
            if self.cancelled or self.isInterruptionRequested():
                raise CancelException("Cancelled")
            self.current_stage = 'verification'
            self.status.emit(self.id, 'Verifying output')
            # Derive ownership from the actual per-download output template,
            # NEVER from the source video's extractor ID.
            suffix = f'-{str(self.id)[:8]}'
            output_tag = suffix if (self.id and self.outtmpl.endswith(f'{suffix}.%(ext)s')) else None
            final_path, probe = resolve_final_media(
                info, self.postprocessed_paths, self.save_dir, self.profile_name,
                preexisting, output_tag=output_tag,
            )
            if not profile_codecs_compatible(probe, self.profile_name):
                if self.cancelled or self.isInterruptionRequested():
                    raise CancelException("Cancelled")
                self.current_stage = 'conversion'
                self.status.emit(self.id, f'Converting to compatible {profile.extension.upper()}')
                final_path, probe = convert_incompatible_profile_output(
                    final_path, self.profile_name, self.save_dir, probe,
                    cancel_check=lambda: self.cancelled or self.isInterruptionRequested(),
                )
                if self.cancelled or self.isInterruptionRequested():
                    raise CancelException("Cancelled")
                final_path, probe = validate_final_media(final_path, self.save_dir, self.profile_name)
            if self.cancelled or self.isInterruptionRequested():
                raise CancelException("Cancelled")
            self.final_filename = str(final_path)
            self.final_probe = probe
            cleanup_verified_intermediates(self.temporary_paths, final_path, self.save_dir)
            size = final_path.stat().st_size
            if self.cancelled or self.isInterruptionRequested():
                raise CancelException("Cancelled")
            self.metrics.emit(self.id, size, size, 0.0, 0)
            self.size_updated.emit(self.id, final_path.name, self.format_size(size))
            if self.cancelled or self.isInterruptionRequested():
                raise CancelException("Cancelled")
            self.progress.emit(
                self.id, final_path.name, 100.0, format_bytes(size), format_bytes(size),
                '0 B/s', '00:00:00', 'Completed'
            )
            self.status.emit(self.id, 'Completed')
            self.finished.emit(self.id, True, '', self.final_filename)

        except PauseException:
            self.status.emit(self.id, 'Paused')
        except CancelException:
            self.status.emit(self.id, 'Cancelled')
            self.finished.emit(self.id, False, 'Cancelled', "")
        except Exception as e:
            summary = f"{self.current_stage.capitalize()} failure: {customer_extraction_error(e)}"
            self.status.emit(self.id, 'Failed')
            self.finished.emit(self.id, False, summary, "")
        finally:
            self.ydl = None

# ==========================================
# 4. STRATRUM DOWNLOAD STUDIO UI
# ==========================================
class DownloadFileInfoDialog(QDialog):
    def __init__(self, parent=None, prefill_url="", app_config=None, request_context=None):
        super().__init__(parent)
        self.app_config = app_config
        self.request_context = request_context or {}
        self.format_info = {}
        self.resolution_options = []
        self.fallback_from = None
        self.fetch_generation = 0
        self.fetchers = []
        self.setWindowTitle("Download File Info")
        self.setMinimumSize(760, 360)

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.addWidget(QLabel("URL"), 0, 0)
        self.url_edit = QLineEdit(prefill_url)
        grid.addWidget(self.url_edit, 0, 1, 1, 4)

        grid.addWidget(QLabel("Category"), 1, 0)
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Video", "Music"])
        grid.addWidget(self.category_combo, 1, 1)
        grid.addWidget(QLabel("Output profile"), 1, 2)
        self.ext_combo = QComboBox()
        self.ext_combo.addItems(list(OUTPUT_PROFILES))
        if app_config:
            self.ext_combo.setCurrentText(app_config.preferred_format)
        grid.addWidget(self.ext_combo, 1, 3, 1, 2)

        grid.addWidget(QLabel("Resolution"), 2, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItem("Best available", None)
        grid.addWidget(self.resolution_combo, 2, 1, 1, 4)

        grid.addWidget(QLabel("Save folder"), 3, 0)
        self.save_dir_combo = QComboBox()
        self.save_dir_combo.setEditable(True)
        downloads_dir = str((Path.home() / 'Downloads').resolve())
        recent = app_config.recent_folders if app_config else []
        self.save_dir_combo.addItems(recent or [downloads_dir])
        self.save_dir_combo.setCurrentText(recent[0] if recent else downloads_dir)
        grid.addWidget(self.save_dir_combo, 3, 1, 1, 3)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_dir)
        grid.addWidget(browse_btn, 3, 4)

        self.remember_cb = QCheckBox("Remember this output profile, resolution and folder")
        self.remember_cb.setChecked(True)
        grid.addWidget(self.remember_cb, 4, 1, 1, 4)
        layout.addLayout(grid)

        self.info_lbl = QLabel("Enter a URL to inspect available formats.")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet("color: #0078d7; font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.info_lbl)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.start_btn = QPushButton("Start Download")
        self.start_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.start_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.fetch_timer = QTimer(self)
        self.fetch_timer.setSingleShot(True)
        self.fetch_timer.setInterval(450)
        self.fetch_timer.timeout.connect(self.fetch_formats)
        self.url_edit.textChanged.connect(self.schedule_format_fetch)
        self.ext_combo.currentTextChanged.connect(self.on_ext_changed)
        self.resolution_combo.currentIndexChanged.connect(self.on_resolution_changed)
        self.on_ext_changed(self.ext_combo.currentText())
        if prefill_url:
            self.schedule_format_fetch()

    def on_ext_changed(self, text):
        profile = output_profile(text)
        self.category_combo.setCurrentText("Music" if profile.media_kind == 'audio' else "Video")
        self.resolution_combo.setEnabled(profile.media_kind == 'video' and bool(self.resolution_options))
        self.update_resolution_summary()

    def schedule_format_fetch(self):
        self.fetch_generation += 1
        self.fetch_timer.start()

    def fetch_formats(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        generation = self.fetch_generation
        self.info_lbl.setText("Resolving formats...")
        self.start_btn.setEnabled(False)
        fetcher = FormatFetcherThread(url, self.request_context_for(url), self.app_config)
        self.fetchers.append(fetcher)
        fetcher.formats_ready.connect(lambda info, gen=generation: self.on_formats_ready(gen, info))
        fetcher.error_occurred.connect(lambda error, gen=generation: self.on_fetch_error(gen, error))
        fetcher.finished.connect(lambda worker=fetcher: self.fetchers.remove(worker) if worker in self.fetchers else None)
        fetcher.start()

    def request_context_for(self, url):
        return self.request_context if self.request_context.get('operational_url') == url else {}

    def on_formats_ready(self, generation, info):
        if generation != self.fetch_generation:
            return
        self.format_info = info
        self.resolution_options = available_resolution_options(info)
        self.resolution_combo.blockSignals(True)
        self.resolution_combo.clear()
        if self.resolution_options:
            best = choose_resolution(self.resolution_options)
            self.resolution_combo.addItem(f"Best available — {format_resolution_detail(best)}", None)
            for option in self.resolution_options:
                self.resolution_combo.addItem(format_resolution_detail(option), option['height'])
            preferred = self.app_config.preferred_resolution if self.app_config else None
            if preferred is not None:
                actual = choose_resolution(self.resolution_options, preferred)
                index = self.resolution_combo.findData(actual['height'])
                if index >= 0:
                    self.resolution_combo.setCurrentIndex(index)
                self.fallback_from = preferred if actual['height'] != preferred else None
        else:
            self.resolution_combo.addItem("No video resolution metadata available", None)
        self.resolution_combo.blockSignals(False)
        self.on_ext_changed(self.ext_combo.currentText())
        self.start_btn.setEnabled(True)

    def on_fetch_error(self, generation, error_msg):
        if generation != self.fetch_generation:
            return
        self.format_info = {}
        self.resolution_options = []
        self.resolution_combo.clear()
        self.resolution_combo.addItem("Format metadata unavailable", None)
        self.resolution_combo.setEnabled(False)
        self.info_lbl.setText(f"Format inspection failed: {clean_error_summary(error_msg)}")
        self.start_btn.setEnabled(True)

    def update_resolution_summary(self):
        profile = output_profile(self.ext_combo.currentText())
        if profile.media_kind == 'audio':
            self.info_lbl.setText("Audio-only profile — resolution selection disabled")
            return
        requested = self.resolution_combo.currentData()
        selected = choose_resolution(self.resolution_options, requested)
        if selected:
            if self.fallback_from:
                prefix = f"Requested {self.fallback_from}p unavailable; actual selection: "
            else:
                fallback = requested is not None and selected['height'] != requested
                prefix = "Actual fallback: " if fallback else "Selected: "
            self.info_lbl.setText(prefix + format_resolution_detail(selected))

    def on_resolution_changed(self):
        self.fallback_from = None
        self.update_resolution_summary()

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if directory:
            self.save_dir_combo.setCurrentText(directory)
            if self.app_config:
                self.app_config.add_recent_folder(directory)

    def get_data(self):
        save_dir = self.save_dir_combo.currentText().strip()
        if self.app_config and self.remember_cb.isChecked():
            self.app_config.add_recent_folder(save_dir)
            self.app_config.preferred_format = self.ext_combo.currentText()
            self.app_config.preferred_resolution = self.resolution_combo.currentData()
            self.app_config.persist()
        return (
            self.url_edit.text().strip(), save_dir, self.resolution_combo.currentData(),
            self.ext_combo.currentText(), self.format_info,
        )


class DownloadProgressPopup(QDialog):
    pause_requested = pyqtSignal(str)
    resume_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal(str, bool)
    speed_limit_changed = pyqtSignal(str, int)

    def __init__(self, filename, url, parent=None, job_id='', app_config=None):
        super().__init__(parent)
        self.job_id = job_id
        self.app_config = app_config
        self.job_state = JobState.CONNECTING.value
        self.setWindowTitle(f"0% {filename}")
        self.setFixedSize(500, 280) # Closed details state
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.details_open = False
        self.filename = filename
        self.lifecycle_generation = 0
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)

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

        speed_layout = QFormLayout()
        self.speed_unit_combo = QComboBox()
        self.speed_unit_combo.addItems(["Unlimited", "KB/s", "MB/s"])
        self.speed_value_spin = QSpinBox()
        self.speed_value_spin.setRange(1, 100000)
        self.speed_value_spin.setValue(1024)
        apply_limit = QPushButton("Apply to this download")
        apply_limit.clicked.connect(self.apply_speed_limit)
        self.active_limit_lbl = QLabel("Unlimited")
        if app_config and app_config.speed_limit_bps:
            if app_config.speed_limit_bps % (1024 * 1024) == 0:
                self.speed_unit_combo.setCurrentText("MB/s"); self.speed_value_spin.setValue(app_config.speed_limit_bps // (1024 * 1024))
            else:
                self.speed_unit_combo.setCurrentText("KB/s"); self.speed_value_spin.setValue(max(1, app_config.speed_limit_bps // 1024))
            self.active_limit_lbl.setText(f"{self.speed_value_spin.value()} {self.speed_unit_combo.currentText()}")
        speed_layout.addRow("Limit", self.speed_unit_combo)
        speed_layout.addRow("Value", self.speed_value_spin)
        speed_layout.addRow(apply_limit)
        speed_layout.addRow("Active", self.active_limit_lbl)
        speed_tab.setLayout(speed_layout)

        completion_layout = QFormLayout()
        self.completion_combo = QComboBox()
        for label, value in (
            ("Keep window open", "keep_open"),
            ("Close progress window", "close"),
            ("Open containing folder", "open_folder"),
            ("Play/open safe media", "open_file"),
            ("Convert to MP3", "convert_mp3"),
            ("Convert to WAV", "convert_wav"),
            ("Convert to MP4", "convert_mp4"),
            ("Convert to M4A", "convert_m4a"),
        ):
            self.completion_combo.addItem(label, value)
        if app_config:
            index = self.completion_combo.findData(app_config.completion_action)
            if index >= 0:
                self.completion_combo.setCurrentIndex(index)
        self.exit_when_idle_cb = QCheckBox("Exit application after all jobs finish")
        self.keep_completed_open_cb = QCheckBox("Keep completed download window open")
        self.keep_completed_open_cb.setChecked(bool(app_config and app_config.keep_completed_window_open))
        self.keep_completed_open_cb.toggled.connect(self.persist_keep_open_preference)
        completion_layout.addRow("On completion", self.completion_combo)
        completion_layout.addRow(self.keep_completed_open_cb)
        completion_layout.addRow(self.exit_when_idle_cb)
        options_tab.setLayout(completion_layout)

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
        self.pause_btn.clicked.connect(self.request_pause_resume)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.request_cancel)

        btn_layout.addWidget(self.details_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

        # Details Panel
        self.details_widget = QWidget()
        det_layout = QVBoxLayout()
        det_layout.addWidget(QLabel("Job details and safe diagnostics"))
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlainText("No connection details are available yet.")
        det_layout.addWidget(self.details_text)
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

    def update_stats(self, filename, percent, downloaded, total, speed, eta, status):
        if filename and filename != "Connecting...":
            self.filename = filename
        self.setWindowTitle(f"{int(percent)}% {self.filename}")
        self.progress_bar.setValue(int(percent))
        self.speed_lbl.setText(speed)
        self.time_lbl.setText(eta)
        self.status_lbl.setText(status)
        self.set_job_state(status.lower())
        self.downloaded_lbl.setText(f"{format_transfer_size(downloaded, total)} ({percent:.1f}%)")
        if total != "N/A":
            self.size_lbl.setText(total)

    def set_job_state(self, state):
        normalized = str(state).lower().replace(' ', '')
        if normalized != JobState.COMPLETED.value:
            self.cancel_auto_close()
        self.job_state = normalized
        if normalized == JobState.PAUSED.value:
            self.pause_btn.setText("Resume")
            self.pause_btn.setEnabled(True)
        elif normalized in {JobState.DOWNLOADING.value, JobState.CONNECTING.value, JobState.RESOLVING.value, JobState.CONVERTING.value, 'starting'}:
            self.pause_btn.setText("Pause")
            self.pause_btn.setEnabled(True)
        else:
            self.pause_btn.setEnabled(False)

    def persist_keep_open_preference(self, checked):
        if self.app_config:
            self.app_config.keep_completed_window_open = bool(checked)
            self.app_config.persist()

    def cancel_auto_close(self):
        self.lifecycle_generation += 1
        self.auto_close_timer.stop()

    def schedule_verified_close(self, callback, delay_ms=1500):
        self.cancel_auto_close()
        if self.keep_completed_open_cb.isChecked():
            return False
        generation = self.lifecycle_generation
        self.auto_close_timer.timeout.connect(
            lambda: callback() if self.lifecycle_generation == generation and self.job_state == JobState.COMPLETED.value else None
        )
        self.auto_close_timer.start(delay_ms)
        return True

    def request_pause_resume(self):
        if self.job_state == JobState.PAUSED.value:
            self.resume_requested.emit(self.job_id)
        else:
            self.pause_requested.emit(self.job_id)

    def request_cancel(self):
        if self.job_state in {JobState.CONVERTING.value, JobState.PAUSED.value, 'starting'}:
            if QMessageBox.question(self, "Cancel Conversion", "Cancel only this conversion? The source and previous valid outputs will be preserved.") == QMessageBox.StandardButton.Yes:
                self.cancel_requested.emit(self.job_id, False)
            return
        question = QMessageBox(self)
        question.setWindowTitle("Cancel Download")
        question.setText("Cancel this download and choose what happens to partial data.")
        keep_button = question.addButton("Keep Partial Data", QMessageBox.ButtonRole.AcceptRole)
        remove_button = question.addButton("Remove Partial Data", QMessageBox.ButtonRole.DestructiveRole)
        question.addButton("Continue Download", QMessageBox.ButtonRole.RejectRole)
        question.exec()
        if question.clickedButton() == keep_button:
            self.cancel_requested.emit(self.job_id, False)
        elif question.clickedButton() == remove_button:
            self.cancel_requested.emit(self.job_id, True)

    def apply_speed_limit(self):
        unit = self.speed_unit_combo.currentText()
        if unit == "Unlimited":
            limit = 0
            label = "Unlimited"
        else:
            multiplier = 1024 if unit == "KB/s" else 1024 * 1024
            limit = self.speed_value_spin.value() * multiplier
            label = f"{self.speed_value_spin.value()} {unit}"
        self.active_limit_lbl.setText(label)
        self.speed_limit_changed.emit(self.job_id, limit)

    def completion_action(self):
        return self.completion_combo.currentData()

    def set_details(self, text):
        self.details_text.setPlainText(str(text))

# ==========================================
# 5. MAIN APP: STRATRUM DOWNLOAD STUDIO
# ==========================================
class LocalConverterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Local Media Converter')
        self.resize(900, 560)
        self.setAcceptDrops(True)
        self.entries = []
        self.pending_jobs = []
        self.active_job_id = None
        self.conversion_controller = ConversionJobController(self)
        self.conversion_controller.progress.connect(self.on_progress)
        self.conversion_controller.finished.connect(self.on_finished)

        layout = QVBoxLayout(self)
        intro = QLabel('Drop local audio/video files here, or select one or more files. FFprobe determines real streams and container support.')
        intro.setWordWrap(True); layout.addWidget(intro)
        top = QHBoxLayout()
        add_button = QPushButton('Add Files'); add_button.clicked.connect(self.select_files); top.addWidget(add_button)
        self.target_combo = QComboBox(); self.target_combo.addItems(list(OUTPUT_PROFILES)); top.addWidget(QLabel('Target:')); top.addWidget(self.target_combo)
        self.apply_all_button = QPushButton('Apply format to all'); self.apply_all_button.clicked.connect(self.apply_format_to_all); top.addWidget(self.apply_all_button)
        self.output_edit = QLineEdit(); self.output_edit.setPlaceholderText('Output folder (defaults to each source folder)'); top.addWidget(self.output_edit, 1)
        browse_button = QPushButton('Browse'); browse_button.clicked.connect(self.select_output_folder); top.addWidget(browse_button)
        self.overwrite_combo = QComboBox(); self.overwrite_combo.addItem('Unique name', 'unique'); self.overwrite_combo.addItem('Ask before replace', 'ask'); self.overwrite_combo.addItem('Skip existing', 'skip')
        top.addWidget(self.overwrite_combo); layout.addLayout(top)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Source', 'Detected media', 'Target', 'Progress', 'State', 'Output'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.start_button = QPushButton('Start'); self.start_button.clicked.connect(self.start_conversions); buttons.addWidget(self.start_button)
        self.cancel_button = QPushButton('Cancel'); self.cancel_button.clicked.connect(self.cancel_active); self.cancel_button.setEnabled(False); buttons.addWidget(self.cancel_button)
        self.pause_button = QPushButton('Pause'); self.pause_button.clicked.connect(self.pause_active); buttons.addWidget(self.pause_button)
        self.resume_button = QPushButton('Resume'); self.resume_button.clicked.connect(self.resume_active); buttons.addWidget(self.resume_button)
        self.remove_button = QPushButton('Remove Selected'); self.remove_button.clicked.connect(self.remove_selected); buttons.addWidget(self.remove_button)
        self.clear_button = QPushButton('Clear List'); self.clear_button.clicked.connect(self.clear_list); buttons.addWidget(self.clear_button)
        self.open_output_button = QPushButton('Open Output'); self.open_output_button.clicked.connect(self.open_selected_output); buttons.addWidget(self.open_output_button)
        self.open_folder_button = QPushButton('Open Folder'); self.open_folder_button.clicked.connect(self.open_selected_folder); buttons.addWidget(self.open_folder_button)
        buttons.addStretch(1); close_button = QPushButton('Close'); close_button.clicked.connect(self.close); buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.target_combo.currentTextChanged.connect(self.refresh_target_availability)
        self.table.itemSelectionChanged.connect(self.update_button_states)
        self.update_button_states()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Select local media files', '', 'Media files (*.*)')
        self.add_files(paths)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select output folder', self.output_edit.text())
        if folder: self.output_edit.setText(folder)

    def add_files(self, paths):
        known = {entry['source'] for entry in self.entries}
        for raw_path in paths:
            try:
                source = str(Path(raw_path).resolve(strict=True))
                if source in known or not Path(source).is_file(): continue
                probe = probe_media_file(source); summary = media_summary(probe)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                QMessageBox.warning(self, 'Unsupported Media', f'{Path(raw_path).name}: {clean_error_summary(exc)}')
                continue
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(source))
            detected = f"{summary['container']} | {summary['codecs']} | {summary['resolution']} | {format_eta(summary['duration'])}"
            self.table.setItem(row, 1, QTableWidgetItem(detected))
            target_selector = QComboBox(); target_selector.addItems(list(OUTPUT_PROFILES)); target_selector.setCurrentText(self.target_combo.currentText())
            for target_index, target_name in enumerate(OUTPUT_PROFILES):
                capability = conversion_target_capabilities(probe)[target_name]
                target_item = target_selector.model().item(target_index)
                if target_item:
                    target_item.setEnabled(capability['enabled']); target_item.setToolTip(capability['reason'])
            self.table.setCellWidget(row, 2, target_selector)
            bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(0); bar.setFormat('Queued 0%'); self.table.setCellWidget(row, 3, bar)
            self.table.setItem(row, 4, QTableWidgetItem('Ready')); self.table.setItem(row, 5, QTableWidgetItem(''))
            entry = {'job_id': uuid.uuid4().hex, 'source': source, 'probe': probe, 'row': row, 'output': '', 'target': target_selector.currentText(), 'state': 'ready'}
            target_selector.currentTextChanged.connect(lambda value, item=entry: self.set_entry_target(item, value))
            self.entries.append(entry); known.add(source)
        self.refresh_target_availability()
        self.update_button_states()

    def set_entry_target(self, entry, target):
        if entry not in self.entries or entry.get('state') not in {'ready', 'queued', 'failed', 'cancelled'}:
            return False
        capability = conversion_target_capabilities(entry['probe']).get(target, {})
        if not capability.get('enabled'):
            return False
        entry['target'] = target
        return True

    def apply_format_to_all(self):
        target = self.target_combo.currentText()
        for entry in self.entries:
            if self.set_entry_target(entry, target):
                selector = self.table.cellWidget(entry['row'], 2)
                if selector: selector.setCurrentText(target)

    def refresh_target_availability(self):
        model = self.target_combo.model()
        for index, name in enumerate(OUTPUT_PROFILES):
            reasons = []
            enabled = True
            for entry in self.entries:
                capability = conversion_target_capabilities(entry['probe'])[name]
                if not capability['enabled']:
                    enabled = False; reasons.append(capability['reason'])
            item = model.item(index)
            if item:
                item.setEnabled(enabled)
                item.setToolTip(reasons[0] if reasons else 'Available; output is always a new re-encoded file.')
        self.apply_all_button.setEnabled(bool(self.entries))

    def _confirm_replace(self, path):
        result = QMessageBox.question(self, 'Replace Existing Output', f'Replace existing output?\n\n{path}', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return result == QMessageBox.StandardButton.Yes

    def start_conversions(self):
        if self.active_job_id or not self.entries: return
        output_dir = self.output_edit.text().strip() or None
        behavior = self.overwrite_combo.currentData()
        self.pending_jobs = []
        reserved = set()
        for entry in self.entries:
            if entry.get('state') not in {'ready', 'failed', 'cancelled'}:
                continue
            try:
                target = entry['target']
                destination = conversion_destination_for_behavior(entry['source'], target, output_dir, behavior, self._confirm_replace, reserved)
                plan = build_conversion_plan(entry['source'], target, output_dir, entry['probe'], destination)
                self.pending_jobs.append((entry, plan))
                reserved.add(str(plan.destination.resolve()))
                entry['state'] = 'queued'
                self.table.item(entry['row'], 4).setText('Queued')
            except (OSError, ValueError, PermissionError, FileExistsError) as exc:
                entry['state'] = 'failed'
                self.table.item(entry['row'], 4).setText(clean_error_summary(exc))
        self._start_next(); self.update_button_states()

    def _start_next(self):
        if not self.pending_jobs:
            self.active_job_id = None; self.update_button_states(); return
        entry, plan = self.pending_jobs.pop(0)
        self.active_job_id = entry['job_id']; entry['state'] = 'starting'
        self.table.item(entry['row'], 4).setText('Starting')
        self.conversion_controller.start(entry['job_id'], entry['source'], plan.target_name, plan.destination.parent, plan.destination)
        self.update_button_states()

    def on_progress(self, job_id, snapshot):
        entry = next((item for item in self.entries if item['job_id'] == job_id), None)
        if not entry: return
        entry['state'] = snapshot.get('state', 'converting')
        bar = self.table.cellWidget(entry['row'], 3); percent = float(snapshot.get('percent') or 0)
        bar.setValue(int(percent)); eta = format_eta(snapshot['eta']) if snapshot.get('eta') is not None else 'calculating'
        if entry['state'] == 'paused':
            bar.setFormat(f"Paused {percent:.0f}%")
        else:
            bar.setFormat(f"{percent:.1f}% | ETA {eta}")
        self.table.item(entry['row'], 4).setText(f"{snapshot.get('state', 'converting').capitalize()} | elapsed {format_eta(snapshot.get('elapsed') or 0)}")
        self.table.item(entry['row'], 5).setText(snapshot.get('destination', ''))

    def on_finished(self, job_id, success, message, output_path):
        entry = next((item for item in self.entries if item['job_id'] == job_id), None)
        if entry:
            bar = self.table.cellWidget(entry['row'], 3)
            if success:
                entry['state'] = 'completed'
                entry['output'] = output_path; bar.setValue(100); bar.setFormat('Completed 100%')
                self.table.item(entry['row'], 4).setText('Completed'); self.table.item(entry['row'], 5).setText(output_path)
            else:
                entry['state'] = 'cancelled' if 'cancelled' in message.lower() else 'failed'
                bar.setFormat('Cancelled' if 'cancelled' in message.lower() else 'Failed')
                self.table.item(entry['row'], 4).setText(clean_error_summary(message))
        if self.active_job_id == job_id: self.active_job_id = None
        self.update_button_states(); QTimer.singleShot(0, self._start_next)

    def cancel_active(self):
        self.pending_jobs.clear()
        if self.active_job_id: self.conversion_controller.cancel(self.active_job_id)
        self.update_button_states()

    def pause_active(self):
        if self.active_job_id and not self.conversion_controller.pause(self.active_job_id):
            QMessageBox.warning(self, 'Pause Failed', 'The active conversion could not be paused.')
        self.update_button_states()

    def resume_active(self):
        if self.active_job_id and not self.conversion_controller.resume(self.active_job_id):
            QMessageBox.warning(self, 'Resume Failed', 'The active conversion could not be resumed.')
        self.update_button_states()

    def _remove_entry(self, entry):
        row = entry['row']; self.table.removeRow(row); self.entries.remove(entry)
        for other in self.entries:
            if other['row'] > row: other['row'] -= 1

    def remove_selected(self):
        entry = self._selected_entry()
        if not entry: return False
        self.pending_jobs = [(item, plan) for item, plan in self.pending_jobs if item is not entry]
        if entry['job_id'] == self.active_job_id:
            if not self.conversion_controller.cancel(entry['job_id'], remove=True):
                self.table.item(entry['row'], 4).setText('Unable to confirm conversion stopped')
                self.update_button_states(); return False
            self.active_job_id = None
        self._remove_entry(entry); self.update_button_states(); QTimer.singleShot(0, self._start_next); return True

    def clear_list(self):
        if self.active_job_id:
            active = next((entry for entry in self.entries if entry['job_id'] == self.active_job_id), None)
            if active and not self.conversion_controller.cancel(active['job_id'], remove=True):
                self.table.item(active['row'], 4).setText('Unable to confirm conversion stopped')
                self.update_button_states(); return False
            self.active_job_id = None
        self.pending_jobs.clear()
        self.table.setRowCount(0); self.entries.clear(); self.update_button_states(); return True

    def update_button_states(self):
        selected = self._selected_entry()
        state = self.conversion_controller.state(self.active_job_id) if self.active_job_id else None
        can_start = any(entry.get('state') in {'ready', 'failed', 'cancelled'} for entry in self.entries)
        self.start_button.setEnabled(can_start and not self.active_job_id)
        self.cancel_button.setEnabled(state in {'starting', 'converting', 'paused'})
        self.pause_button.setEnabled(state in {'starting', 'converting'})
        self.resume_button.setEnabled(state == 'paused')
        self.remove_button.setEnabled(selected is not None)
        self.clear_button.setEnabled(bool(self.entries))
        has_output = bool(selected and selected.get('output') and Path(selected['output']).is_file())
        self.open_output_button.setEnabled(has_output)
        self.open_folder_button.setEnabled(selected is not None)

    def _selected_entry(self):
        rows = self.table.selectionModel().selectedRows()
        return next((entry for entry in self.entries if rows and entry['row'] == rows[0].row()), None)

    def open_selected_output(self):
        entry = self._selected_entry()
        if entry and entry.get('output') and Path(entry['output']).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(entry['output']))

    def open_selected_folder(self):
        entry = self._selected_entry()
        if entry:
            folder = Path(entry.get('output') or entry['source']).parent
            if folder.is_dir(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event):
        if self.active_job_id and not self.conversion_controller.cancel(self.active_job_id, remove=True):
            QMessageBox.warning(self, 'Close Failed', 'The converter remains open because the active process could not be confirmed stopped.')
            event.ignore(); return
        event.accept()


class BrowserIntegrationDialog(QDialog):
    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.app_config = app_config
        self.setWindowTitle("Browser Integration")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Copy the local authentication token into the Chrome, Edge, or Firefox extension. "
            "The token is masked and must never be shared or logged."
        ))
        token_field = QLineEdit(app_config.auth_token)
        token_field.setReadOnly(True)
        token_field.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(token_field)
        self.default_action_combo = QComboBox()
        self.default_action_combo.addItem("Quick Download", "quick_download")
        self.default_action_combo.addItem("Download with Options", "download_with_options")
        self.default_action_combo.setCurrentIndex(max(0, self.default_action_combo.findData(app_config.primary_browser_action)))
        self.default_action_combo.currentIndexChanged.connect(self.persist_default_action)
        action_row = QFormLayout()
        action_row.addRow("Default browser action", self.default_action_combo)
        self.auth_retry_check = QCheckBox("Retry supported sites with a browser profile after an anonymous authentication failure")
        self.auth_retry_check.setChecked(app_config.authenticated_retry_enabled)
        action_row.addRow("Authenticated retry", self.auth_retry_check)
        self.auth_browser_combo = QComboBox()
        for browser in ("chrome", "edge", "firefox"):
            self.auth_browser_combo.addItem(browser.title(), browser)
        self.auth_browser_combo.setCurrentIndex(max(0, self.auth_browser_combo.findData(app_config.authenticated_retry_browser)))
        action_row.addRow("Browser", self.auth_browser_combo)
        self.auth_profile_edit = QLineEdit(app_config.authenticated_retry_profile)
        self.auth_profile_edit.setPlaceholderText("Default profile, profile name, or local profile path")
        action_row.addRow("Profile", self.auth_profile_edit)
        layout.addLayout(action_row)
        self.auth_retry_check.toggled.connect(self.persist_authenticated_retry)
        self.auth_browser_combo.currentIndexChanged.connect(self.persist_authenticated_retry)
        self.auth_profile_edit.editingFinished.connect(self.persist_authenticated_retry)
        self.auth_retry_check.toggled.connect(self.update_authenticated_controls)
        self.update_authenticated_controls()

        actions = QHBoxLayout()
        copy_button = QPushButton("Copy Token")
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(app_config.auth_token))
        actions.addWidget(copy_button)
        guide_button = QPushButton("Open Extension Guide")
        guide_button.clicked.connect(self.open_guide)
        actions.addWidget(guide_button)
        reset_button = QPushButton("Reset All Pairings")
        reset_button.clicked.connect(self.reset_all_pairings)
        actions.addWidget(reset_button)
        clear_folders_button = QPushButton("Clear Recent Folders")
        clear_folders_button.clicked.connect(self.clear_recent_folders)
        actions.addWidget(clear_folders_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        layout.addWidget(QLabel(f"Paired browser origins (maximum {MAX_PAIRED_ORIGINS}):"))
        pairing_actions = QHBoxLayout()
        self.origin_combo = QComboBox()
        pairing_actions.addWidget(self.origin_combo)
        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_origin)
        pairing_actions.addWidget(remove_button)
        layout.addLayout(pairing_actions)
        self.pairing_label = QLabel()
        layout.addWidget(self.pairing_label)
        self.refresh_origins()

    def persist_default_action(self):
        selected = self.default_action_combo.currentData()
        if selected in DESKTOP_BROWSER_ACTIONS and selected != self.app_config.primary_browser_action:
            self.app_config.primary_browser_action = selected
            self.app_config.persist()

    def update_authenticated_controls(self):
        enabled = self.auth_retry_check.isChecked()
        self.auth_browser_combo.setEnabled(enabled)
        self.auth_profile_edit.setEnabled(enabled)

    def persist_authenticated_retry(self):
        browser = self.auth_browser_combo.currentData()
        profile = normalize_browser_profile(self.auth_profile_edit.text())
        if browser not in AUTHENTICATED_BROWSERS:
            browser = 'chrome'
        self.app_config.authenticated_retry_enabled = self.auth_retry_check.isChecked()
        self.app_config.authenticated_retry_browser = browser
        self.app_config.authenticated_retry_profile = profile
        self.app_config.persist()

    def refresh_origins(self):
        self.origin_combo.clear()
        self.origin_combo.addItems(self.app_config.allowed_origins)
        count = len(self.app_config.allowed_origins)
        self.pairing_label.setText(
            f"{count} browser origin{'s' if count != 1 else ''} paired."
            if count else "No browser extension is currently paired."
        )

    def open_guide(self):
        try:
            if not open_browser_extension_guide():
                raise OSError("The operating system did not open the guide")
        except (OSError, ValueError):
            QMessageBox.warning(self, "Guide Unavailable", "The browser extension README could not be opened.")

    def remove_selected_origin(self):
        origin = self.origin_combo.currentText()
        if not origin:
            return
        try:
            self.app_config.remove_origin(origin)
        except OSError:
            QMessageBox.warning(self, "Removal Failed", "The browser pairing could not be persisted.")
            return
        self.refresh_origins()

    def reset_all_pairings(self):
        answer = QMessageBox.question(
            self,
            "Reset All Browser Pairings",
            "Reset every paired browser extension? Each browser must send a new fully valid authenticated request to pair again.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.app_config.reset_all_origins()
        except OSError:
            QMessageBox.warning(self, "Reset Failed", "The browser pairings could not be persisted.")
            return
        self.refresh_origins()

    def clear_recent_folders(self):
        self.app_config.clear_recent_folders()
        QMessageBox.information(self, "Recent Folders", "Recent save folders were cleared.")


class StratrumDownloadStudio(QMainWindow):
    def __init__(self, app_config):
        super().__init__()
        self.app_config = app_config
        self.download_manager = DownloadManager(app_config)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(760, 480)
        width, height = (app_config.window_size + [1150, 680])[:2]
        self.setGeometry(100, 100, max(800, int(width)), max(520, int(height)))
        self.downloads = []; self.popups = {}
        self.conversion_controller = ConversionJobController(self)
        self.conversion_controller.progress.connect(self.conversion_progress)
        self.conversion_controller.finished.connect(self.conversion_done)
        self.conversion_controller.state_changed.connect(lambda *_: self.update_action_capabilities())
        self.converters = self.conversion_controller.jobs
        self.progress_snapshots = {}
        self.last_progress_paint = {}
        self.history_writer = None
        self.init_ui()
        self.init_tray_icon()
        self.load_downloads_from_file()
        self.load_recovered_queue_jobs()
        self.download_manager.job_changed.connect(lambda *_: self.refresh_dashboard())
        self.refresh_dashboard()
        self.init_server()

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = Path(__file__).resolve().parent / 'stratum-download-studio.ico'
        icon = QIcon(str(icon_path)) if icon_path.is_file() else QIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)

        tray_menu = QMenu()
        tray_menu.addAction(f"Show {APP_NAME}", self.show_normal)
        tray_menu.addSeparator()
        tray_menu.addAction("Exit", self.force_quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick: self.show_normal()

    def show_normal(self, request_foreground=False):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.raise_()
        if request_foreground:
            self.request_foreground(self)

    def request_foreground(self, widget):
        widget.show(); widget.raise_(); widget.activateWindow(); widget.setFocus()
        if sys.platform != 'win32':
            return True
        try:
            import ctypes
            hwnd = int(widget.winId())
            if ctypes.windll.user32.SetForegroundWindow(hwnd):
                return True
            class FLASHWINFO(ctypes.Structure):
                _fields_ = [('cbSize', ctypes.c_uint), ('hwnd', ctypes.c_void_p), ('dwFlags', ctypes.c_uint),
                            ('uCount', ctypes.c_uint), ('dwTimeout', ctypes.c_uint)]
            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x00000003, 2, 0)
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
        except (AttributeError, OSError, TypeError, ValueError):
            return False
        return False

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and self.windowState() & Qt.WindowState.WindowMinimized:
            event.accept(); self.hide()
            self.tray_icon.showMessage(APP_NAME, "Running in background.", QSystemTrayIcon.MessageIcon.Information, 1500)
            return
        super().changeEvent(event)

    def closeEvent(self, event):
        event.ignore(); self.hide()

    def force_quit(self):
        # Keep resumable HTTP partials intact instead of destroying a live QThread.
        for record in self.downloads:
            worker = record.get('thread')
            if isinstance(worker, FileDownloadThread) and worker.isRunning():
                worker.paused = True
                worker.wait(2500)
                if worker.isRunning():
                    QMessageBox.warning(self, "File Download", "A file connection is still stopping. Your partial download is preserved; please use Exit again after it stops.")
                    return
        self.persist_ui_preferences()
        self.save_downloads_to_file(wait=True)
        self.server_thread.stop(); self.server_thread.wait(); QApplication.quit()

    def save_downloads_to_file(self, wait=False):
        save_data = []
        for row in range(self.table.rowCount()):
            bar = self.table.cellWidget(row, 3)
            status = bar.text() if bar else self.table.item(row, 3).text() if self.table.item(row, 3) else "Completed"
            if d_info := next((d for d in self.downloads if d['row'] == row), None):
                job = d_info.get('job')
                save_data.append({
                    'filename': self.table.item(row, 0).text(),
                    'size': self.table.item(row, 2).text() if self.table.item(row, 2) else "",
                    'status': status,
                    'eta': self.table.item(row, 4).text() if self.table.item(row, 4) else "",
                    'speed': self.table.item(row, 5).text() if self.table.item(row, 5) else "",
                    'date': self.table.item(row, 6).text() if self.table.item(row, 6) else "",
                    'url': d_info.get('url', ''),
                    'id': d_info['id'], 'outtmpl': d_info['outtmpl'], 'save_dir': d_info.get('save_dir', ''),
                    'format': d_info['format'], 'ext': d_info['ext'], 'final_path': d_info.get('final_path', ''),
                    'converted_output_path': d_info.get('converted_output_path', ''),
                    'requested_resolution': d_info.get('requested_resolution'),
                    'state': job.state if job else d_info.get('state', JobState.QUEUED.value),
                    'job': job.to_dict() if job else None,
                })
        def write_history():
            try:
                atomic_write_json(self.app_config.history_path, save_data)
            except Exception:
                pass
        self.history_writer = threading.Thread(target=write_history, name='StratrumHistoryWriter', daemon=False)
        self.history_writer.start()
        if wait:
            self.history_writer.join(timeout=5)

    def load_downloads_from_file(self):
        history_file = self.app_config.history_path
        if not history_file.exists(): return
        if history_file.stat().st_size > 2 * 1024 * 1024:
            os.replace(history_file, str(history_file) + ".oversize")
            return
        try:
            with history_file.open('r', encoding='utf-8') as f: save_data = json.load(f)
            for item in save_data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                filename_item = QTableWidgetItem(item.get('filename', '')); filename_item.setToolTip(item.get('filename', ''))
                self.table.setItem(row, 0, filename_item)
                self.table.setItem(row, 1, QTableWidgetItem(""))
                self.table.setItem(row, 2, QTableWidgetItem(item.get('size', '')))

                pb = QProgressBar(); pb.setRange(0, 100); status = item.get('status', '')
                if "Downloading" in status or "Paused" in status: pb.setValue(0); pb.setFormat("Paused")
                else: pb.setValue(100); pb.setFormat(status)

                self.table.setCellWidget(row, 3, pb)
                self.table.setItem(row, 4, QTableWidgetItem(item.get('eta', '')))
                self.table.setItem(row, 5, QTableWidgetItem(item.get('speed', '')))
                self.table.setItem(row, 6, QTableWidgetItem(item.get('date', '')))
                source_display = sanitize_source_url(item.get('url', ''))
                source_item = QTableWidgetItem(source_display); source_item.setToolTip(source_display)
                self.table.setItem(row, 7, source_item)

                stored_job = item.get('job') if isinstance(item.get('job'), dict) else None
                if stored_job:
                    job = DownloadJob.from_dict(stored_job)
                else:
                    job = DownloadJob(
                        job_id=item.get('id', uuid.uuid4().hex), source_url=item.get('url', ''),
                        save_dir=item.get('save_dir', str(Path(item.get('outtmpl', '.')).parent)),
                        requested_format=item.get('ext', 'MP4'), requested_resolution=item.get('requested_resolution'),
                        final_output_path=item.get('final_path', ''), state=item.get('state', JobState.COMPLETED.value),
                    )
                if job.job_id in self.download_manager.jobs:
                    job = self.download_manager.jobs[job.job_id]
                else:
                    self.download_manager.add_job(job)
                pb.setValue(100 if job.state == JobState.COMPLETED.value else 0)
                pb.setFormat("Completed 100%" if job.state == JobState.COMPLETED.value else job.state.capitalize())
                self.downloads.append({
                    'id': job.job_id, 'url': item.get('url', ''), 'outtmpl': item.get('outtmpl', ''),
                    'save_dir': item.get('save_dir', str(Path(item.get('outtmpl', '.')).parent)),
                    'format': item.get('format', ''), 'ext': item.get('ext', ''), 'thread': None, 'row': row,
                    'final_path': item.get('final_path', ''),
                    'converted_output_path': item.get('converted_output_path', ''),
                    'requested_resolution': item.get('requested_resolution'), 'job': job,
                })
        except json.JSONDecodeError:
            print("History file is corrupted. Starting fresh.")
            os.replace(history_file, str(history_file) + ".corrupt")
        except Exception as e:
            print(f"Failed to load history: {e}")

    def load_recovered_queue_jobs(self):
        known = {record['id'] for record in self.downloads}
        for job_id in self.download_manager.queue:
            if job_id in known:
                continue
            job = self.download_manager.jobs[job_id]
            row = self.table.rowCount(); self.table.insertRow(row)
            filename = Path(job.final_output_path).name if job.final_output_path else "Recovered incomplete job"
            filename_item = QTableWidgetItem(filename); filename_item.setToolTip(filename); self.table.setItem(row, 0, filename_item)
            self.table.setItem(row, 1, QTableWidgetItem(str(job.priority)))
            self.table.setItem(row, 2, QTableWidgetItem(format_transfer_size(format_bytes(job.downloaded_bytes), format_bytes(job.total_bytes) if job.total_bytes else 'N/A')))
            bar = QProgressBar(); bar.setRange(0, 100)
            percent = int(job.downloaded_bytes / job.total_bytes * 100) if job.total_bytes else 0
            bar.setValue(max(0, min(100, percent))); bar.setFormat(f"{job.state.capitalize()} {bar.value()}%")
            self.table.setCellWidget(row, 3, bar)
            self.table.setItem(row, 4, QTableWidgetItem(format_eta(job.eta) if job.eta is not None else 'N/A'))
            self.table.setItem(row, 5, QTableWidgetItem(f"{format_bytes(job.speed)}/s" if job.speed else '0 B/s'))
            self.table.setItem(row, 6, QTableWidgetItem(job.created_at))
            source = sanitize_source_url(job.source_url); source_item = QTableWidgetItem(source); source_item.setToolTip(source); self.table.setItem(row, 7, source_item)
            self.downloads.append({
                'id': job.job_id, 'url': job.source_url, 'outtmpl': str(Path(job.save_dir) / f'%(title)s [%(id)s]-{job.job_id[:8]}.%(ext)s'),
                'save_dir': job.save_dir, 'format': ('FILE' if job.requested_format == 'FILE' else
                    build_format_selector(job.requested_format, job.requested_resolution)),
                'ext': job.requested_format, 'thread': None, 'row': row, 'final_path': job.final_output_path,
                'converted_output_path': '', 'requested_resolution': job.requested_resolution, 'metadata': {}, 'job': job,
            })

    def show_dummy_msg(self, title):
        if title == "Options":
            self.show_preferences()

    def show_preferences(self):
        dialog = QDialog(self); dialog.setWindowTitle(f"{APP_NAME} Options")
        layout = QFormLayout(dialog)
        keep_open = QCheckBox("Keep completed download window open"); keep_open.setChecked(self.app_config.keep_completed_window_open)
        browser = QPushButton("Browser Integration..."); browser.clicked.connect(lambda: BrowserIntegrationDialog(self.app_config, dialog).exec())
        save = QPushButton("Save")
        save.clicked.connect(dialog.accept)
        layout.addRow(keep_open); layout.addRow(browser); layout.addRow(save)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.app_config.keep_completed_window_open = keep_open.isChecked()
            self.app_config.persist()

    def init_ui(self):
        menubar = self.menuBar()
        tasks_menu = menubar.addMenu("Tasks")
        tasks_menu.addAction("Add new media download").triggered.connect(lambda: self.open_add_dialog(""))
        tasks_menu.addAction("Download file (PDF / ZIP / installer)...").triggered.connect(self.open_file_dialog)
        tasks_menu.addAction("Convert local media...").triggered.connect(self.open_local_converter)
        batch_action = tasks_menu.addAction("Batch Download (Phase 2B)"); batch_action.setEnabled(False)
        batch_action.setToolTip("Batch input is deferred to Phase 2B.")
        grabber_action = tasks_menu.addAction("Site Grabber (Phase 2C)"); grabber_action.setEnabled(False)
        grabber_action.setToolTip("Full site crawling is deferred to Phase 2C.")
        tasks_menu.addSeparator(); tasks_menu.addAction("Exit").triggered.connect(self.force_quit)

        file_menu = menubar.addMenu("File")
        self.pause_action = file_menu.addAction("Pause Download"); self.pause_action.triggered.connect(self.pause_download)
        self.resume_action = file_menu.addAction("Resume Download"); self.resume_action.triggered.connect(self.resume_download)
        self.stop_action = file_menu.addAction("Cancel Download"); self.stop_action.triggered.connect(self.cancel_selected_download)
        self.properties_action = file_menu.addAction("Properties / Details"); self.properties_action.triggered.connect(self.show_properties)
        self.delete_action = file_menu.addAction("Remove"); self.delete_action.triggered.connect(self.delete_download)

        dl_menu = menubar.addMenu("Downloads")
        dl_menu.addAction("Pause All").triggered.connect(self.pause_all_downloads)
        dl_menu.addAction("Delete All Completed").triggered.connect(self.delete_completed)
        dl_menu.addAction("Move Up").triggered.connect(lambda: self.move_selected_job(-1))
        dl_menu.addAction("Move Down").triggered.connect(lambda: self.move_selected_job(1))
        dl_menu.addAction("Retry").triggered.connect(self.retry_selected_job)
        stop_after = dl_menu.addAction("Stop After Current Jobs"); stop_after.setCheckable(True)
        stop_after.setChecked(self.download_manager.stop_after_current); stop_after.toggled.connect(self.set_stop_after_current)

        view_menu = menubar.addMenu("View")
        sidebar_action = view_menu.addAction("Category Sidebar"); sidebar_action.setCheckable(True); sidebar_action.setChecked(True)
        toolbar_view_action = view_menu.addAction("Toolbar"); toolbar_view_action.setCheckable(True); toolbar_view_action.setChecked(True)
        view_menu.addAction("Reset Column Layout").triggered.connect(self.reset_column_layout)

        help_menu = menubar.addMenu("Help")
        help_menu.addAction("Quick Start").triggered.connect(self.show_quick_start)
        help_menu.addAction("Supported Sites").triggered.connect(self.show_supported_sites)
        help_menu.addAction("Open Logs / Diagnostics").triggered.connect(self.export_diagnostics)
        help_menu.addAction(f"About {APP_NAME}").triggered.connect(self.show_about)

        registration_menu = menubar.addMenu("Registration")
        registration_action = registration_menu.addAction("Registration unavailable pending licensing review")
        registration_action.setEnabled(False)

        self.toolbar = QToolBar("Main Toolbar", self)
        self.toolbar.setMovable(False); self.toolbar.setIconSize(self.toolbar.iconSize() * 1.5)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(self.toolbar)

        # Cohesive local SVG icons; existing QAction references and handlers preserved.
        actions = [
            ("video", "Add media", lambda: self.open_add_dialog("")),
            ("file", "Download file", self.open_file_dialog),
            ("convert", "Converter", self.open_local_converter),
            ("play", "Resume", self.resume_download),
            ("pause", "Pause", self.pause_download),
            ("cancel", "Cancel", self.cancel_selected_download),
            ("pause-all", "Pause all", self.pause_all_downloads),
            ("trash", "Delete", self.delete_download),
            ("clear", "Clear done", self.delete_completed),
            ("settings", "Options", lambda: self.show_dummy_msg("Options")),
            ("share", "Share", self.share_link),
        ]
        self.toolbar_actions = {}
        for glyph, label, callback in actions:
            action = self.toolbar.addAction(ids_icon(glyph, size=38), label)
            action.setToolTip(label)
            action.triggered.connect(callback)
            self.toolbar_actions[label] = action
        self.toolbar_resume_action = self.toolbar_actions["Resume"]
        self.toolbar_pause_action = self.toolbar_actions["Pause"]
        self.toolbar_stop_action = self.toolbar_actions["Cancel"]
        self.toolbar_delete_action = self.toolbar_actions["Delete"]

        self.sidebar_toggle_button = QToolButton(self)
        self.sidebar_toggle_button.setObjectName("idsBannerToggle")
        self.sidebar_toggle_button.setIcon(ids_icon("sidebar", "#ffffff", size=36))
        self.sidebar_toggle_button.setIconSize(QSize(23, 23))
        self.sidebar_toggle_button.setToolTip("Show or hide categories")
        self.sidebar_toggle_button.setAccessibleName("Show or hide categories")
        self.sidebar_toggle_button.clicked.connect(lambda: sidebar_action.setChecked(not sidebar_action.isChecked()))
        self.text_scale_combo = QComboBox(self)
        self.text_scale_combo.setToolTip("Interface text size")
        self.text_scale_combo.setAccessibleName("Interface text size")
        for label, value in (("100%", 100), ("115%", 115), ("130%", 130)):
            self.text_scale_combo.addItem(label, value)
        scale_index = self.text_scale_combo.findData(self.app_config.ui_text_scale)
        self.text_scale_combo.setCurrentIndex(max(0, scale_index))
        self.text_scale_combo.setMaximumWidth(89)
        self.text_scale_combo.currentIndexChanged.connect(self.set_text_scale)

        workspace = QWidget(self)
        workspace.setObjectName("idsWorkspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(13, 11, 13, 9)
        workspace_layout.setSpacing(11)
        self.brand_header, self.dashboard_metrics, self.brand_subtitle = make_banner(workspace)
        self.brand_header.layout().addWidget(self.sidebar_toggle_button)
        self.brand_header.layout().addWidget(self.text_scale_combo)
        workspace_layout.addWidget(self.brand_header)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(8)
        self.splitter.setChildrenCollapsible(False)
        self.sidebar_panel = QFrame(self)
        self.sidebar_panel.setObjectName("idsSidebarPanel")
        self.sidebar_panel.setMinimumWidth(162)
        sidebar_layout = QVBoxLayout(self.sidebar_panel)
        sidebar_layout.setContentsMargins(10, 11, 6, 10)
        sidebar_layout.setSpacing(9)
        sidebar_heading = QHBoxLayout()
        sidebar_title = QLabel("Library")
        sidebar_title.setObjectName("idsSidebarTitle")
        sidebar_heading.addWidget(sidebar_title)
        sidebar_heading.addStretch()
        for glyph, tip, width in (
            ("narrow", "Compact category sidebar", 174),
            ("wide", "Wider category sidebar", 275),
        ):
            button = QToolButton(self.sidebar_panel)
            button.setIcon(ids_icon(glyph, size=31))
            button.setIconSize(QSize(20, 20))
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.clicked.connect(lambda checked=False, amount=width: self.set_sidebar_width(amount))
            sidebar_heading.addWidget(button)
        sidebar_layout.addLayout(sidebar_heading)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAccessibleName("Download categories")
        root_all = QTreeWidgetItem(["All Downloads"])
        root_all.setIcon(0, ids_icon("folder", size=30))
        root_all.setToolTip(0, "All Downloads")
        for category, glyph in (
            ("Video", "video"), ("Audio", "audio"),
            ("Compressed", "archive"), ("Documents", "document"),
        ):
            child = QTreeWidgetItem(root_all, [category])
            child.setIcon(0, ids_icon(glyph, size=30))
            child.setToolTip(0, category)
        self.tree.addTopLevelItem(root_all)
        for label, glyph in (("Unfinished", "clock"), ("Finished", "check")):
            child = QTreeWidgetItem([label])
            child.setIcon(0, ids_icon(glyph, size=30))
            child.setToolTip(0, label)
            self.tree.addTopLevelItem(child)
        root_all.setExpanded(True)
        self.tree.setCurrentItem(root_all)
        self.tree.itemClicked.connect(self.filter_by_category)
        sidebar_layout.addWidget(self.tree)
        self.splitter.addWidget(self.sidebar_panel)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "File Name", "Q", "Size", "Status",
            "Time Left", "Transfer Rate", "Last Try Date", "Description",
        ])
        self.table.setAccessibleName("Download jobs and progress")
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemSelectionChanged.connect(self.update_action_capabilities)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

        self.download_pages = QStackedWidget(self)
        self.empty_page = make_empty_state(
            lambda: self.open_add_dialog(""), self.open_file_dialog, self.open_local_converter, self,
        )
        self.download_pages.addWidget(self.empty_page)
        self.download_pages.addWidget(self.table)
        self.splitter.addWidget(self.download_pages)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes(self.app_config.splitter_sizes[:2])
        workspace_layout.addWidget(self.splitter, 1)

        self.dashboard_footer = QFrame(self)
        self.dashboard_footer.setObjectName("idsFooter")
        footer_layout = QHBoxLayout(self.dashboard_footer)
        footer_layout.setContentsMargins(12, 3, 10, 3)
        self.dashboard_footer_text = QLabel("Ready for a new download")
        self.dashboard_footer_text.setObjectName("idsFooterText")
        footer_layout.addWidget(self.dashboard_footer_text)
        footer_layout.addStretch()
        self.help_button = QToolButton(self)
        self.help_button.setIcon(ids_icon("help", size=30))
        self.help_button.setIconSize(QSize(20, 20))
        self.help_button.setToolTip("Quick start guide")
        self.help_button.setAccessibleName("Quick start guide")
        self.help_button.clicked.connect(self.show_quick_start)
        footer_layout.addWidget(self.help_button)
        workspace_layout.addWidget(self.dashboard_footer)
        self.setCentralWidget(workspace)

        sidebar_action.setChecked(self.app_config.sidebar_visible)
        self.sidebar_panel.setVisible(self.app_config.sidebar_visible)
        sidebar_action.toggled.connect(self.set_sidebar_visible)
        toolbar_view_action.toggled.connect(self.toolbar.setVisible)
        self.apply_text_scale(self.app_config.ui_text_scale, persist=False)
        self.refresh_dashboard()

        columns_menu = view_menu.addMenu("Columns")
        for index, name in enumerate(["File Name", "Q", "Size", "Status", "Time Left", "Transfer Rate", "Last Try Date", "Description"]):
            action = columns_menu.addAction(name); action.setCheckable(True)
            action.setChecked(index not in self.app_config.hidden_columns)
            action.toggled.connect(lambda checked, col=index: self.table.setColumnHidden(col, not checked))
            self.table.setColumnHidden(index, index in self.app_config.hidden_columns)
        if self.app_config.column_widths:
            for index, width in enumerate(self.app_config.column_widths[:self.table.columnCount()]):
                self.table.setColumnWidth(index, max(40, int(width)))
        self.update_action_capabilities()

    def set_sidebar_visible(self, visible):
        self.sidebar_panel.setVisible(bool(visible))
        self.app_config.sidebar_visible = bool(visible)
        self.sidebar_toggle_button.setToolTip("Hide categories" if visible else "Show categories")
        self.app_config.persist()

    def set_sidebar_width(self, width):
        if not self.sidebar_panel.isVisible():
            self.sidebar_panel.show()
            self.app_config.sidebar_visible = True
        total = max(500, sum(self.splitter.sizes()))
        chosen = max(self.sidebar_panel.minimumWidth(), min(int(width), total - 340))
        self.splitter.setSizes([chosen, total - chosen])
        self.app_config.splitter_sizes = list(self.splitter.sizes())
        self.app_config.persist()

    def set_text_scale(self, index):
        self.apply_text_scale(self.text_scale_combo.itemData(index))

    def apply_text_scale(self, value, persist=True):
        scale = int(value) if value in (100, 115, 130) else 100
        app = QApplication.instance()
        if app:
            font = QFont("Segoe UI", 10)
            font.setPointSize({100: 10, 115: 12, 130: 13}[scale])
            app.setFont(font)
        self.app_config.ui_text_scale = scale
        if hasattr(self, 'sidebar_panel'):
            self.sidebar_panel.setMinimumWidth({100: 162, 115: 187, 130: 225}[scale])
        if persist:
            self.app_config.persist()
        if hasattr(self, 'table'):
            self.table.verticalHeader().setDefaultSectionSize(int(37 * scale / 100))

    def refresh_dashboard(self):
        if not hasattr(self, 'dashboard_metrics'):
            return
        jobs = [record['job'] for record in self.downloads if record.get('job')]
        active_states = {
            JobState.CONNECTING.value, JobState.RESOLVING.value,
            JobState.DOWNLOADING.value, JobState.MERGING.value,
            JobState.VERIFYING.value, JobState.CONVERTING.value,
        }
        counts = {
            'active': sum(job.state in active_states for job in jobs),
            'waiting': sum(job.state in {JobState.QUEUED.value, JobState.PAUSED.value} for job in jobs),
            'done': sum(job.state == JobState.COMPLETED.value for job in jobs),
        }
        for key, word in (('active', 'Active'), ('waiting', 'Waiting'), ('done', 'Finished')):
            self.dashboard_metrics[key].setText(f"{word}  {counts[key]}")
            self.dashboard_metrics[key].setAccessibleName(f"{word}: {counts[key]} downloads")
        self.download_pages.setCurrentIndex(1 if self.table.rowCount() else 0)
        if counts['active']:
            status = f"{counts['active']} download{'s' if counts['active'] != 1 else ''} in progress"
        elif counts['waiting']:
            status = f"{counts['waiting']} download{'s' if counts['waiting'] != 1 else ''} waiting"
        elif jobs:
            status = "All current downloads are idle"
        else:
            status = "Ready for a new download"
        self.dashboard_footer_text.setText(status)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'toolbar') and hasattr(self, 'dashboard_metrics'):
            compact = self.width() < 1090
            self.toolbar.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonIconOnly if compact else
                Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            )
            self.dashboard_metrics['done'].setVisible(self.width() >= 1000)
            self.brand_subtitle.setVisible(self.width() >= 820)
            very_narrow = self.width() < 840
            self.toolbar.setIconSize(QSize(22, 22) if very_narrow else QSize(30, 30))
            self.toolbar.setStyleSheet(
                "QToolBar {padding:2px 6px;} QToolButton {min-width:31px;"
                "min-height:29px;padding:3px 5px;}" if very_narrow else ""
            )
            self.brand_header.setMinimumHeight(75 if very_narrow else 91)
            self.brand_header.layout().setContentsMargins(
                14 if very_narrow else 22, 8 if very_narrow else 12,
                14 if very_narrow else 20, 8 if very_narrow else 12
            )

    def selected_record(self):
        rows = self.table.selectionModel().selectedRows() if hasattr(self, 'table') else []
        return next((item for item in self.downloads if rows and item['row'] == rows[0].row()), None)

    def open_local_converter(self):
        LocalConverterDialog(self).exec()

    def persist_ui_preferences(self):
        self.app_config.window_size = [self.width(), self.height()]
        self.app_config.splitter_sizes = self.splitter.sizes()
        self.app_config.column_widths = [self.table.columnWidth(index) for index in range(self.table.columnCount())]
        self.app_config.hidden_columns = [index for index in range(self.table.columnCount()) if self.table.isColumnHidden(index)]
        self.app_config.persist()

    def reset_column_layout(self):
        for index in range(self.table.columnCount()):
            self.table.setColumnHidden(index, False)
            self.table.resizeColumnToContents(index)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    def update_action_capabilities(self):
        capabilities = self.selected_action_capabilities()
        for action, key in (
            (getattr(self, 'resume_action', None), 'resume'),
            (getattr(self, 'pause_action', None), 'pause'),
            (getattr(self, 'stop_action', None), 'stop'),
            (getattr(self, 'delete_action', None), 'delete'),
            (getattr(self, 'toolbar_resume_action', None), 'resume'),
            (getattr(self, 'toolbar_pause_action', None), 'pause'),
            (getattr(self, 'toolbar_stop_action', None), 'stop'),
            (getattr(self, 'toolbar_delete_action', None), 'delete'),
        ):
            if action:
                action.setEnabled(capabilities.get(key, False))

    def selected_action_capabilities(self):
        record = self.selected_record()
        capabilities = job_capabilities(record['job']) if record and record.get('job') else {key: False for key in ('resume', 'pause', 'stop', 'delete')}
        conversion_state = self.conversion_controller.state(record['id']) if record else None
        if conversion_state is not None:
            capabilities = dict(capabilities)
            capabilities['pause'] = conversion_state in {'starting', 'converting'}
            capabilities['resume'] = conversion_state == 'paused'
            capabilities['stop'] = conversion_state in {'starting', 'converting', 'paused'}
        return capabilities

    def show_quick_start(self):
        QMessageBox.information(self, "Quick Start", "Use Add URL for video/audio. Use File Download for PDF, ZIP, installers and other direct HTTP/HTTPS files. You can pause, resume and choose a save folder.")

    def show_supported_sites(self):
        QMessageBox.information(self, "Supported Sites", "Video and audio use supported yt-dlp extractors. General files use the direct HTTP(S) downloader. Website authorization, redirects and supported formats vary; DRM is unsupported.")

    def show_about(self):
        QMessageBox.information(self, f"About {APP_NAME}", f"{APP_NAME}\nTool by InShaLIve.os\n\nMedia downloads and conversions are supported. General browser file interception is in development.")

    def export_diagnostics(self):
        logs_dir = self.app_config.app_data_root / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        destination = logs_dir / f"diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        payload = {
            'application': APP_NAME,
            'jobs': [{
                **{k: v for k, v in job.to_dict().items() if k != 'original_source_url'},
                'source_url': sanitize_source_url(job.source_url),
                'original_source_url': sanitize_source_url(job.original_source_url),
                'error_summary': clean_error_summary(job.error_summary),
            } for job in self.download_manager.jobs.values()],
        }
        def write_and_open():
            atomic_write_json(destination, payload)
            subprocess.Popen(['explorer', '/select,', str(destination)])
        threading.Thread(target=write_and_open, name='StratrumDiagnosticWriter', daemon=True).start()

    def show_properties(self):
        record = self.selected_record()
        if not record:
            QMessageBox.information(self, "Properties", "Select a download job first.")
            return
        job = record['job']
        editable = job_capabilities(job)['edit'] and job.requested_format != 'FILE'
        dialog = QDialog(self); dialog.setWindowTitle("Download Properties"); dialog.setMinimumWidth(620)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        source_field = QLineEdit(sanitize_source_url(job.original_source_url)); source_field.setReadOnly(True)
        folder_field = QLineEdit(job.save_dir); folder_field.setEnabled(editable)
        format_combo = QComboBox(); format_combo.addItems(list(OUTPUT_PROFILES) + (['FILE'] if job.requested_format == 'FILE' else [])); format_combo.setCurrentText(job.requested_format); format_combo.setEnabled(editable)
        resolution_combo = QComboBox(); resolution_combo.addItem("Best available", None)
        for height, label in RESOLUTION_LABELS.items(): resolution_combo.addItem(label, height)
        idx = resolution_combo.findData(job.requested_resolution); resolution_combo.setCurrentIndex(max(0, idx)); resolution_combo.setEnabled(editable and output_profile(job.requested_format).media_kind == 'video')
        format_combo.currentTextChanged.connect(lambda value: resolution_combo.setEnabled(editable and output_profile(value).media_kind == 'video'))
        priority_spin = QSpinBox(); priority_spin.setRange(-100, 100); priority_spin.setValue(job.priority); priority_spin.setEnabled(editable)
        form.addRow("Sanitized source", source_field); form.addRow("Save folder", folder_field)
        form.addRow("Requested format", format_combo); form.addRow("Requested resolution", resolution_combo)
        form.addRow("Queue", QLabel(job.queue_name)); form.addRow("Priority", priority_spin)
        form.addRow("Actual format", QLabel(job.actual_format or "pending")); form.addRow("Actual resolution", QLabel(str(job.actual_resolution or "pending")))
        form.addRow("Final output", QLabel(job.final_output_path or "pending"))
        form.addRow("Transferred", QLabel(f"{format_bytes(job.downloaded_bytes)} / {format_bytes(job.total_bytes) if job.total_bytes else 'unknown'}"))
        form.addRow("Resumable", QLabel("Yes" if job.resumable else "No")); form.addRow("State", QLabel(job.state))
        form.addRow("Timestamps", QLabel(f"Created {job.created_at}; Started {job.started_at or '-'}; Completed {job.completed_at or '-'}"))
        form.addRow("Last safe error", QLabel(job.error_summary or "None")); layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        if editable:
            save_button = QPushButton("Save Safe Changes"); save_button.clicked.connect(dialog.accept); buttons.addWidget(save_button)
        close_button = QPushButton("Close"); close_button.clicked.connect(dialog.reject); buttons.addWidget(close_button); layout.addLayout(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and editable:
            folder = Path(folder_field.text()).expanduser()
            if not folder.is_dir():
                QMessageBox.warning(self, "Properties", "The selected save folder does not exist.")
                return
            job.save_dir = str(folder.resolve()); job.requested_format = format_combo.currentText()
            job.requested_resolution = resolution_combo.currentData() if output_profile(job.requested_format).media_kind == 'video' else None
            job.priority = priority_spin.value(); record['save_dir'] = job.save_dir; record['ext'] = job.requested_format
            record['requested_resolution'] = job.requested_resolution
            record['outtmpl'] = str(Path(job.save_dir) / f'%(title)s [%(id)s]-{job.job_id[:8]}.%(ext)s')
            record['format'] = build_format_selector(job.requested_format, job.requested_resolution)
            self.download_manager.persist(); self.table.setItem(record['row'], 1, QTableWidgetItem(str(job.priority)))

    def move_selected_job(self, offset):
        record = self.selected_record()
        if record:
            self.download_manager.move(record['id'], offset)

    def retry_selected_job(self):
        record = self.selected_record()
        if record and self.download_manager.retry(record['id']):
            record['job'].state = JobState.QUEUED.value
            self.start_queued_jobs()

    def set_stop_after_current(self, enabled):
        self.download_manager.stop_after_current = bool(enabled)
        self.app_config.stop_after_current = bool(enabled)
        self.app_config.persist()
        self.download_manager.persist()
        if not enabled:
            self.start_queued_jobs()

    def pause_all_downloads(self):
        for record in self.downloads:
            self.pause_job(record['id'])

    def cancel_selected_download(self):
        record = self.selected_record()
        if not record:
            QMessageBox.information(self, "Cancel Download", "Select a download job first.")
            return
        self.cancel_job(record['id'], False)

    def pause_job(self, job_id):
        record = self.get_download_by_id(job_id)
        if self.conversion_controller.state(job_id) in {'starting', 'converting'}:
            if self.conversion_controller.pause(job_id) and job_id in self.popups:
                self.popups[job_id].set_job_state('paused')
            return
        if not record or not job_capabilities(record['job'])['pause']:
            return
        if record.get('thread') and record['thread'].isRunning():
            record['thread'].paused = True
        self.download_manager.set_state(job_id, JobState.PAUSED)
        if job_id in self.popups:
            self.popups[job_id].set_job_state(JobState.PAUSED.value)
        self.update_action_capabilities()
        QTimer.singleShot(150, self.start_queued_jobs)

    def resume_job(self, job_id):
        record = self.get_download_by_id(job_id)
        if self.conversion_controller.state(job_id) == 'paused':
            if self.conversion_controller.resume(job_id) and job_id in self.popups:
                self.popups[job_id].set_job_state('converting')
            return
        if record and job_capabilities(record['job'])['resume']:
            record['job'].state = JobState.QUEUED.value
            self.download_manager.persist()
            self.start_queued_jobs()
            self.update_action_capabilities()

    def cancel_job(self, job_id, remove_partials=False):
        record = self.get_download_by_id(job_id)
        if not record:
            return
        thread = record.get('thread')
        if self.conversion_controller.state(job_id) in {'starting', 'converting', 'paused'}:
            self.conversion_controller.cancel(job_id)
            if bar := self.table.cellWidget(record['row'], 3): bar.setFormat("Cancelling conversion...")
            return
        if thread and thread.isRunning():
            thread.cancel()
        self.download_manager.set_state(job_id, JobState.CANCELLED)
        if remove_partials and thread:
            root = Path(record['save_dir']).resolve()
            for partial in list(thread.temporary_paths):
                try:
                    path = Path(partial).resolve(strict=True)
                    path.relative_to(root)
                    if path.suffix.lower() in {'.part', '.ytdl'} or '.part' in path.name or re.search(r'\.f\d+\.', path.name, re.IGNORECASE):
                        path.unlink()
                except (OSError, ValueError):
                    continue
        if job_id in self.popups:
            self.popups[job_id].set_job_state(JobState.CANCELLED.value)
        self.update_action_capabilities()

    def set_job_speed_limit(self, job_id, bytes_per_second):
        record = self.get_download_by_id(job_id)
        if record and record.get('thread'):
            record['thread'].set_speed_limit(bytes_per_second)
        self.app_config.speed_limit_bps = max(0, int(bytes_per_second or 0))
        self.app_config.persist()

    def update_job_metrics(self, job_id, downloaded, total, speed, eta):
        if job_id in self.download_manager.jobs:
            self.download_manager.update_progress(job_id, downloaded, total, speed, eta)

    def filter_by_category(self, item, column):
        category = item.text(0)
        for row in range(self.table.rowCount()):
            if category == "All Downloads": self.table.setRowHidden(row, False); continue
            filename = self.table.item(row, 0).text().lower()
            record = next((item for item in self.downloads if item['row'] == row), None)
            state = record['job'].state if record and record.get('job') else JobState.QUEUED.value
            hidden = True
            if category == "Video" and filename.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')): hidden = False
            elif category == "Audio" and filename.endswith(('.mp3', '.wav', '.flac', '.m4a')): hidden = False
            elif category == "Compressed" and filename.endswith(('.zip', '.rar', '.7z')): hidden = False
            elif category == "Documents" and filename.endswith(('.pdf', '.docx', '.txt')): hidden = False
            elif category == "Finished" and state == JobState.COMPLETED.value: hidden = False
            elif category == "Unfinished" and state != JobState.COMPLETED.value: hidden = False
            self.table.setRowHidden(row, hidden)

    def show_context_menu(self, position):
        record = self.selected_record()
        capabilities = job_capabilities(record['job']) if record else {key: False for key in ('open', 'open_folder', 'convert', 'resume', 'pause', 'delete')}
        conversion_state = self.conversion_controller.state(record['id']) if record else None
        menu = QMenu()
        open_action = menu.addAction("Open"); open_action.setEnabled(capabilities['open']); open_action.triggered.connect(self.open_selected_file)
        folder_action = menu.addAction("Open folder"); folder_action.setEnabled(capabilities['open_folder']); folder_action.triggered.connect(self.open_selected_folder)
        menu.addAction("Properties / Details").triggered.connect(self.show_properties)
        menu.addSeparator()
        cv_menu = menu.addMenu("Convert Format...")
        for target in (profile.extension for profile in OUTPUT_PROFILES.values()):
            action = cv_menu.addAction(f"To {target.upper()}")
            supported = bool(record and capabilities['convert'] and conversion_supported(record.get('final_path', ''), target, record.get('probe')))
            action.setEnabled(supported)
            if record and not supported:
                try:
                    reason = conversion_target_capabilities(record.get('probe') or probe_media_file(record.get('final_path', '')))[target.upper()]['reason']
                    action.setToolTip(reason)
                except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                    action.setToolTip('FFprobe could not verify this conversion target.')
            action.triggered.connect(lambda checked=False, ext=target: self.trigger_conversion(ext))
        menu.addSeparator()
        resume_action = menu.addAction("Resume Download"); resume_action.setEnabled(capabilities['resume']); resume_action.triggered.connect(self.resume_download)
        pause_action = menu.addAction("Pause Download"); pause_action.setEnabled(capabilities['pause']); pause_action.triggered.connect(self.pause_download)
        pause_conversion = menu.addAction("Pause Conversion"); pause_conversion.setEnabled(conversion_state in {'starting', 'converting'}); pause_conversion.triggered.connect(self.pause_download)
        resume_conversion = menu.addAction("Resume Conversion"); resume_conversion.setEnabled(conversion_state == 'paused'); resume_conversion.triggered.connect(self.resume_download)
        cancel_conversion = menu.addAction("Cancel Conversion"); cancel_conversion.setEnabled(conversion_state in {'starting', 'converting', 'paused'}); cancel_conversion.triggered.connect(self.cancel_selected_download)
        menu.addSeparator()
        delete_action = menu.addAction("Remove"); delete_action.setEnabled(capabilities['delete']); delete_action.triggered.connect(self.delete_download)
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
        record = self.selected_record()
        if not record:
            QMessageBox.information(self, "Share Source", "Select a download row to copy or open its source URL.")
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copy Source URL")
        open_action = menu.addAction("Open Source Page")
        chosen = menu.exec(QCursor.pos())
        if chosen == copy_action:
            QApplication.clipboard().setText(record['url'])
            QMessageBox.information(self, "Source URL", "Source URL copied to the clipboard.")
        elif chosen == open_action:
            valid, _ = validate_url(record['url'])
            if valid:
                webbrowser.open(record['url'])
            else:
                QMessageBox.warning(self, "Source URL", "The stored source URL is invalid.")

    def delete_completed(self):
        for row in range(self.table.rowCount() - 1, -1, -1):
            record = next((item for item in self.downloads if item['row'] == row), None)
            if record and record['job'].state == JobState.COMPLETED.value:
                self.downloads.remove(record)
                self.table.removeRow(row)
                self.download_manager.jobs.pop(record['id'], None)
                if record['id'] in self.download_manager.queue:
                    self.download_manager.queue.remove(record['id'])
                for other in self.downloads:
                    if other['row'] > row:
                        other['row'] -= 1
        self.download_manager.persist()
        self.refresh_dashboard()

    def init_server(self):
        self.server_thread = ServerThread(self.app_config)
        self.server_thread.download_requested.connect(self.handle_browser_request)
        self.server_thread.file_requested.connect(self.handle_file_handoff)
        self.server_thread.failed.connect(self.browser_bridge_failed)
        self.server_thread.start()

    def browser_bridge_failed(self, message):
        self.statusBar().showMessage(message)
        self.tray_icon.showMessage("I-DS Browser Connection", message, QSystemTrayIcon.MessageIcon.Warning, 6000)

    def handle_browser_request(self, url, action, request_context=None):
        if action not in EXTENSION_ACTIONS:
            return False
        resolved_action = {
            'default': self.app_config.primary_browser_action,
            'quick': 'quick_download',
            'options': 'download_with_options',
        }.get(action, action)
        if resolved_action == 'quick_download':
            self.show_normal(request_foreground=True)
            try:
                save_dir, requested_resolution, target_format = self.quick_download_defaults()
            except ValueError as exc:
                QMessageBox.warning(self, "Quick Download Unavailable", str(exc))
                return False
            self.start_new_download(url, save_dir, requested_resolution, target_format, None, request_context)
            return True
        self.open_add_dialog(url, request_foreground=True, request_context=request_context)
        return True

    def quick_download_defaults(self, home_directory=None):
        target_format = self.app_config.preferred_format if self.app_config.preferred_format in OUTPUT_PROFILES else 'MP4'
        requested_resolution = self.app_config.preferred_resolution
        if requested_resolution not in {None, 240, 360, 480, 720, 1080, 1440, 2160, 4320}:
            requested_resolution = None
        candidates = [Path(folder).expanduser() for folder in self.app_config.recent_folders]
        if home_directory is not None:
            candidates.append(Path(home_directory) / 'Downloads')
        else:
            system_downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
            if system_downloads:
                candidates.append(Path(system_downloads))
            candidates.append(Path.home() / 'Downloads')
        save_dir = next((candidate.resolve() for candidate in candidates if candidate.is_dir()), None)
        if save_dir is None:
            raise ValueError("Quick Download cannot start because the saved folder and your Downloads folder are unavailable. Choose a valid folder in Download with Options first.")
        return str(save_dir), requested_resolution, target_format

    def quick_download_defaults_valid(self):
        try:
            self.quick_download_defaults()
            return True
        except ValueError:
            return False

    def open_add_dialog(self, url="", request_foreground=False, request_context=None):
        if isinstance(url, bool): url = ""
        self.show_normal(request_foreground=request_foreground)
        dialog = DownloadFileInfoDialog(self, prefill_url=url, app_config=self.app_config, request_context=request_context)
        if request_foreground:
            QTimer.singleShot(0, lambda: self.request_foreground(dialog))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            final_url, save_dir, requested_height, target_ext, metadata = dialog.get_data()
            if final_url: self.start_new_download(final_url, save_dir, requested_height, target_ext, metadata, dialog.request_context_for(final_url))

    def open_file_dialog(self):
        url, accepted = QInputDialog.getText(self, "Download a File", "HTTP/HTTPS file URL:")
        if not accepted or not url.strip():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Choose where to save the file",
            self.quick_download_defaults()[0] if self.quick_download_defaults_valid() else str(Path.home())
        )
        if folder and not self.start_http_download(url.strip(), folder, show_popup=True):
            QMessageBox.warning(self, "File Download", "The URL or save folder is not valid. Use an HTTP/HTTPS file link and an existing folder.")

    def handle_file_handoff(self, url, request_context, file_name_hint, receipt):
        # Queued Qt slot executes on the GUI thread. A timed-out request is
        # rejected atomically and must not create a late/duplicate file job.
        receipt.resolve(lambda: self.start_http_download(url, filename_hint=file_name_hint))

    def start_http_download(self, url, save_dir=None, filename_hint="", show_popup=False):
        valid, _ = validate_url(url)
        if not valid:
            return False
        if save_dir is None:
            try:
                save_dir = self.quick_download_defaults()[0]
            except ValueError:
                return False
        try:
            folder = Path(save_dir).expanduser().resolve(strict=True)
        except (OSError, ValueError):
            return False
        if not folder.is_dir():
            return False
        job_id = uuid.uuid4().hex
        hint = safe_file_name(filename_hint) if filename_hint else ''
        job = DownloadJob(
            job_id=job_id, source_url=url, save_dir=str(folder),
            requested_format='FILE', file_name_hint=hint, state=JobState.QUEUED.value,
        )
        self.download_manager.add_job(job)
        self.app_config.add_recent_folder(folder)
        row = self.table.rowCount()
        self.table.insertRow(row)
        bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(0); bar.setFormat("Queued")
        self.table.setItem(row, 0, QTableWidgetItem(hint or "File download"))
        self.table.setItem(row, 1, QTableWidgetItem("0"))
        self.table.setItem(row, 2, QTableWidgetItem("Calculating"))
        self.table.setCellWidget(row, 3, bar)
        self.table.setItem(row, 4, QTableWidgetItem("--:--"))
        self.table.setItem(row, 5, QTableWidgetItem("0 B/s"))
        self.table.setItem(row, 6, QTableWidgetItem(datetime.now().strftime("%b %d %H:%M:%S %Y")))
        source_display = sanitize_source_url(url)
        source_item = QTableWidgetItem(source_display)
        source_item.setToolTip(source_display)
        self.table.setItem(row, 7, source_item)
        record = {
            'id': job_id, 'url': url, 'outtmpl': str(folder / (hint or 'download.bin')),
            'save_dir': str(folder), 'format': 'FILE', 'ext': 'FILE', 'thread': None,
            'row': row, 'final_path': '', 'converted_output_path': '',
            'requested_resolution': None, 'metadata': {}, 'job': job,
        }
        self.downloads.append(record)
        if show_popup:
            popup = DownloadProgressPopup(hint or "File download", source_display, self, job_id, self.app_config)
            popup.pause_requested.connect(self.pause_job)
            popup.resume_requested.connect(self.resume_job)
            popup.cancel_requested.connect(self.cancel_job)
            popup.speed_limit_changed.connect(self.set_job_speed_limit)
            popup.set_details("General HTTP file download. Existing files will not be overwritten.")
            self.popups[job_id] = popup
            popup.show()
        self.start_queued_jobs()
        return True

    def start_new_download(self, url, save_dir, requested_height, target_ext, metadata=None, request_context=None):
        download_id = uuid.uuid4().hex
        save_path = Path(save_dir).expanduser().resolve()
        if not save_path.is_dir():
            QMessageBox.warning(self, "Save Folder", "The selected save folder does not exist.")
            return
        profile = output_profile(target_ext)
        format_str = build_format_selector(target_ext, requested_height)
        outtmpl = build_safe_output_template(save_path, download_id)
        job = DownloadJob(
            job_id=download_id, package_id=download_id, source_url=url, save_dir=str(save_path),
            requested_format=str(target_ext).upper(), requested_resolution=requested_height,
            priority=0, state=JobState.QUEUED.value,
        )
        self.download_manager.add_job(job)
        self.app_config.add_recent_folder(save_path)

        row = self.table.rowCount()
        self.table.insertRow(row)

        pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(0)
        self.table.setItem(row, 0, QTableWidgetItem("Connecting..."))
        self.table.setItem(row, 1, QTableWidgetItem(str(job.priority)))
        self.table.setItem(row, 2, QTableWidgetItem("Calculating"))
        self.table.setCellWidget(row, 3, pb)
        self.table.setItem(row, 4, QTableWidgetItem("--:--"))
        self.table.setItem(row, 5, QTableWidgetItem("0 B/s"))
        self.table.setItem(row, 6, QTableWidgetItem(datetime.now().strftime("%b %d %H:%M:%S %Y")))
        source_display = sanitize_source_url(url)
        source_item = QTableWidgetItem(source_display); source_item.setToolTip(source_display)
        self.table.setItem(row, 7, source_item)

        record = {
            'id': download_id, 'url': url, 'outtmpl': outtmpl, 'save_dir': str(save_path),
            'format': format_str, 'ext': target_ext, 'thread': None, 'row': row,
            'final_path': '', 'converted_output_path': '', 'requested_resolution': requested_height,
            'metadata': metadata or {}, 'request_context': request_context or {}, 'job': job,
        }
        self.downloads.append(record)

        popup = DownloadProgressPopup("Queued", url, self, download_id, self.app_config)
        popup.pause_requested.connect(self.pause_job)
        popup.resume_requested.connect(self.resume_job)
        popup.cancel_requested.connect(self.cancel_job)
        popup.speed_limit_changed.connect(self.set_job_speed_limit)
        popup.set_details(f"Requested profile: {target_ext}\nRequested resolution: {requested_height or 'Best'}\nSave folder: {save_path}")
        popup.show()
        self.popups[download_id] = popup
        self.start_queued_jobs()

    def create_download_thread(self, record):
        if record['job'].requested_format == 'FILE':
            thread = FileDownloadThread(
                record['id'], record['url'], record['save_dir'],
                record['job'].file_name_hint, self.app_config.speed_limit_bps,
            )
            thread.progress.connect(self.update_progress)
            thread.status.connect(self.update_status)
            thread.result_ready.connect(self.download_finished)
            thread.finished.connect(lambda id=record['id'], worker=thread: self.file_thread_stopped(id, worker))
            thread.size_updated.connect(self.update_size)
            thread.metrics.connect(self.update_job_metrics)
            return thread
        thread = DownloadThread(
            record['id'], record['url'], record['outtmpl'], record['format'], record['ext'],
            record.get('requested_resolution'), record.get('metadata'), record['save_dir'],
            self.app_config.speed_limit_bps,
            record.get('request_context'),
            self.app_config,
        )
        thread.progress.connect(self.update_progress)
        thread.status.connect(self.update_status)
        thread.finished.connect(self.download_finished)
        thread.size_updated.connect(self.update_size)
        thread.metrics.connect(self.update_job_metrics)
        return thread

    def start_queued_jobs(self):
        while self.download_manager.can_start_more():
            pending = next((record for record in self.downloads if record['job'].state == JobState.QUEUED.value and not record.get('thread')), None)
            if not pending:
                break
            thread = self.create_download_thread(pending)
            pending['thread'] = thread
            self.download_manager.set_state(pending['id'], JobState.RESOLVING)
            if pending['id'] in self.popups:
                self.popups[pending['id']].set_job_state(JobState.RESOLVING.value)
            thread.start()

    def file_thread_stopped(self, job_id, worker):
        record = self.get_download_by_id(job_id)
        if record and record.get('thread') is worker:
            record['thread'] = None
            if record['job'].state == JobState.QUEUED.value:
                self.start_queued_jobs()

    def get_download_by_id(self, id): return next((d for d in self.downloads if d['id'] == id), None)

    def update_progress(self, id, filename, percent, downloaded, total, speed, eta, status):
        if d := self.get_download_by_id(id):
            now = time.monotonic()
            if status != 'Completed' and now - self.last_progress_paint.get(id, 0.0) < 0.12:
                return
            self.last_progress_paint[id] = now
            if filename and filename != "Connecting...":
                item = QTableWidgetItem(filename); item.setToolTip(filename)
                self.table.setItem(d['row'], 0, item)

            self.table.setItem(d['row'], 2, QTableWidgetItem(format_transfer_size(downloaded, total)))
            self.table.setItem(d['row'], 4, QTableWidgetItem(eta))
            self.table.setItem(d['row'], 5, QTableWidgetItem(speed))
            if bar := self.table.cellWidget(d['row'], 3):
                bar.setValue(int(percent))
                bar.setFormat(f"{status} {int(percent)}%")

            if id in self.popups:
                self.popups[id].update_stats(filename, percent, downloaded, total, speed, eta, status)

    def update_size(self, id, filename, size):
        if d := self.get_download_by_id(id): self.table.setItem(d['row'], 2, QTableWidgetItem(size))

    def update_status(self, id, status):
        if d := self.get_download_by_id(id):
            state_map = {
                'Connecting': JobState.CONNECTING, 'Downloading': JobState.DOWNLOADING,
                'Postprocessing': JobState.MERGING, 'Merging streams': JobState.MERGING,
                'Converting': JobState.CONVERTING, 'Verifying output': JobState.VERIFYING,
                'Completed': JobState.COMPLETED, 'Paused': JobState.PAUSED,
                'Cancelled': JobState.CANCELLED, 'Failed': JobState.FAILED, 'Error': JobState.FAILED,
            }
            if status.startswith('Downloading'):
                state_map[status] = JobState.DOWNLOADING
            if status in state_map and id in self.download_manager.jobs:
                self.download_manager.set_state(id, state_map[status])
            if status == 'Paused' and d['job'].requested_format != 'FILE':
                d['thread'] = None
            if id in self.popups:
                self.popups[id].set_job_state(state_map.get(status, status).value if isinstance(state_map.get(status), JobState) else status)
                self.popups[id].set_details(
                    f"State: {status}\nRequested profile: {d['job'].requested_format}\n"
                    f"Requested resolution: {d['job'].requested_resolution or 'Best'}\n"
                    f"Output: {d['job'].final_output_path or 'pending'}\n"
                    f"Last safe error: {d['job'].error_summary or 'None'}"
                )
            if bar := self.table.cellWidget(d['row'], 3):
                color_map = {
                    'Queued': '#808080', 'Connecting': '#0078d7', 'Downloading': '#0067b8',
                    'Paused': '#ca5010', 'Postprocessing': '#8764b8', 'Merging streams': '#8764b8',
                    'Converting': '#8764b8', 'Verifying output': '#498205', 'Completed': '#107c10',
                    'Failed': '#a4262c', 'Error': '#a4262c', 'Cancelled': '#605e5c',
                }
                selected_color = color_map.get(status, '#0067b8' if status.startswith('Downloading') else None)
                if selected_color:
                    bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {selected_color}; }}")
                if status == 'Completed':
                    bar.setValue(100)
                    bar.setFormat("Completed 100%")
                elif status.startswith('Downloading') and bar.value() > 0:
                    bar.setFormat(f"{status} {bar.value()}%")
                else:
                    bar.setFormat(status)
            self.update_action_capabilities()

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
                    self.download_manager.set_state(id, JobState.FAILED, 'Unsafe completed output path')
                    if popup := self.popups.get(id):
                        popup.set_job_state(JobState.FAILED.value)
                        popup.set_details("State: failed\nUnsafe completed output path; the window remains open.")
                    self.start_queued_jobs()
                    return
                if bar: bar.setValue(100); bar.setFormat("Complete 100%")
                thread = d.get('thread')
                probe = thread.final_probe if thread else {}
                video_stream = next((stream for stream in probe.get('streams', []) if stream.get('codec_type') == 'video'), {})
                d['job'].final_output_path = str(safe_path)
                d['job'].actual_format = safe_path.suffix.lower().lstrip('.')
                d['job'].actual_resolution = video_stream.get('height')
                d['probe'] = probe
                d['job'].temporary_paths = list(thread.temporary_paths) if thread else []
                d['job'].resolved_media_url = thread.resolved_media_url if thread else ''
                self.download_manager.set_state(id, JobState.COMPLETED)
                completed_size = format_bytes(safe_path.stat().st_size)
                self.table.setItem(d['row'], 2, QTableWidgetItem(format_transfer_size(completed_size, completed_size)))
                popup = self.popups.get(id)
                if popup:
                    popup.update_stats(safe_path.name, 100.0, completed_size, completed_size, '0 B/s', '00:00:00', 'Completed')
                    self.execute_completion_action(d, popup)

                dlg = QMessageBox(self)
                dlg.setWindowTitle("Download Complete")
                dlg.setText(f"Download Complete!\n\n{safe_path.name}")
                open_btn = None
                if not self.is_dangerous_file(safe_path):
                    open_btn = dlg.addButton("Open", QMessageBox.ButtonRole.ActionRole)
                folder_btn = dlg.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
                dlg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
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
                cancelled = str(error_msg).lower() == 'cancelled'
                state = JobState.CANCELLED if cancelled else JobState.FAILED
                self.download_manager.set_state(id, state, error_msg)
                if bar: bar.setFormat("Cancelled" if cancelled else f"Failed: {clean_error_summary(error_msg)}")
                if id in self.popups:
                    self.popups[id].set_job_state(state.value)
                    self.popups[id].set_details(f"State: {state.value}\nSafe error: {clean_error_summary(error_msg)}\nPartial files were retained unless removal was explicitly requested.")
                if not cancelled:
                    QMessageBox.warning(self, "Download Failed", clean_error_summary(error_msg))
            d['thread'] = None
            self.save_downloads_to_file()
            self.refresh_dashboard()
            self.update_action_capabilities()
            self.start_queued_jobs()

    def execute_completion_action(self, record, popup):
        action = popup.completion_action()
        self.app_config.completion_action = action
        self.app_config.persist()
        if action == 'open_folder':
            try: open_download_folder(record)
            except (OSError, ValueError): pass
        elif action == 'open_file':
            try: open_download_file(record)
            except (OSError, ValueError, PermissionError): pass
        elif action.startswith('convert_'):
            self.start_conversion_for_record(record, action.split('_', 1)[1])
        if not action.startswith('convert_'):
            popup.schedule_verified_close(
                lambda job_id=record['id'], expected=popup: self.close_completed_popup(job_id, expected)
            )
        if popup.exit_when_idle_cb.isChecked() and self.download_manager.active_count() == 0 and not self.download_manager.pending_jobs():
            QTimer.singleShot(0, self.force_quit)

    def close_completed_popup(self, job_id, expected_popup):
        record = self.get_download_by_id(job_id)
        if self.popups.get(job_id) is not expected_popup or not record or record['job'].state != JobState.COMPLETED.value:
            return False
        expected_popup.close()
        self.popups.pop(job_id, None)
        return True

    def pause_download(self):
        record = self.selected_record()
        if record:
            self.pause_job(record['id'])

    def resume_download(self):
        record = self.selected_record()
        if record:
            self.resume_job(record['id'])

    def delete_download(self):
        for idx in sorted(self.table.selectionModel().selectedRows(), key=lambda x: x.row(), reverse=True):
            row = idx.row()
            if d := next((d for d in self.downloads if d['row'] == row), None):
                if not job_capabilities(d['job'])['delete']:
                    continue
                if d['thread'] and d['thread'].isRunning(): d['thread'].cancel()
                self.table.removeRow(row); self.downloads.remove(d)
                self.download_manager.jobs.pop(d['id'], None)
                if d['id'] in self.download_manager.queue: self.download_manager.queue.remove(d['id'])
                self.download_manager.persist()
                for other in self.downloads:
                    if other['row'] > row: other['row'] -= 1
        self.refresh_dashboard()

    def trigger_conversion(self, target_ext):
        record = self.selected_record()
        if record:
            self.start_conversion_for_record(record, target_ext)

    def start_conversion_for_record(self, record, target_ext):
        if not job_capabilities(record['job'])['convert'] or not conversion_supported(record.get('final_path', ''), target_ext, record.get('probe')):
            QMessageBox.information(self, "Convert", "This completed input cannot be converted to the selected output.")
            return False
        if bar := self.table.cellWidget(record['row'], 3): bar.setFormat(f"Converting to {target_ext.upper()}...")
        self.download_manager.set_state(record['id'], JobState.CONVERTING)
        popup = self.popups.get(record['id'])
        if popup:
            popup.set_job_state(JobState.CONVERTING.value)
            popup.set_details(f"State: starting\nTarget: {target_ext.upper()}\nSource is preserved.")
            popup.show()
        return self.conversion_controller.start(record['id'], record['final_path'], target_ext)

    def conversion_progress(self, row_id, snapshot):
        if d := self.get_download_by_id(row_id):
            percent = float(snapshot.get('percent') or 0)
            state = str(snapshot.get('state') or 'converting')
            if bar := self.table.cellWidget(d['row'], 3):
                bar.setValue(int(percent)); bar.setFormat(f"Paused {percent:.0f}%" if state == 'paused' else f"Converting {percent:.1f}%")
            if popup := self.popups.get(row_id):
                eta = format_eta(snapshot['eta']) if snapshot.get('eta') is not None else 'calculating'
                popup.set_job_state(state)
                popup.set_details(
                    f"Source: {snapshot.get('source', '')}\nDestination: {snapshot.get('destination', '')}\n"
                    f"Target: {snapshot.get('target', '')}\nState: {state}\n"
                    f"Progress: {percent:.1f}%\nElapsed: {format_eta(snapshot.get('elapsed') or 0)}\nETA: {eta}"
                )

    def conversion_done(self, row_id, success, msg, output_path):
        if d := self.get_download_by_id(row_id):
            bar = self.table.cellWidget(d['row'], 3)
            if not success:
                self.download_manager.set_state(row_id, JobState.COMPLETED, f"Conversion failure: {msg}")
                cancelled = 'cancelled' in str(msg).lower()
                if bar: bar.setFormat("Conversion cancelled" if cancelled else f"Conversion failed: {clean_error_summary(msg)}")
                if cancelled:
                    if popup := self.popups.get(row_id):
                        popup.set_job_state(JobState.CANCELLED.value)
                        popup.set_details('State: cancelled\nThe source and previous valid outputs were preserved. Incomplete temporary output was removed.')
                    QMessageBox.information(self, "Conversion Cancelled", "The original downloaded file remains available.")
                else:
                    if popup := self.popups.get(row_id):
                        popup.set_job_state('failed'); popup.set_details(f"State: failed\nResult: {clean_error_summary(msg)}")
                    QMessageBox.warning(self, "Conversion Failed", clean_error_summary(msg))
                self.start_queued_jobs()
                return
            try:
                converted_path = store_conversion_output(d, output_path)
            except (OSError, ValueError):
                self.download_manager.set_state(row_id, JobState.COMPLETED, 'Conversion failure: output missing or unsafe')
                if bar: bar.setFormat("Conversion output missing or unsafe")
                QMessageBox.warning(self, "Conversion Failed", "The conversion output is missing or outside the download folder.")
                self.start_queued_jobs()
                return
            self.download_manager.set_state(row_id, JobState.COMPLETED)
            if bar: bar.setFormat("Completed 100%")
            if popup := self.popups.get(row_id):
                popup.progress_bar.setValue(100)
                popup.set_job_state(JobState.COMPLETED.value)
                popup.set_details(f"State: completed\nConverted output: {converted_path}")
                popup.schedule_verified_close(lambda job_id=row_id, expected=popup: self.close_completed_popup(job_id, expected))
            self.save_downloads_to_file()
            self.start_queued_jobs()

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

def main(argv=None):
    runtime_config = initialize_runtime()
    app = QApplication.instance() or QApplication(list(argv) if argv is not None else sys.argv)
    app.setStyleSheet(MODERN_STYLE)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = StratrumDownloadStudio(runtime_config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
