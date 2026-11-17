"""Qt signals adapter for job-scoped I-DS HTTP file transfers."""
from __future__ import annotations
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from ids_http_engine import download_http_file, FileTransferPaused, FileTransferCancelled


def display_bytes(amount):
    amount = float(max(0, amount))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024


class FileDownloadThread(QThread):
    progress = pyqtSignal(str, str, float, str, str, str, str, str)
    status = pyqtSignal(str, str)
    result_ready = pyqtSignal(str, bool, str, str)
    size_updated = pyqtSignal(str, str, str)
    metrics = pyqtSignal(str, int, int, float, object)

    def __init__(self, id, url, save_dir, filename_hint="", speed_limit_bps=0):
        super().__init__()
        self.id = id
        self.url = url
        self.save_dir = str(Path(save_dir).resolve())
        self.filename_hint = filename_hint
        self.speed_limit_bps = max(0, int(speed_limit_bps or 0))
        self.cancelled = False
        self.paused = False
        self.final_probe = {}
        self.temporary_paths = {str(Path(save_dir) / f".i-ds-{id}.part")}
        self.resolved_media_url = ""
        self._has_started = False
        self._state_lock = threading.Lock()

    def cancel(self):
        with self._state_lock:
            self.cancelled = True
        self.requestInterruption()

    def set_speed_limit(self, bytes_per_second):
        with self._state_lock:
            self.speed_limit_bps = max(0, int(bytes_per_second or 0))

    def _stop(self):
        with self._state_lock:
            if self.cancelled or self.isInterruptionRequested():
                return "cancelled"
            if self.paused:
                return "paused"
        return None

    def _progress(self, details):
        if not self._has_started and details.get("state") == "downloading":
            self._has_started = True
            self.status.emit(self.id, "Downloading")
        downloaded = details["downloaded"]
        total = details.get("total") or 0
        speed = details.get("speed") or 0
        eta = details.get("eta")
        name = details.get("name") or "File download"
        pct = min(100, (100 * downloaded / total)) if total else 0
        self.metrics.emit(self.id, int(downloaded), int(total), float(speed), eta)
        self.progress.emit(
            self.id, name, pct, display_bytes(downloaded),
            display_bytes(total) if total else "N/A", display_bytes(speed) + "/s",
            f"{eta // 60:02d}:{eta % 60:02d}" if isinstance(eta, int) else "--:--",
            "Downloading" if details.get("state") == "downloading" else "Completed",
        )

    def run(self):
        self.status.emit(self.id, "Connecting")
        try:
            path = download_http_file(
                self.url, self.save_dir, self.id,
                filename_hint=self.filename_hint,
                progress=self._progress,
                should_stop=self._stop,
                get_speed_limit=lambda: self.speed_limit_bps,
            )
            if self._stop():
                # A late cancel after exclusive promotion must not destroy a valid output.
                self.status.emit(self.id, "Completed")
            size = path.stat().st_size
            self.metrics.emit(self.id, size, size, 0.0, 0)
            self.size_updated.emit(self.id, path.name, display_bytes(size))
            self.status.emit(self.id, "Completed")
            self.result_ready.emit(self.id, True, "", str(path))
        except FileTransferPaused:
            self.status.emit(self.id, "Paused")
        except FileTransferCancelled:
            self.status.emit(self.id, "Cancelled")
            self.result_ready.emit(self.id, False, "Cancelled", "")
        except Exception as exc:
            self.status.emit(self.id, "Failed")
            # Never include signed URLs or network credentials in user-facing errors.
            self.result_ready.emit(self.id, False, str(exc), "")
