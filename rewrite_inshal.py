import os
import re

file_path = 'e:/Inshal/Personal IDM/inshal_dm.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Token and Config Handling
token_replacement = '''import string
import threading
import time

def validate_token(token):
    return isinstance(token, str) and len(token) == 64 and all(c in string.hexdigits for c in token)

def get_or_create_config():
    config_path = os.path.join(get_appdata_dir(), 'config', 'config.json')
    config_dir = os.path.dirname(config_path)
    os.makedirs(config_dir, exist_ok=True)
    
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception:
            pass

    token = config.get('auth_token', '')
    if not validate_token(token):
        token = secrets.token_hex(32)
        config['auth_token'] = token
        
    allowed_origin = config.get('allowed_origin', '')
    config['allowed_origin'] = allowed_origin

    fd, tmp_path = tempfile.mkstemp(dir=config_dir, prefix="cfg_", suffix=".tmp")
    with os.fdopen(fd, 'w') as f:
        json.dump(config, f)
    os.replace(tmp_path, config_path)
    
    return config

def update_allowed_origin(origin):
    global ALLOWED_ORIGIN
    ALLOWED_ORIGIN = origin
    config_path = os.path.join(get_appdata_dir(), 'config', 'config.json')
    try:
        with open(config_path, 'r') as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg['allowed_origin'] = origin
    cfg['auth_token'] = AUTH_TOKEN
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(config_path), prefix="cfg_", suffix=".tmp")
    with os.fdopen(fd, 'w') as f:
        json.dump(cfg, f)
    os.replace(tmp_path, config_path)

config = get_or_create_config()
AUTH_TOKEN = config['auth_token']
ALLOWED_ORIGIN = config['allowed_origin']

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

rate_limiter = RateLimiter(5, 1.0)

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

def validate_request(headers, rfile):
    if not rate_limiter.allow():
        return 429, b'{"error": "Too many requests"}'
        
    auth_header = headers.get('X-Stratrum-Auth', '')
    if not secrets.compare_digest(auth_header, AUTH_TOKEN):
        return 401, b'{"error": "Unauthorized"}'
        
    origin = headers.get('Origin', '')
    global ALLOWED_ORIGIN
    if not ALLOWED_ORIGIN and origin.startswith(('chrome-extension://', 'moz-extension://', 'extension://')):
        update_allowed_origin(origin)
    elif origin != ALLOWED_ORIGIN:
        return 403, b'{"error": "Origin not allowed"}'
        
    if headers.get('Content-Type') != 'application/json':
        return 415, b'{"error": "Unsupported Media Type"}'

    try:
        content_length = int(headers.get('Content-Length', -1))
    except ValueError:
        return 400, b'{"error": "Invalid Content-Length"}'

    if content_length < 0:
        return 400, b'{"error": "Missing or negative Content-Length"}'
    if content_length > 16384:
        return 413, b'{"error": "Payload too large"}'

    try:
        post_data = rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
    except UnicodeDecodeError:
        return 400, b'{"error": "Invalid UTF-8"}'
    except json.JSONDecodeError:
        return 400, b'{"error": "Malformed JSON"}'
        
    url = data.get('url', '')
    is_valid, err_msg = validate_url(url)
    if not is_valid:
        return 400, json.dumps({"error": err_msg}).encode('utf-8')
        
    return 200, url
'''

content = re.sub(
    r"def get_or_create_token\(\).*?HISTORY_FILE = os\.path\.join\(get_appdata_dir\(\), 'history', 'history\.json'\)",
    token_replacement + "\nHISTORY_FILE = os.path.join(get_appdata_dir(), 'history', 'history.json')",
    content,
    flags=re.DOTALL
)

# 2. Update HTTP Handler
server_replacement = '''class IDMServerHandler(http.server.BaseHTTPRequestHandler):
    def send_cors_headers(self):
        origin = self.headers.get('Origin', '')
        if origin == ALLOWED_ORIGIN or (not ALLOWED_ORIGIN and origin.startswith(('chrome-extension://', 'moz-extension://', 'extension://'))):
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Stratrum-Auth')
        
    def do_OPTIONS(self):
        self.send_response(200); self.send_cors_headers(); self.end_headers()
        
    def do_POST(self):
        if self.path != '/add_download':
            self.send_response(404); self.end_headers(); return
            
        status_code, result = validate_request(self.headers, self.rfile)
        
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
    def run(self):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 8000), IDMServerHandler)
        self.httpd.url_signal = self.url_received
        self.httpd.serve_forever()
    def stop(self):
        if hasattr(self, 'httpd'):
            self.httpd.shutdown()
            self.httpd.server_close()'''

content = re.sub(
    r"class IDMServerHandler\(http\.server\.BaseHTTPRequestHandler\):.*?self\.httpd\.serve_forever\(\)",
    server_replacement,
    content,
    flags=re.DOTALL
)

