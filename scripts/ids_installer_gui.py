"""I-DS native Windows installer with optional browser-setup guidance.

Private per-user setup only. No browser profile modifications, elevations,
secret transfers, app migrations, or automatic extension installations.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)


def asset(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def install_target():
    sandbox = os.environ.get("I_DS_TEST_INSTALLROOT")
    return Path(sandbox) if sandbox else Path(os.environ["LOCALAPPDATA"]) / "Programs" / "I-DS"


def extension_target():
    return install_target() / "Browser Extension"


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
    if not os.environ.get("I_DS_TEST_INSTALLROOT") and not (
        asset("browser_extension") / "manifest.json"
    ).is_file():
        raise RuntimeError("The browser extension files are missing from this installer")

    target = install_target() / "I-DS.exe"
    command = [
        str(Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(script), "-SourceExe", str(exe), "-NoLaunch",
    ]
    if upgrade:
        command.append("-Upgrade")
    result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
    if result.returncode or not matching_binary(exe, target):
        summary = (result.stderr or result.stdout or "Installed binary verification failed").strip()
        raise RuntimeError(summary[-500:])
    if not os.environ.get("I_DS_TEST_INSTALLROOT") and not (
        extension_target() / "manifest.json"
    ).is_file():
        raise RuntimeError("The desktop app was installed, but its browser extension was not.")
    return str(target)


def browser_executable(browser):
    if browser not in ("chrome", "edge"):
        return None
    rel = "Google/Chrome/Application/chrome.exe" if browser == "chrome" else "Microsoft/Edge/Application/msedge.exe"
    for root in (os.environ.get("ProgramFiles", ""),
                 os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("LOCALAPPDATA", "")):
        if root:
            candidate = Path(root) / Path(rel)
            if candidate.is_file():
                return candidate
    return None


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
        self.launching = False
        self.setWindowTitle("I-DS - Download Support Setup")
        icon = asset("stratum-download-studio.ico")
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self.setMinimumWidth(480)
        self.resize(580, 380)
        self.setStyleSheet("""
            QWidget { background:#f2f7fb; color:#163553; font-family:'Segoe UI'; }
            QLabel#heading { font-size:23px; font-weight:700; color:#103956; }
            QLabel#subtitle { font-size:13px; color:#42627a; }
            QLabel#notice { background:#e3f5f1; padding:10px; border:1px solid #96d8d1;
                            border-radius:9px; color:#1d5d63; }
            QGroupBox { border:1px solid #b9d4e0; border-radius:9px; margin-top:11px;
                        padding:12px 8px 8px 8px; background:#fff; font-weight:600; }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 4px; }
            QPushButton { padding:9px 12px; border-radius:8px; font-weight:600; min-height:28px; }
            QPushButton#install { background:#086f92; color:white; border:1px solid #055b7d; }
            QPushButton#install:hover { background:#0b82a8; }
            QPushButton#close { background:#ffffff; border:1px solid #c9d8e2; }
            QPushButton:focus { border:2px solid #cf9d30; }
            QProgressBar { border:1px solid #c8dbe5; border-radius:7px;
                           background:#ffffff; height:12px; text-align:center; }
            QProgressBar::chunk { background:#087f91; border-radius:6px; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 17, 22, 19)
        root.setSpacing(9)
        heading = QLabel("I-DS | I.os Download Support")
        heading.setObjectName("heading")
        root.addWidget(heading)
        subtitle = QLabel("Tool by InShaLIve.os | One-click Windows installation")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)
        notice = QLabel("Installs for your Windows account. No admin access needed.\n"
                        "Downloads and settings are preserved.")
        notice.setObjectName("notice")
        notice.setWordWrap(True)
        root.addWidget(notice)
        self.status = QLabel("Ready to install.")
        self.status.setAccessibleName("Installation status")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress)

        self.browser_group = QGroupBox("Next: Connect Chrome or Edge")
        browser_layout = QVBoxLayout(self.browser_group)
        steps = QLabel(
            "1. Open the extension folder and Chrome or Edge extensions page.\n"
            "2. Enable Developer mode > Load unpacked > select this folder.\n"
            "3. In I-DS, use Options > Browser Integration > Copy Token,\n"
            "   then click Connect with copied token in the extension settings."
        )
        steps.setWordWrap(True)
        steps.setAccessibleName("Browser companion setup instructions")
        browser_layout.addWidget(steps)
        folder_button = QPushButton("Open Extension Folder")
        folder_button.setAccessibleName("Show the installed I-DS browser extension files")
        folder_button.clicked.connect(self.open_extension_folder)
        browser_layout.addWidget(folder_button)
        browsers = QHBoxLayout()
        for browser in ("chrome", "edge"):
            button = QPushButton("Set Up " + browser.title())
            button.setAccessibleName("Open " + browser.title() + " extensions page")
            button.clicked.connect(lambda checked=False, kind=browser: self.open_browser_page(kind))
            browsers.addWidget(button)
        browser_layout.addLayout(browsers)
        self.browser_group.hide()
        root.addWidget(self.browser_group)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("close")
        self.close_btn.clicked.connect(self.close)
        actions.addWidget(self.close_btn)
        self.install_btn = QPushButton("Install I-DS")
        self.install_btn.setObjectName("install")
        self.install_btn.clicked.connect(self.install_clicked)
        actions.addWidget(self.install_btn)
        root.addLayout(actions)

    def install_clicked(self):
        exists = (install_target() / "I-DS.exe").exists()
        if exists:
            answer = QMessageBox.question(
                self, "Update existing I-DS",
                "An I-DS installation already exists. Back up its executable and update it?\n"
                "Your downloads and settings will be preserved.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.install_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.status.setText("Installing and verifying I-DS...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.worker = InstallationWorker(upgrade=exists, parent=self)
        self.worker.succeeded.connect(self.installed_ok)
        self.worker.failed.connect(self.installed_error)
        self.worker.start()

    def installed_ok(self, path):
        self.installed = path
        self.progress.setVisible(False)
        self.status.setText("Installed successfully. Connect a browser below or open I-DS now.\n"
                            "Your downloads and settings were preserved.")
        self.browser_group.setVisible(True)
        self.install_btn.setText("Open I-DS")
        self.install_btn.clicked.disconnect()
        self.install_btn.clicked.connect(self.launch_installed)
        self.install_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        self.resize(max(580, self.width()), max(490, self.height()))
        self.install_btn.setFocus()

    def launch_installed(self):
        if self.launching or not self.installed:
            return
        self.launching = True
        try:
            subprocess.Popen([self.installed], cwd=str(Path(self.installed).parent), close_fds=True)
        except OSError as exc:
            self.launching = False
            QMessageBox.warning(self, "Could Not Open I-DS", str(exc)[:350])
            return
        self.close()  # one click opens app, no lingering installer

    def open_extension_folder(self):
        folder = extension_target()
        if not (folder / "manifest.json").is_file():
            QMessageBox.warning(self, "Extension Not Found", "Reinstall I-DS to restore the browser extension files.")
            return
        try:
            os.startfile(str(folder))
        except OSError:
            QMessageBox.warning(self, "Cannot Open Folder", "Open this folder in File Explorer:\n" + str(folder))

    def open_browser_page(self, browser):
        executable = browser_executable(browser)
        if executable is None:
            QMessageBox.warning(self, "Browser Not Found", browser.title() + " is not installed on this PC.")
            return
        try:
            subprocess.Popen([str(executable), browser + "://extensions"], close_fds=True)
        except OSError:
            QMessageBox.warning(self, "Browser Setup", "Open " + browser + "://extensions in " + browser.title() + ".")

    def installed_error(self, reason):
        self.progress.setVisible(False)
        self.status.setText("Installation could not finish. Your downloads were not removed.")
        self.install_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        QMessageBox.warning(self, "I-DS installation", reason[:450])


def main():
    if "--verify-install-sandbox" in sys.argv:
        if not os.environ.get("I_DS_TEST_INSTALLROOT") or not os.environ.get("I_DS_TEST_SHORTCUTSROOT"):
            return 2
        report = os.environ.get("I_DS_TEST_RESULT")
        try:
            installed = install_release(upgrade=True)
            if report:
                Path(report).write_text("PASS:" + installed, encoding="utf-8")
            return 0
        except Exception as exc:
            if report:
                Path(report).write_text("FAIL:" + str(exc), encoding="utf-8")
            return 1
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = SetupWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
