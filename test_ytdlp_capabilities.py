import http.server
from pathlib import Path
import threading

import stratum_dependency_policy as policy

policy.load_controlled_yt_dlp()

import brotli
from Cryptodome.Cipher import AES
import curl_cffi.requests
import mutagen
import requests
from websockets.sync.client import connect
from websockets.sync.server import serve

def test_brotli_and_requests_urllib3_local_network_path():
    payload = b'controlled local brotli fixture'

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = brotli.compress(payload)
            self.send_response(200)
            self.send_header('Content-Encoding', 'br')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = requests.get(f'http://127.0.0.1:{server.server_port}/fixture', timeout=5)
        assert response.content == payload
        assert response.raw.version == 10
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_websocket_local_deterministic_echo():
    with serve(lambda websocket: websocket.send(websocket.recv()), '127.0.0.1', 0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.socket.getsockname()[1]
            with connect(f'ws://127.0.0.1:{port}') as websocket:
                websocket.send('controlled')
                assert websocket.recv() == 'controlled'
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_curl_cffi_impersonation_available_but_not_globally_forced():
    assert any(name.startswith('chrome') for name in dir(curl_cffi.requests.BrowserType))
    options = policy.controlled_yt_dlp_options()
    assert 'impersonate' not in options


def test_cryptodome_aes128_non_drm_fixture():
    key = bytes(range(16))
    iv = bytes(range(16, 32))
    plaintext = b'authorized-hls!!'
    ciphertext = AES.new(key, AES.MODE_CBC, iv).encrypt(plaintext)
    assert AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext) == plaintext


def test_mutagen_and_ejs_capability_payloads_load():
    import yt_dlp_ejs

    assert mutagen.version_string == '1.48.1'
    assert Path(yt_dlp_ejs.__file__).resolve().is_relative_to(
        (Path(__file__).resolve().parent / '.deps').resolve())
