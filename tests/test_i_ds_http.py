"""Offline, real-loopback Phase 2B HTTP transfer tests; no user files or internet."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import pytest
from ids_http_engine import (
    download_http_file, FileTransferPaused, FileTransferCancelled,
    FileTransferError, safe_file_name, check_public_url,
)

PAYLOAD = (b"0123456789" * 150000) + b"end"


class Handler(BaseHTTPRequestHandler):
    payload = PAYLOAD
    requests_seen = []
    def do_GET(self):
        kind = self.path.split("?", 1)[0]
        type(self).requests_seen.append((kind, self.headers.get("Range"), self.headers.get("If-Range")))
        if kind == "/missing":
            self.send_response(404); self.end_headers(); return
        if kind == "/redirect":
            self.send_response(302); self.send_header("Location", "/file.pdf"); self.end_headers(); return
        if kind == "/html":
            self.send_response(200); self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", "28"); self.end_headers()
            self.wfile.write(b"<html>not a file</html>     ")
            return
        blob = self.payload
        offset = 0
        header_range = self.headers.get("Range")
        if kind != "/no-range" and header_range and self.headers.get("If-Range") == '"data-v1"':
            offset = int(header_range.split("=")[1].split("-")[0])
        if offset:
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {offset if kind != '/bad-range' else offset+1}-{len(blob)-1}/{len(blob)}")
            blob = blob[offset:]
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", 'attachment; filename="example.pdf"')
        self.send_header("ETag", '"data-v1"')
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        for index in range(0, len(blob), 8096):
            try:
                self.wfile.write(blob[index:index+8096])
            except (ConnectionError, OSError):
                break

    def log_message(self, *args):
        pass


@contextmanager
def serve():
    Handler.requests_seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown(); server.server_close()
        thread.join(timeout=2)


def run(base, tmp_path, job="a"*32, **kwargs):
    return download_http_file(base + "/file.pdf", tmp_path, job, allow_local=True, retries=0, **kwargs)


def test_filename_safety():
    assert safe_file_name("../../setup.exe") == "setup.exe"
    assert safe_file_name("C:\\windows\\system32\\file.zip") == "file.zip"
    assert safe_file_name("CON.txt") == "_CON.txt"
    assert safe_file_name("document.pdf") == "document.pdf"
    assert safe_file_name("") == "download.bin"


def test_http_pdf_and_exclusive_duplicate_output(tmp_path):
    with serve() as base:
        first = run(base, tmp_path)
        second = run(base, tmp_path, job="b"*32)
        assert first.read_bytes() == second.read_bytes() == PAYLOAD
        assert first.name == "example.pdf" and second.name == "example (1).pdf"
        assert not list(tmp_path.glob("*.part"))
        assert not list(tmp_path.glob(".i-ds-*.json"))


def test_pause_and_byte_range_resume(tmp_path):
    with serve() as base:
        flag = {"paused": False}
        def progress(details):
            if details["downloaded"] > 40000:
                flag["paused"] = True
        with pytest.raises(FileTransferPaused):
            run(base, tmp_path, progress=progress, should_stop=lambda: "paused" if flag["paused"] else None)
        assert list(tmp_path.glob("*.part"))
        result = run(base, tmp_path)
        assert result.read_bytes() == PAYLOAD
        assert any(header and header.startswith("bytes=") for _, header, _ in Handler.requests_seen)


def test_server_ignoring_range_restarts_safely(tmp_path):
    with serve() as base:
        flag = {"pause": False}
        with pytest.raises(FileTransferPaused):
            download_http_file(base + "/no-range", tmp_path, "c"*32, allow_local=True, retries=0,
                progress=lambda details: flag.__setitem__("pause", details["downloaded"] > 40000),
                should_stop=lambda: "paused" if flag["pause"] else None)
        result = download_http_file(base + "/no-range", tmp_path, "c"*32, allow_local=True, retries=0)
        assert result.read_bytes() == PAYLOAD


def test_bad_content_range_rejected_and_partial_retained(tmp_path):
    with serve() as base:
        flag = {"pause": False}
        with pytest.raises(FileTransferPaused):
            download_http_file(base + "/bad-range", tmp_path, "d"*32, allow_local=True, retries=0,
                progress=lambda details: flag.__setitem__("pause", details["downloaded"] > 40000),
                should_stop=lambda: "paused" if flag["pause"] else None)
        with pytest.raises(FileTransferError, match="unexpected partial range"):
            download_http_file(base + "/bad-range", tmp_path, "d"*32, allow_local=True, retries=0)
        assert list(tmp_path.glob("*.part"))


def test_404_and_html_page_rejected(tmp_path):
    with serve() as base:
        with pytest.raises(FileTransferError, match="HTTP 404"):
            download_http_file(base + "/missing", tmp_path, "e"*32, allow_local=True, retries=0)
        with pytest.raises(FileTransferError, match="web page"):
            download_http_file(base + "/html", tmp_path, "f"*32, allow_local=True, retries=0)


def test_redirect_and_cancel_are_safe(tmp_path):
    with serve() as base:
        dest = download_http_file(base + "/redirect", tmp_path, "1"*32, allow_local=True, retries=0)
        assert dest.read_bytes() == PAYLOAD
        with pytest.raises(FileTransferCancelled):
            run(base, tmp_path, job="2"*32, should_stop=lambda: "cancelled")


def test_private_hosts_blocked_by_default():
    for url in ["http://127.0.0.1/x", "http://localhost/x", "file:///etc/passwd", "https://a:b@example.com/x"]:
        with pytest.raises(FileTransferError):
            check_public_url(url)