# 3. Update File Handling & Safety
file_safety = '''def is_dangerous_file(filepath):
        unsafe_exts = {'.exe', '.msi', '.bat', '.cmd', '.com', '.scr', '.ps1', '.vbs', '.js', '.jar', '.lnk', '.reg'}
        _, ext = os.path.splitext(filepath)
        return ext.lower() in unsafe_exts

    def open_selected_file(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                if d.get('final_path') and os.path.exists(d['final_path']):
                    if self.is_dangerous_file(d['final_path']):
                        QMessageBox.warning(self, "Security Warning", "Execution of downloaded dangerous file types is disabled for your safety. Use 'Open Folder' instead.")
                        return
                    os.startfile(d['final_path'])

    def open_selected_folder(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                if d.get('final_path'):
                    norm_path = os.path.normpath(d["final_path"])
                    if os.path.exists(norm_path):
                        subprocess.Popen(['explorer', '/select,', norm_path])
                    else:
                        QMessageBox.warning(self, "Error", "File does not exist.")'''

content = re.sub(
    r"def check_safe_file.*?subprocess\.Popen\(\['explorer', '/select,', os\.path\.normpath\(d\[\"final_path\"\]\)\]\)",
    file_safety,
    content,
    flags=re.DOTALL
)

# Update shutdown in main app
content = content.replace("def force_quit(self):\n        self.save_downloads_to_file(); QApplication.quit()",
                          "def force_quit(self):\n        self.save_downloads_to_file(); self.server_thread.stop(); self.server_thread.wait(); QApplication.quit()")

# 4. Remove ffmpeg -y
content = content.replace("['-y', '-i'", "['-i'")

# 5. Safe Filename generation
safe_name_func = '''import re
def generate_safe_filename(save_dir, title, ext):
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 
                'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    
    title = re.sub(r'[\x00-\x1f\\\\/:*?"<>|]', '_', title)
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
'''
content = content.replace("import yt_dlp", "import yt_dlp\n" + safe_name_func)

# Fix start_new_download to use safe filename
download_opts = '''download_id = uuid.uuid4().hex
        
        if target_ext in ["MP3", "WAV", "FLAC", "M4A"]: format_str = 'bestaudio/best'
        elif target_ext == "MP4": format_str = {0: 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 1: 'bestvideo[height<=1080][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 2: 'bestvideo[height<=720][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 3: 'bestvideo[height<=480][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best'}.get(quality_idx, 'best')
        else: format_str = {0: 'bestvideo+bestaudio/best', 1: 'bestvideo[height<=1080]+bestaudio/best', 2: 'bestvideo[height<=720]+bestaudio/best', 3: 'bestvideo[height<=480]+bestaudio/best'}.get(quality_idx, 'best')

        outtmpl = os.path.join(save_dir, '%(title)s.%(ext)s') # yt-dlp will handle template, but we post-process filename'''
content = content.replace('''download_id = uuid.uuid4().hex
        outtmpl = os.path.join(save_dir, '%(title)s.%(ext)s')
        
        if target_ext in ["MP3", "WAV", "FLAC", "M4A"]: format_str = 'bestaudio/best'
        elif target_ext == "MP4": format_str = {0: 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 1: 'bestvideo[height<=1080][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 2: 'bestvideo[height<=720][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 3: 'bestvideo[height<=480][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best'}.get(quality_idx, 'best')
        else: format_str = {0: 'bestvideo+bestaudio/best', 1: 'bestvideo[height<=1080]+bestaudio/best', 2: 'bestvideo[height<=720]+bestaudio/best', 3: 'bestvideo[height<=480]+bestaudio/best'}.get(quality_idx, 'best')''', download_opts)

download_thread_run = '''            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                title = info.get('title', 'download')
                
            safe_final_path = generate_safe_filename(os.path.dirname(self.outtmpl), title, self.target_ext)
            
            if self.final_filename and os.path.exists(self.final_filename):
                os.replace(self.final_filename, safe_final_path)
                self.final_filename = safe_final_path

            if os.path.exists(self.final_filename):
                self.size_updated.emit(self.id, os.path.basename(self.final_filename), self.format_size(os.path.getsize(self.final_filename)))'''

content = re.sub(
    r"with yt_dlp\.YoutubeDL\(ydl_opts\) as ydl: ydl\.download\(\[self\.url\]\).*?self\.format_size\(os\.path\.getsize\(self\.final_filename\)\)\)",
    download_thread_run,
    content,
    flags=re.DOTALL
)

# Remove "IDM Clone" and "EXACT IDM GUI REPLICAS"
content = content.replace("Inshal DM - Professional Download Manager", "Stratrum Download Studio")
content = content.replace("Inshal DM", "Stratrum Download Studio")
content = content.replace("EXACT IDM GUI REPLICAS", "STRATRUM DOWNLOAD STUDIO UI")
content = content.replace("Sent to IDM Clone", "Sent to Stratrum")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
