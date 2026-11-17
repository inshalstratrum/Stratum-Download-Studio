"""Synthetic Qt queue + real local HTTP transfer + acknowledged browser handoff."""
import io
import json
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QMessageBox

import stratum_download_studio as studio
import ids_http_qt
import ids_http_engine
from ids_handoff import HandoffReceipt

app = QApplication.instance() or QApplication([])

DATA = b"%PDF-1.4\n" + b"Phase2B" * 30000 + b"\n%%EOF"


class LocalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/manual.pdf":
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(DATA)))
        self.send_header("ETag", '"qt-test"')
        self.end_headers()
        try:
            self.wfile.write(DATA)
        except (OSError, ConnectionError):
            pass
    def log_message(self, *args):
        pass


def test_receipt_expiration_never_enqueues():
    receipt = HandoffReceipt()
    assert receipt.wait(0.001) is False
    calls = []
    assert receipt.resolve(lambda: calls.append(1) or True) is False
    assert not calls


def test_valid_file_bridge_waits_for_acceptance(tmp_path):
    conf = studio.initialize_runtime(tmp_path / "config", auth_token="b" * 64,
                                     allowed_origin="chrome-extension://" + "a" * 32)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), studio.DownloadServerHandler)
    httpd.app_config = conf
    collected = []
    class AcceptedSignal:
        def emit(self, url, context, hint, receipt):
            collected.append((url, hint))
            receipt.resolve(lambda: True)
    httpd.file_signal = AcceptedSignal()
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    body = json.dumps({"url": "https://example.com/manual.pdf", "action": "http_download",
                       "fileName": "..\\..\\folder\\manual.pdf"}).encode()
    req = request.Request(f"http://127.0.0.1:{httpd.server_port}/add_download",
             data=body, method="POST", headers={
                 "X-Stratrum-Auth": "b" * 64,
                 "Origin": "chrome-extension://" + "a" * 32,
                 "Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=3) as response:
            assert response.status == 200
            assert json.loads(response.read())["status"] == "success"
        assert collected == [("https://example.com/manual.pdf", "manual.pdf")]
    finally:
        httpd.shutdown(); httpd.server_close(); t.join(timeout=3)


def test_gui_file_job_downloads_into_synthetic_folder(tmp_path, monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
    local_server = threading.Thread(target=server.serve_forever, daemon=True)
    local_server.start()
    synthetic = tmp_path / "downloads"
    synthetic.mkdir()
    runtime = studio.initialize_runtime(tmp_path / "synthetic-state", auth_token="c" * 64)
    monkeypatch.setattr(studio.StratrumDownloadStudio, "init_server", lambda self: None)
    monkeypatch.setattr(studio, "validate_url", lambda url: (True, ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Close)
    real_download = ids_http_engine.download_http_file
    monkeypatch.setattr(ids_http_qt, "download_http_file",
                        lambda *args, **kw: real_download(*args, **kw, allow_local=True))
    window = studio.StratrumDownloadStudio(runtime)
    url = f"http://127.0.0.1:{server.server_port}/manual.pdf"
    try:
        assert window.start_http_download(url, synthetic, "manual.pdf") is True
        deadline = time.monotonic() + 9
        while time.monotonic() < deadline:
            app.processEvents()
            jobs = list(window.download_manager.jobs.values())
            if jobs and jobs[-1].state in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert jobs and jobs[-1].state == "completed", jobs[-1].error_summary if jobs else "no job"
        assert (synthetic / "manual.pdf").read_bytes() == DATA
        assert window.table.rowCount() == 1
        assert window.table.item(0, 0).text() == "manual.pdf"
        assert not list(synthetic.glob("*.part"))
        app.processEvents()
        assert runtime.history_path.exists() or window.download_manager.queue_path.exists()
    finally:
        window.tray_icon.hide()
        for record in window.downloads:
            t = record.get("thread")
            if t and t.isRunning():
                t.wait(4000)
        window.hide()
        server.shutdown(); server.server_close(); local_server.join(timeout=3)


def test_paused_file_job_recovers_without_media_format_lookup(tmp_path, monkeypatch):
    runtime = studio.initialize_runtime(tmp_path / "recovery-data", auth_token="d"*64)
    downloads = tmp_path / "recovery-files"
    downloads.mkdir()
    manager = studio.DownloadManager(runtime)
    saved = studio.DownloadJob(
        job_id="f"*32, source_url="https://example.org/archive.zip",
        save_dir=str(downloads), requested_format="FILE",
        file_name_hint="archive.zip", state=studio.JobState.PAUSED.value,
    )
    manager.add_job(saved)
    monkeypatch.setattr(studio.StratrumDownloadStudio, "init_server", lambda self: None)
    window = studio.StratrumDownloadStudio(runtime)
    try:
        restored = window.get_download_by_id(saved.job_id)
        assert restored is not None
        assert restored["format"] == "FILE"
        assert restored["job"].file_name_hint == "archive.zip"
        assert restored["job"].state == "paused"
        assert window.table.rowCount() == 1
    finally:
        window.tray_icon.hide()
        window.hide()
