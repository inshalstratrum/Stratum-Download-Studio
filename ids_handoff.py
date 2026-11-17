"""One-shot Qt-to-HTTP handoff receipt.

A browser download is never cancelled on an HTTP 200 unless a desktop job
has actually entered its queue. Expired requests cannot be enqueued later.
"""
import threading


class HandoffReceipt:
    def __init__(self):
        self._lock = threading.Lock()
        self._event = threading.Event()
        self.status = "pending"

    def resolve(self, enqueue):
        with self._lock:
            if self.status != "pending":
                return False
            try:
                result = bool(enqueue())
            except Exception:
                result = False
            self.status = "accepted" if result else "rejected"
            self._event.set()
            return result

    def wait(self, timeout=5.0):
        self._event.wait(timeout)
        with self._lock:
            if self.status == "pending":
                self.status = "expired"
                self._event.set()
            return self.status == "accepted"
