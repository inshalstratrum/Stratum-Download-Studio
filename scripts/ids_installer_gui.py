"""I-DS installer UI for the existing self-contained Windows desktop application.

This is a packaging helper only, not a second downloader. No elevation or
deletion of downloads, browser profiles, or user configuration.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)


def asset(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def install_target():
    sandbox = os.environ.get("I_DS_TEST_INSTALLROOT")
    return Path(sandbox) if sandbox else Path(os.environ["LOCALAPPDATA"]) / "Programs" / "I-DS"


def matching_binary(source, destination):
    if not destination.is_file():
        return False
    def digest(path):
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.digest()
    return digest(source) == digest(destination)


def install_release(*, upgrade=False):
    exe = asset("I-DS.exe")
    script = asset("install_ids_windows.ps1")
    if not exe.is_file() or not script.is_file():
        raise RuntimeError("Installer payload is incomplete")
    target = install_target() / "I-DS.exe"
    command = [
        str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(script), "-SourceExe", str(exe), "-NoLaunch",
    ]
    if upgrade:
        command.append("-Upgrade")
    result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
    if result.returncode or not matching_binary(exe, target):
        summary = (result.stderr or result.stdout or "Installed binary verification failed").strip()
        raise RuntimeError(summary[-500:])
    return str(target)


class InstallationWorker(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, upgrade=False, parent=None):
        super().__init__(parent)
        self.upgrade = upgrade

    def run(self):
        try:
            self.succeeded.emit(install_release(upgrade=self.upgrade))
        except Exception as exc:
            self.failed.emit(str(exc))


class SetupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.installed = ""
        self.setWindowTitle("I-DS — Download Support Setup")
        icon = asset("i-ds.ico")
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self.setMinimumWidth(480)
        self.resize(570, 340)
        self.setStyleSheet("""
            QWidget { background:#f2f7fb; color:#163553; font-family:'Segoe UI'; }
            QLabel#heading { font-size:24px; font-weight:700; color:#103956; }
            QLabel#subtitle { font-size:13px; color:#42627a; }
            QLabel#notice { background:#e3f5f1; padding:13px; border:1px solid #96d8d1;
                            border-radius:10px; color:#1d5d63; }
            QPushButton { padding:12px 18px; border-radius:9px; font-weight:650; }
            QPushButton#install { background:#086f92; color:white; border:1px solid #055b7d; }
            QPushButton#install:hover { background:#0b82a8; }
            QPushButton#close { background:#ffffff; border:1px solid #c9d8e2; }
            QProgressBar { border:1px solid #c8dbe5; border-radius:7px;
                           background:#ffffff; height:12px; text-align:center; }
            QProgressBar::chunk { background:#087f91; border-radius:6px; }
        """)
        v=QVBoxLayout(self)
        v.setContentsMargins(28,25,28,24)
        v.setSpacing(15)
        logo=QLabel("I-DS  |  I.os Download Support")
        logo.setObjectName("heading")
        v.addWidget(logo)
        subtitle=QLabel("Tool by InShaLIve.os • One-click Windows installation")
        subtitle.setObjectName("subtitle")
        v.addWidget(subtitle)
        notice=QLabel("Installs for your Windows account. No admin access needed.\n"
                      "Downloads and settings are preserved.")
        notice.setObjectName("notice")
        notice.setWordWrap(True)
        v.addWidget(notice)
        self.status=QLabel("Ready to install.")
        self.status.setAccessibleName("Installation status")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        self.progress=QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        v.addWidget(self.progress)
        buttons=QHBoxLayout()
        buttons.addStretch(1)
        self.close_btn=QPushButton("Close")
        self.close_btn.setObjectName("close")
        self.close_btn.clicked.connect(self.close)
        buttons.addWidget(self.close_btn)
        self.install_btn=QPushButton("Install I-DS")
        self.install_btn.setObjectName("install")
        self.install_btn.clicked.connect(self.install_clicked)
        buttons.addWidget(self.install_btn)
        v.addLayout(buttons)

    def install_clicked(self):
        exists=(install_target() / "I-DS.exe").exists()
        if exists:
            result=QMessageBox.question(
                self,"Update existing I-DS",
                "An I-DS installation already exists. Back up its executable and install this version?\n"
                "Your downloaded files and preferences will not be removed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result!=QMessageBox.StandardButton.Yes:
                return
        self.install_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.status.setText("Installing and verifying I-DS...")
        self.progress.setVisible(True)
        self.progress.setRange(0,0)
        self.worker=InstallationWorker(upgrade=exists,parent=self)
        self.worker.succeeded.connect(self.installed_ok)
        self.worker.failed.connect(self.installed_error)
        self.worker.start()

    def installed_ok(self, path):
        self.installed=path
        self.progress.setVisible(False)
        self.status.setText("Installed successfully. You can open I-DS from the Start Menu.")
        self.install_btn.setText("Open I-DS")
        self.install_btn.clicked.disconnect()
        self.install_btn.clicked.connect(lambda: subprocess.Popen([self.installed],cwd=str(Path(self.installed).parent)))
        self.install_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

    def installed_error(self, reason):
        self.progress.setVisible(False)
        self.status.setText("Installation could not finish. No existing downloads were removed.")
        self.install_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        QMessageBox.warning(self,"I-DS installation",reason[:450])


def main():
    if "--verify-install-sandbox" in sys.argv:
        if not os.environ.get("I_DS_TEST_INSTALLROOT") or not os.environ.get("I_DS_TEST_SHORTCUTSROOT"):
            return 2
        report=os.environ.get("I_DS_TEST_RESULT")
        try:
            installed=install_release(upgrade=True)
            if report:
                Path(report).write_text("PASS:"+installed,encoding="utf-8")
            return 0
        except Exception as exc:
            if report:
                Path(report).write_text("FAIL:"+str(exc),encoding="utf-8")
            return 1
    app=QApplication(sys.argv)
    app.setFont(QFont("Segoe UI",10))
    window=SetupWindow()
    window.show()
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
