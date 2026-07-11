import pytest
import os
import json
import tempfile
import threading
import urllib.request
import urllib.error
import urllib.parse
from http.server import ThreadingHTTPServer
import sys
import time
import subprocess

# Mock PyQt6 to avoid headless errors
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

import inshal_dm
from inshal_dm import IDMServerHandler

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    old_auth = getattr(inshal_dm, 'AUTH_TOKEN', '')
    old_origin = getattr(inshal_dm, 'ALLOWED_ORIGIN', '')
    old_history = getattr(inshal_dm, 'HISTORY_FILE', '')

    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

    inshal_dm.rate_limiter.allowance = inshal_dm.rate_limiter.rate
    inshal_dm.rate_limiter.last_check = time.monotonic()

    inshal_dm.AUTH_TOKEN = 'b' * 64
    inshal_dm.ALLOWED_ORIGIN = 'chrome-extension://valid'
    inshal_dm.HISTORY_FILE = str(tmp_path / 'history.json')

    yield

    inshal_dm.AUTH_TOKEN = old_auth
    inshal_dm.ALLOWED_ORIGIN = old_origin
    inshal_dm.HISTORY_FILE = old_history


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), IDMServerHandler)
    port = httpd.server_port

    class MockServer:
        def emit(self, url): pass
    httpd.url_signal = MockServer()

    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()

    yield port

    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=1.0)

def do_request(port, data=None, headers=None, method='POST', path='/add_download'):
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data is not None:
        if isinstance(data, str):
            data = data.encode('utf-8')
    try:
        with urllib.request.urlopen(req, data=data, timeout=2) as response:
            return response.status, response.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore')

def test_successful_authenticated_request(server):
    headers = {
        'X-Stratrum-Auth': inshal_dm.AUTH_TOKEN,
        'Content-Type': 'application/json; charset=utf-8',
        'Origin': inshal_dm.ALLOWED_ORIGIN
    }
    data = json.dumps({"url": "https://example.com/video.mp4"})
    status, body = do_request(server, data=data, headers=headers)
    assert status == 200

def test_missing_token(server):
    headers = {'Content-Type': 'application/json', 'Origin': inshal_dm.ALLOWED_ORIGIN}
    status, body = do_request(server, data="{}", headers=headers)
    assert status == 401

def test_unapproved_origin(server):
    headers = {
        'X-Stratrum-Auth': inshal_dm.AUTH_TOKEN,
        'Content-Type': 'application/json',
        'Origin': 'chrome-extension://invalid'
    }
    status, body = do_request(server, data="{}", headers=headers)
    assert status == 403

def test_invalid_utf8_failure(server):
    headers = {
        'X-Stratrum-Auth': inshal_dm.AUTH_TOKEN,
        'Content-Type': 'application/json',
        'Origin': inshal_dm.ALLOWED_ORIGIN,
        'Content-Length': '3'
    }
    url = f"http://127.0.0.1:{server}/add_download"
    req = urllib.request.Request(url, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, data=b"\xff\xfe\x00", timeout=2) as response:
            status = response.status
            body = response.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode('utf-8', errors='ignore')

    assert status == 400
    assert "Invalid UTF-8" in body

def test_atomic_config_replacement(tmp_path):
    config = inshal_dm.get_or_create_config()
    assert 'auth_token' in config
    assert 'allowed_origin' in config
    cfg_path = os.path.join(inshal_dm.get_appdata_dir(), 'config', 'config.json')
    assert os.path.exists(cfg_path)

def test_corrupt_config_regeneration(tmp_path):
    cfg_path = os.path.join(inshal_dm.get_appdata_dir(), 'config', 'config.json')
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, 'w') as f:
        f.write("{corrupted json}")

    config = inshal_dm.get_or_create_config()
    assert len(config['auth_token']) == 64

def test_first_use_origin_pairing(server):
    inshal_dm.ALLOWED_ORIGIN = ''
    headers = {
        'X-Stratrum-Auth': inshal_dm.AUTH_TOKEN,
        'Content-Type': 'application/json',
        'Origin': 'chrome-extension://neworigin'
    }
    status, body = do_request(server, data=json.dumps({"url": "https://example.com"}), headers=headers)
    assert status == 200
    assert inshal_dm.ALLOWED_ORIGIN == 'chrome-extension://neworigin'

def test_unsuccessful_request_does_not_pair_origin(server):
    inshal_dm.ALLOWED_ORIGIN = ''
    headers = {
        'X-Stratrum-Auth': 'badtoken',
        'Content-Type': 'application/json',
        'Origin': 'chrome-extension://malicious'
    }
    status, body = do_request(server, data="{}", headers=headers)
    assert status == 401
    assert inshal_dm.ALLOWED_ORIGIN == ''

def test_rate_limiter_does_not_punish_invalid_requests(server):
    headers = {
        'X-Stratrum-Auth': 'badtoken',
        'Content-Type': 'application/json',
        'Origin': inshal_dm.ALLOWED_ORIGIN
    }
    for _ in range(6):
        status, body = do_request(server, data="{}", headers=headers)
        assert status == 401

    headers['X-Stratrum-Auth'] = inshal_dm.AUTH_TOKEN
    status, body = do_request(server, data=json.dumps({"url": "https://example.com"}), headers=headers)
    assert status == 200

def test_open_safe_file(tmp_path):
    app = inshal_dm.InshalDM()
    safe_file = tmp_path / "test.mp4"
    safe_file.touch()
    assert not app.is_dangerous_file(str(safe_file))

def test_open_dangerous_file(tmp_path):
    app = inshal_dm.InshalDM()
    danger_file = tmp_path / "test.exe"
    danger_file.touch()
    assert app.is_dangerous_file(str(danger_file))

def test_converter_unique_output(tmp_path):
    f1 = inshal_dm.generate_safe_filename(str(tmp_path), "vid", "mp4")
    with open(f1, 'w') as f: f.write("")
    f2 = inshal_dm.generate_safe_filename(str(tmp_path), "vid", "mp4")
    assert f2.endswith("vid_1.mp4")

def test_converter_no_overwrite(tmp_path, monkeypatch):
    input_vid = tmp_path / "in.mp4"
    input_vid.touch()

    class MockProcess:
        returncode = 0

    def mock_run(args, **kwargs):
        assert '-y' not in args
        return MockProcess()

    monkeypatch.setattr(subprocess, "run", mock_run)

    t = inshal_dm.ConvertThread("0", str(input_vid), "mp3")
    t.run()

def test_no_check_safe_file_or_idm_references():
    with open('inshal_dm.py', 'r', encoding='utf-8') as f:
        content = f.read()
        assert 'check_safe_file' not in content
        assert 'IDM Clone' not in content
        assert 'FFmpeg -y' not in content
