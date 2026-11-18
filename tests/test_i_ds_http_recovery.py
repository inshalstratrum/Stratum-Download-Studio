"""Phase 2B.1 large-ish real socket tests, synthetic files only."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket, threading

import pytest

from ids_http_engine import download_http_file, FileTransferError, FileTransferPaused

DATA = (b"X-IDS-recovery-test\r\n" * 70000) + b"EOF"
NEW_DATA = (b"Y-IDS-changed-resource\r\n" * 70000) + b"NEW"

class RecoveryServer(BaseHTTPRequestHandler):
    attempts = {}
    seen = []
    lock = threading.Lock()
    version = 1

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        with self.lock:
            n = self.attempts.get(path, 0)
            self.attempts[path] = n + 1
            self.seen.append((path, self.headers.get("Range"), self.headers.get("If-Range")))
        if path == "/busy.zip" and n == 0:
            self.send_response(503); self.end_headers(); return
        blob = NEW_DATA if path == "/changed.zip" and n > 0 else DATA
        tag = '"v2"' if path == "/changed.zip" and n > 0 else '"v1"'
        start = 0
        request_range = self.headers.get("Range")
        if request_range and self.headers.get("If-Range") == tag:
            start = int(request_range.split("=", 1)[1].split("-", 1)[0])
            if start >= len(blob):
                self.send_response(416); self.end_headers(); return
        self.send_response(206 if start else 200)
        if start:
            self.send_header("Content-Range", f"bytes {start}-{len(blob)-1}/{len(blob)}")
        self.send_header("Content-Disposition", 'attachment; filename="archive.zip"')
        self.send_header("Content-Type", "application/zip")
        self.send_header("ETag", tag)
        self.send_header("Content-Length", str(len(blob) - start))
        self.end_headers()
        if path == "/flaky.zip" and n == 0:
            self.wfile.write(blob[:280000])
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        try:
            for pos in range(start, len(blob), 65536):
                self.wfile.write(blob[pos:pos+65536])
        except (OSError, ConnectionError):
            pass

    def log_message(self, *_):
        pass

@contextmanager
def server():
    RecoveryServer.attempts = {}
    RecoveryServer.seen = []
    host = ThreadingHTTPServer(("127.0.0.1", 0), RecoveryServer)
    t = threading.Thread(target=host.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{host.server_port}"
    finally:
        host.shutdown();host.server_close();t.join(timeout=2)


def test_interruption_partial_survives_then_byte_range_recovers(tmp_path):
    with server() as base:
        job = "b" * 32
        with pytest.raises(FileTransferError, match="interrupted|Incomplete"):
            download_http_file(base+"/flaky.zip", tmp_path, job, allow_local=True, retries=0)
        assert (tmp_path/f".i-ds-{job}.part").is_file()
        assert (tmp_path/f".i-ds-{job}.json").is_file()
        output = download_http_file(base+"/flaky.zip", tmp_path, job, allow_local=True, retries=0)
        assert output.read_bytes() == DATA
        assert any(name == "/flaky.zip" and rng and rng.startswith("bytes=") for name,rng,_ in RecoveryServer.seen)
        assert not (tmp_path/f".i-ds-{job}.part").exists()
        assert not (tmp_path/f".i-ds-{job}.json").exists()


def test_transient_server_error_retries_and_succeeds(tmp_path):
    with server() as base:
        output = download_http_file(base+"/busy.zip", tmp_path, "c"*32, allow_local=True, retries=2)
        assert output.read_bytes() == DATA
        assert RecoveryServer.attempts["/busy.zip"] == 2


def test_changed_validator_restarts_instead_of_appending_old_bytes(tmp_path):
    with server() as base:
        paused = {"yes": False}
        job = "d" * 32
        with pytest.raises(FileTransferPaused):
            download_http_file(
                base+"/changed.zip",tmp_path,job,allow_local=True,retries=0,
                progress=lambda event: paused.update(yes=event["downloaded"] > 30000),
                should_stop=lambda: "paused" if paused["yes"] else None)
        output = download_http_file(base+"/changed.zip",tmp_path,job,allow_local=True,retries=0)
        assert output.read_bytes() == NEW_DATA
        assert any(name == "/changed.zip" and rng for name,rng,_ in RecoveryServer.seen)


def test_parallel_downloads_create_unique_outputs_without_overwrite(tmp_path):
    with server() as base:
        jobs = ["%032x" % i for i in range(1,5)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            outputs = list(pool.map(
                lambda job: download_http_file(base+"/files.zip",tmp_path,job,allow_local=True,retries=0), jobs))
        assert len({str(x) for x in outputs}) == 4
        assert all(x.read_bytes() == DATA for x in outputs)
        assert not list(tmp_path.glob(".i-ds-*.part"))
