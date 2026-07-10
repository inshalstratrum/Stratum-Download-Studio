import sys
import os
import uuid
import json
import http.server
import socketserver
import subprocess
import re
from datetime import datetime
import yt_dlp

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QToolBar,
    QDialog, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QProgressBar, QSystemTrayIcon, QMenu, QStyle, QSpinBox, QVBoxLayout,
    QHBoxLayout, QHeaderView, QSplitter, QTreeWidget, QTreeWidgetItem, 
    QPushButton, QComboBox, QMenuBar, QFormLayout, QGroupBox, QTabWidget,
    QWidget, QGridLayout, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QPixmap

# ==========================================
# MODERN UI STYLESHEET 
# ==========================================
MODERN_STYLE = """
QMainWindow, QDialog { background-color: #f0f0f0; color: #000000; }
QTableWidget { background-color: #ffffff; border: 1px solid #a0a0a0; gridline-color: #e0e0e0; color: #000000; }
QTableWidget::item:selected { background-color: #0078d7; color: #ffffff; }
QHeaderView::section { background-color: #f0f0f0; padding: 4px; border: 1px solid #a0a0a0; color: #000000; }
QPushButton { background-color: #e1e1e1; color: black; border-radius: 2px; padding: 5px 15px; border: 1px solid #adadad; }
QPushButton:hover { background-color: #e5f1fb; border: 1px solid #0078d7; }
QPushButton:pressed { background-color: #cce4f7; border: 1px solid #005499; }
QLineEdit, QComboBox { padding: 4px; border: 1px solid #a0a0a0; background-color: white; color: black; }
QProgressBar { text-align: center; border: 1px solid #a0a0a0; background-color: #e6e6e6; color: black; }
QProgressBar::chunk { background-color: #06b025; }
QTreeWidget { border: 1px solid #a0a0a0; background-color: white; color: black; }
QTreeWidget::item:selected { background-color: #0078d7; color: white; }
QTabWidget::pane { border: 1px solid #a0a0a0; background: #f0f0f0; }
"""

def get_ffmpeg_path():
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, 'ffmpeg.exe')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_ffmpeg = os.path.join(base_dir, 'ffmpeg.exe')
    if os.path.exists(local_ffmpeg): return local_ffmpeg
    return 'ffmpeg'

# ==========================================
# 1. LOCAL SERVER
# ==========================================
class IDMServerHandler(http.server.BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    def do_OPTIONS(self):
        self.send_response(200); self.send_cors_headers(); self.end_headers()
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data.decode('utf-8'))
            url = data.get('url', '')
            if url:
                self.server.url_signal.emit(url)
                self.send_response(200); self.send_cors_headers(); self.end_headers()
                self.wfile.write(b'{"status": "success"}')
            else:
                self.send_response(400); self.send_cors_headers(); self.end_headers()
        except:
            self.send_response(500); self.send_cors_headers(); self.end_headers()

class ServerThread(QThread):
    url_received = pyqtSignal(str)
    def run(self):
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("127.0.0.1", 8000), IDMServerHandler)
        self.httpd.url_signal = self.url_received
        self.httpd.serve_forever()

# ==========================================
# 2. ASYNC FORMAT FETCHER
# ==========================================
class FormatFetcherThread(QThread):
    formats_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    def __init__(self, url):
        super().__init__(); self.url = url
    def run(self):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
                self.formats_ready.emit(ydl.extract_info(self.url, download=False))
        except Exception as e:
            self.error_occurred.emit(str(e))

class ConvertThread(QThread):
    finished = pyqtSignal(str, bool, str)
    def __init__(self, row_id, input_file, target_ext):
        super().__init__()
        self.row_id = row_id; self.input_file = input_file; self.target_ext = target_ext
    def run(self):
        try:
            base, _ = os.path.splitext(self.input_file)
            output_file = f"{base}_converted.{self.target_ext}"
            process = subprocess.run([get_ffmpeg_path(), '-y', '-i', self.input_file, output_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            if process.returncode == 0: self.finished.emit(self.row_id, True, "Converted!")
            else: self.finished.emit(self.row_id, False, "Conversion Failed")
        except Exception as e: self.finished.emit(self.row_id, False, str(e))

# ==========================================
# 3. DOWNLOAD ENGINE ("THE SPEED GRABBER")
# ==========================================
class PauseException(Exception): pass

class DownloadThread(QThread):
    progress = pyqtSignal(str, str, float, str, str)
    status = pyqtSignal(str, str)
    finished = pyqtSignal(str, bool, str, str) 
    size_updated = pyqtSignal(str, str, str)

    def __init__(self, id, url, outtmpl, format_str, target_ext):
        super().__init__()
        self.id = id; self.url = url; self.outtmpl = outtmpl
        self.format_str = format_str; self.target_ext = target_ext.lower()
        self.paused = False; self.final_filename = ""

    def format_size(self, bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0: return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} TB"

    def progress_hook(self, d):
        if self.paused: raise PauseException("Paused")
        if d['status'] == 'downloading':
            filename = os.path.basename(d['filename'])
            percent_clean = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%').strip('%'))
            try: percent = float(percent_clean)
            except ValueError: percent = 0.0
            
            speed = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', 'N/A'))
            eta = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', 'N/A'))
            
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total_bytes: self.size_updated.emit(self.id, filename, self.format_size(total_bytes))
            self.progress.emit(self.id, filename, percent, speed, eta)
            self.status.emit(self.id, 'Downloading')
        elif d['status'] == 'finished':
            self.final_filename = d.get('info_dict', {}).get('_filename', d['filename'])

    def run(self):
        try:
            ydl_opts = {
                'outtmpl': self.outtmpl,
                'format': self.format_str,
                'progress_hooks': [self.progress_hook],
                'quiet': True, 'no_warnings': True, 'noplaylist': True,
                'ffmpeg_location': get_ffmpeg_path(),
                # --- THE SPEED GRABBER MULTIPLEXING ---
                'concurrent_fragment_downloads': 10,
                'buffersize': 1024 * 32,
            }
            
            audio_formats = ['mp3', 'wav', 'flac', 'm4a']
            if self.target_ext in audio_formats:
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': self.target_ext, 'preferredquality': '192'}]
            else:
                ydl_opts['merge_output_format'] = self.target_ext 

            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([self.url])
                
            if self.target_ext in audio_formats and self.final_filename:
                base, _ = os.path.splitext(self.final_filename)
                self.final_filename = base + f".{self.target_ext}"
            elif self.final_filename:
                base, _ = os.path.splitext(self.final_filename)
                self.final_filename = base + f".{self.target_ext}"

            if os.path.exists(self.final_filename):
                self.size_updated.emit(self.id, os.path.basename(self.final_filename), self.format_size(os.path.getsize(self.final_filename)))

            self.status.emit(self.id, 'Completed')
            self.finished.emit(self.id, True, '', self.final_filename)
            
        except PauseException: self.status.emit(self.id, 'Paused')
        except Exception as e: self.status.emit(self.id, 'Error'); self.finished.emit(self.id, False, str(e), "")

# ==========================================
# 4. EXACT IDM GUI REPLICAS
# ==========================================
class DownloadFileInfoDialog(QDialog):
    def __init__(self, parent=None, prefill_url=""):
        super().__init__(parent)
        self.setWindowTitle("Download File Info")
        self.setFixedSize(650, 300)
        
        layout = QVBoxLayout()
        
        # Grid layout for exact spacing
        grid = QGridLayout()
        
        # 1. URL
        grid.addWidget(QLabel("URL"), 0, 0)
        self.url_edit = QLineEdit(prefill_url)
        grid.addWidget(self.url_edit, 0, 1, 1, 4)
        
        # 2. Category & Format
        grid.addWidget(QLabel("Category"), 1, 0)
        self.category_combo = QComboBox()
        self.category_combo.addItems(["General", "Compressed", "Documents", "Music", "Programs", "Video"])
        grid.addWidget(self.category_combo, 1, 1, 1, 2)
        
        grid.addWidget(QLabel("Format:"), 1, 3, alignment=Qt.AlignmentFlag.AlignRight)
        self.ext_combo = QComboBox()
        self.ext_combo.addItems(["MP4", "MKV", "AVI", "MOV", "WEBM", "MP3", "WAV", "FLAC", "M4A"])
        grid.addWidget(self.ext_combo, 1, 4)
        
        # 3. Save As
        grid.addWidget(QLabel("Save As"), 2, 0)
        self.save_dir_edit = QLineEdit(os.path.join(os.path.expanduser('~'), 'Downloads'))
        grid.addWidget(self.save_dir_edit, 2, 1, 1, 3)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self.browse_dir)
        grid.addWidget(browse_btn, 2, 4)
        
        # 4. Remember Path Checkbox
        self.remember_cb = QCheckBox("Remember this path for category")
        self.remember_cb.setChecked(True)
        grid.addWidget(self.remember_cb, 3, 1, 1, 4)
        
        # 5. Description
        grid.addWidget(QLabel("Description"), 4, 0)
        self.desc_edit = QLineEdit()
        grid.addWidget(self.desc_edit, 4, 1, 1, 4)
        
        layout.addLayout(grid)
        
        # Size Preview
        self.info_lbl = QLabel("Fetching File Data...")
        self.info_lbl.setStyleSheet("color: #0078d7; font-weight: bold; margin-top: 10px;")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_lbl)

        # Buttons (Bottom)
        btn_layout = QHBoxLayout()
        self.dl_later_btn = QPushButton("Download Later")
        self.dl_later_btn.clicked.connect(self.reject) 
        self.start_btn = QPushButton("Start Download")
        self.start_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.dl_later_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

        self.ext_combo.currentTextChanged.connect(self.on_ext_changed)
        if prefill_url: self.fetch_formats()
        self.url_edit.textChanged.connect(self.fetch_formats)
        self.on_ext_changed("MP4")

    def on_ext_changed(self, text):
        if text in ["MP3", "WAV", "FLAC", "M4A"]: self.category_combo.setCurrentText("Music")
        elif text in ["MP4", "MKV", "AVI", "MOV", "WEBM"]: self.category_combo.setCurrentText("Video")

    def fetch_formats(self):
        url = self.url_edit.text().strip()
        if not url: return
        self.info_lbl.setText("Connecting to server...")
        self.start_btn.setEnabled(False)
        self.fetcher = FormatFetcherThread(url)
        self.fetcher.formats_ready.connect(self.on_formats_ready)
        self.fetcher.error_occurred.connect(self.on_fetch_error)
        self.fetcher.start()

    def on_formats_ready(self, info):
        size = info.get('filesize_approx') or info.get('filesize')
        size_str = f" | Size: {round(size/1024/1024, 2)} MB" if size else ""
        self.info_lbl.setText(f"File Ready{size_str}")
        self.start_btn.setEnabled(True)

    def on_fetch_error(self, error_msg):
        self.info_lbl.setText("Ready to Download (Dynamic Size)")
        self.start_btn.setEnabled(True)

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if directory: self.save_dir_edit.setText(directory)

    def get_data(self):
        return self.url_edit.text().strip(), self.save_dir_edit.text().strip(), 0, self.ext_combo.currentText()


class DownloadProgressPopup(QDialog):
    def __init__(self, filename, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"0% {filename}")
        self.setFixedSize(500, 280) # Closed details state
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.details_open = False
        self.filename = filename
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Tabs
        self.tabs = QTabWidget()
        status_tab = QWidget()
        speed_tab = QWidget()
        options_tab = QWidget()
        self.tabs.addTab(status_tab, "Download status")
        self.tabs.addTab(speed_tab, "Speed Limiter")
        self.tabs.addTab(options_tab, "Options on completion")
        
        # Status Tab Layout (Exact IDM replica)
        status_layout = QFormLayout()
        status_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        url_lbl = QLineEdit(url)
        url_lbl.setReadOnly(True)
        url_lbl.setStyleSheet("border: none; background: transparent;")
        status_layout.addRow("", url_lbl)
        
        self.status_lbl = QLabel("Receiving data...")
        self.status_lbl.setStyleSheet("color: blue;")
        status_layout.addRow("Status", self.status_lbl)
        
        self.size_lbl = QLabel("Calculating...")
        status_layout.addRow("File size", self.size_lbl)
        
        self.downloaded_lbl = QLabel("0 MB (0%)")
        status_layout.addRow("Downloaded", self.downloaded_lbl)
        
        self.speed_lbl = QLabel("0 MB/sec")
        status_layout.addRow("Transfer rate", self.speed_lbl)
        
        self.time_lbl = QLabel("Calculating...")
        status_layout.addRow("Time left", self.time_lbl)
        
        status_layout.addRow("Resume capability", QLabel("Yes"))
        status_tab.setLayout(status_layout)
        
        main_layout.addWidget(self.tabs)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(15)
        main_layout.addWidget(self.progress_bar)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.details_btn = QPushButton("Show details >>")
        self.details_btn.clicked.connect(self.toggle_details)
        
        self.pause_btn = QPushButton("Pause")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.details_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)
        
        # Details Panel (Connections Table)
        self.details_widget = QWidget()
        det_layout = QVBoxLayout()
        det_layout.addWidget(QLabel("Start positions and download progress by connections"))
        
        self.conn_table = QTableWidget(4, 3) # Dummy 4 connections to mimic UI
        self.conn_table.setHorizontalHeaderLabels(["N.", "Downloaded", "Info"])
        self.conn_table.verticalHeader().setVisible(False)
        self.conn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.conn_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.conn_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        # Populate dummy multiplexing lines
        for i in range(4):
            self.conn_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.conn_table.setItem(i, 1, QTableWidgetItem("Receiving..."))
            self.conn_table.setItem(i, 2, QTableWidgetItem("Downloading data"))
            
        det_layout.addWidget(self.conn_table)
        self.details_widget.setLayout(det_layout)
        self.details_widget.hide()
        
        main_layout.addWidget(self.details_widget)
        self.setLayout(main_layout)

    def toggle_details(self):
        if self.details_open:
            self.details_widget.hide()
            self.details_btn.setText("Show details >>")
            self.setFixedSize(500, 280)
            self.details_open = False
        else:
            self.details_widget.show()
            self.details_btn.setText("<< Hide details")
            self.setFixedSize(500, 450)
            self.details_open = True

    def update_stats(self, percent, speed, eta, total_size=""):
        self.setWindowTitle(f"{int(percent)}% {self.filename}")
        self.progress_bar.setValue(int(percent))
        self.speed_lbl.setText(speed)
        self.time_lbl.setText(eta)
        self.downloaded_lbl.setText(f"({percent}%)")
        if total_size: self.size_lbl.setText(total_size)

# ==========================================
# 5. MAIN APP: INSHAL_DM
# ==========================================
class InshalDM(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inshal DM - Professional Download Manager")
        self.setGeometry(100, 100, 1150, 680)
        self.downloads = []; self.popups = {} 
        self.init_ui()
        self.init_tray_icon() 
        self.load_downloads_from_file() 
        self.init_server()

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)
        
        tray_menu = QMenu()
        tray_menu.addAction("Show Inshal DM", self.show_normal)
        tray_menu.addSeparator()
        tray_menu.addAction("Exit", self.force_quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick: self.show_normal()

    def show_normal(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and self.windowState() & Qt.WindowState.WindowMinimized:
            event.accept(); self.hide()
            self.tray_icon.showMessage("Inshal DM", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 1500)
            return
        super().changeEvent(event)

    def closeEvent(self, event):
        event.ignore(); self.hide()

    def force_quit(self):
        self.save_downloads_to_file(); QApplication.quit()

    def save_downloads_to_file(self):
        save_data = []
        for row in range(self.table.rowCount()):
            bar = self.table.cellWidget(row, 3)
            status = bar.text() if bar else self.table.item(row, 3).text() if self.table.item(row, 3) else "Completed"
            if d_info := next((d for d in self.downloads if d['row'] == row), None):
                save_data.append({
                    'filename': self.table.item(row, 0).text(),
                    'size': self.table.item(row, 2).text() if self.table.item(row, 2) else "",
                    'status': status,
                    'eta': self.table.item(row, 4).text() if self.table.item(row, 4) else "",
                    'speed': self.table.item(row, 5).text() if self.table.item(row, 5) else "",
                    'date': self.table.item(row, 6).text() if self.table.item(row, 6) else "",
                    'url': self.table.item(row, 7).text() if self.table.item(row, 7) else "",
                    'id': d_info['id'], 'outtmpl': d_info['outtmpl'], 'format': d_info['format'], 'ext': d_info['ext'], 'final_path': d_info.get('final_path', '')
                })
        with open('inshaldm_history.json', 'w') as f: json.dump(save_data, f)

    def load_downloads_from_file(self):
        if not os.path.exists('inshaldm_history.json'): return
        try:
            with open('inshaldm_history.json', 'r') as f: save_data = json.load(f)
            for item in save_data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(item.get('filename', '')))
                self.table.setItem(row, 1, QTableWidgetItem(""))
                self.table.setItem(row, 2, QTableWidgetItem(item.get('size', '')))
                
                pb = QProgressBar(); pb.setRange(0, 100); status = item.get('status', '')
                if "Downloading" in status or "Paused" in status: pb.setValue(0); pb.setFormat("Paused")
                else: pb.setValue(100); pb.setFormat(status)
                    
                self.table.setCellWidget(row, 3, pb)
                self.table.setItem(row, 4, QTableWidgetItem(item.get('eta', '')))
                self.table.setItem(row, 5, QTableWidgetItem(item.get('speed', '')))
                self.table.setItem(row, 6, QTableWidgetItem(item.get('date', '')))
                self.table.setItem(row, 7, QTableWidgetItem(item.get('url', '')))
                
                self.downloads.append({
                    'id': item.get('id', ''), 'url': item.get('url', ''), 'outtmpl': item.get('outtmpl', ''),
                    'format': item.get('format', ''), 'ext': item.get('ext', ''), 'thread': None, 'row': row, 'final_path': item.get('final_path', '')
                })
        except: pass

    def show_dummy_msg(self, title): QMessageBox.information(self, "Inshal DM", f"'{title}' feature coming soon!")

    def init_ui(self):
        menubar = self.menuBar()
        tasks_menu = menubar.addMenu("Tasks")
        tasks_menu.addAction("Add new download").triggered.connect(lambda: self.open_add_dialog(""))
        tasks_menu.addAction("Add batch download").triggered.connect(lambda: self.show_dummy_msg("Batch Download"))
        tasks_menu.addAction("Run site grabber").triggered.connect(lambda: self.show_dummy_msg("Site Grabber"))
        tasks_menu.addSeparator(); tasks_menu.addAction("Exit").triggered.connect(self.force_quit)
        
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Stop Download").triggered.connect(self.pause_download)
        file_menu.addAction("Remove").triggered.connect(self.delete_download)
        file_menu.addAction("Download Now").triggered.connect(self.resume_download)
        
        dl_menu = menubar.addMenu("Downloads")
        dl_menu.addAction("Pause All").triggered.connect(self.pause_download)
        dl_menu.addAction("Delete All Completed").triggered.connect(self.delete_completed)
        
        menubar.addMenu("View"); menubar.addMenu("Help"); menubar.addMenu("Registration")

        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False); toolbar.setIconSize(toolbar.iconSize() * 1.5)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)

        toolbar.addAction("➕\nAdd URL").triggered.connect(lambda: self.open_add_dialog(""))
        toolbar.addAction("▶\nResume").triggered.connect(self.resume_download)
        toolbar.addAction("⏹\nStop").triggered.connect(self.pause_download)
        toolbar.addAction("🛑\nStop All").triggered.connect(self.pause_download)
        toolbar.addAction("❌\nDelete").triggered.connect(self.delete_download)
        toolbar.addAction("🗑\nClear Done").triggered.connect(self.delete_completed)
        toolbar.addAction("⚙\nOptions").triggered.connect(lambda: self.show_dummy_msg("Options"))
        toolbar.addAction("🔗\nShare").triggered.connect(self.share_link)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        root_all = QTreeWidgetItem(["All Downloads"])
        QTreeWidgetItem(root_all, ["Video"]); QTreeWidgetItem(root_all, ["Audio"]); QTreeWidgetItem(root_all, ["Compressed"]); QTreeWidgetItem(root_all, ["Documents"])
        self.tree.addTopLevelItem(root_all); self.tree.addTopLevelItem(QTreeWidgetItem(["Unfinished"])); self.tree.addTopLevelItem(QTreeWidgetItem(["Finished"]))
        root_all.setExpanded(True)
        self.tree.itemClicked.connect(self.filter_by_category)
        splitter.addWidget(self.tree)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["File Name", "Q", "Size", "Status", "Time Left", "Transfer Rate", "Last Try Date", "Description"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        splitter.addWidget(self.table)
        splitter.setSizes([200, 950])

    def filter_by_category(self, item, column):
        category = item.text(0)
        for row in range(self.table.rowCount()):
            if category == "All Downloads": self.table.setRowHidden(row, False); continue
            filename = self.table.item(row, 0).text().lower()
            bar = self.table.cellWidget(row, 3)
            status = bar.text() if bar else self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            hidden = True
            if category == "Video" and filename.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')): hidden = False
            elif category == "Audio" and filename.endswith(('.mp3', '.wav', '.flac', '.m4a')): hidden = False
            elif category == "Compressed" and filename.endswith(('.zip', '.rar', '.7z')): hidden = False
            elif category == "Documents" and filename.endswith(('.pdf', '.docx', '.txt')): hidden = False
            elif category == "Finished" and "Complete" in status: hidden = False
            elif category == "Unfinished" and "Complete" not in status: hidden = False
            self.table.setRowHidden(row, hidden)

    def show_context_menu(self, position):
        menu = QMenu()
        menu.addAction("Open").triggered.connect(self.open_selected_file)
        menu.addAction("Open folder").triggered.connect(self.open_selected_folder)
        menu.addSeparator()
        cv_menu = menu.addMenu("Convert Format...")
        cv_menu.addAction("To MP4").triggered.connect(lambda: self.trigger_conversion("mp4"))
        cv_menu.addAction("To MP3").triggered.connect(lambda: self.trigger_conversion("mp3"))
        cv_menu.addAction("To WAV").triggered.connect(lambda: self.trigger_conversion("wav"))
        menu.addSeparator()
        menu.addAction("Resume Download").triggered.connect(self.resume_download)
        menu.addAction("Stop Download").triggered.connect(self.pause_download)
        menu.addSeparator()
        menu.addAction("Remove").triggered.connect(self.delete_download)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def open_selected_file(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                if d.get('final_path') and os.path.exists(d['final_path']): os.startfile(d['final_path'])

    def open_selected_folder(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                if d.get('final_path') and os.path.exists(d['final_path']): subprocess.Popen(f'explorer /select,"{os.path.normpath(d["final_path"])}"')

    def share_link(self):
        if selected := self.table.selectionModel().selectedRows():
            QApplication.clipboard().setText(self.table.item(selected[0].row(), 7).text())
            QMessageBox.information(self, "Link Copied", "URL copied to clipboard!")

    def delete_completed(self):
        for row in range(self.table.rowCount() - 1, -1, -1):
            bar = self.table.cellWidget(row, 3)
            if "Complete" in (bar.text() if bar else self.table.item(row, 3).text() if self.table.item(row, 3) else ""):
                if d := next((d for d in self.downloads if d['row'] == row), None): self.downloads.remove(d)
                self.table.removeRow(row)
                for other in self.downloads:
                    if other['row'] > row: other['row'] -= 1

    def init_server(self):
        self.server_thread = ServerThread()
        self.server_thread.url_received.connect(self.open_add_dialog)
        self.server_thread.start()

    def open_add_dialog(self, url=""):
        if isinstance(url, bool): url = ""
        self.show_normal() 
        dialog = DownloadFileInfoDialog(self, prefill_url=url)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            final_url, save_dir, quality_idx, target_ext = dialog.get_data()
            if final_url: self.start_new_download(final_url, save_dir, quality_idx, target_ext)

    def start_new_download(self, url, save_dir, quality_idx, target_ext):
        download_id = uuid.uuid4().hex
        outtmpl = os.path.join(save_dir, '%(title)s.%(ext)s')
        
        if target_ext in ["MP3", "WAV", "FLAC", "M4A"]: format_str = 'bestaudio/best'
        elif target_ext == "MP4": format_str = {0: 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 1: 'bestvideo[height<=1080][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 2: 'bestvideo[height<=720][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best', 3: 'bestvideo[height<=480][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4]/best'}.get(quality_idx, 'best')
        else: format_str = {0: 'bestvideo+bestaudio/best', 1: 'bestvideo[height<=1080]+bestaudio/best', 2: 'bestvideo[height<=720]+bestaudio/best', 3: 'bestvideo[height<=480]+bestaudio/best'}.get(quality_idx, 'best')

        row = self.table.rowCount()
        self.table.insertRow(row)
        
        pb = QProgressBar(); pb.setRange(0, 100); pb.setValue(0)
        self.table.setItem(row, 0, QTableWidgetItem("Connecting..."))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem("Calculating"))
        self.table.setCellWidget(row, 3, pb) 
        self.table.setItem(row, 4, QTableWidgetItem("--:--"))
        self.table.setItem(row, 5, QTableWidgetItem("0 B/s"))
        self.table.setItem(row, 6, QTableWidgetItem(datetime.now().strftime("%b %d %H:%M:%S %Y")))
        self.table.setItem(row, 7, QTableWidgetItem(url))
        
        thread = DownloadThread(download_id, url, outtmpl, format_str, target_ext)
        thread.progress.connect(self.update_progress)
        thread.status.connect(self.update_status)
        thread.finished.connect(self.download_finished)
        thread.size_updated.connect(self.update_size)
        
        self.downloads.append({'id': download_id, 'url': url, 'outtmpl': outtmpl, 'format': format_str, 'ext': target_ext, 'thread': thread, 'row': row, 'final_path': ''})
        thread.start()
        
        popup = DownloadProgressPopup("Connecting...", url, self)
        popup.show()
        self.popups[download_id] = popup

    def get_download_by_id(self, id): return next((d for d in self.downloads if d['id'] == id), None)

    def update_progress(self, id, filename, percent, speed, eta):
        if d := self.get_download_by_id(id):
            if self.table.item(d['row'], 0).text() == "Connecting...":
                self.table.setItem(d['row'], 0, QTableWidgetItem(filename))
                
            self.table.setItem(d['row'], 4, QTableWidgetItem(eta))
            self.table.setItem(d['row'], 5, QTableWidgetItem(speed))
            if bar := self.table.cellWidget(d['row'], 3): bar.setValue(int(percent)); bar.setFormat(f"{int(percent)}%")
                
            if id in self.popups: self.popups[id].update_stats(percent, speed, eta, self.table.item(d['row'], 2).text())

    def update_size(self, id, filename, size):
        if d := self.get_download_by_id(id): self.table.setItem(d['row'], 2, QTableWidgetItem(size))

    def update_status(self, id, status):
        if d := self.get_download_by_id(id):
            if bar := self.table.cellWidget(d['row'], 3): bar.setFormat(status)

    def download_finished(self, id, success, error_msg, filepath):
        if d := self.get_download_by_id(id):
            bar = self.table.cellWidget(d['row'], 3)
            if success:
                if bar: bar.setValue(100); bar.setFormat("Complete")
                d['final_path'] = filepath 
                if id in self.popups: self.popups[id].close(); del self.popups[id]
                
                dlg = QMessageBox(self)
                dlg.setWindowTitle("Download Complete")
                dlg.setText(f"Download Complete!\n\n{os.path.basename(filepath)}")
                open_btn = dlg.addButton("Open", QMessageBox.ButtonRole.ActionRole)
                folder_btn = dlg.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
                dlg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
                dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                dlg.exec()
                
                if dlg.clickedButton() == open_btn: os.startfile(filepath)
                elif dlg.clickedButton() == folder_btn: subprocess.Popen(f'explorer /select,"{os.path.normpath(filepath)}"')
            else:
                if bar: bar.setFormat(f"Error: {error_msg}")
            d['thread'] = None

    def pause_download(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                if d['thread'] and d['thread'].isRunning(): d['thread'].paused = True

    def resume_download(self):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                bar = self.table.cellWidget(d['row'], 3)
                if bar and "Paused" in bar.text():
                    thread = DownloadThread(d['id'], d['url'], d['outtmpl'], d['format'], d['ext'])
                    thread.progress.connect(self.update_progress)
                    thread.status.connect(self.update_status)
                    thread.finished.connect(self.download_finished)
                    thread.size_updated.connect(self.update_size)
                    d['thread'] = thread
                    thread.start()

    def delete_download(self):
        for idx in sorted(self.table.selectionModel().selectedRows(), key=lambda x: x.row(), reverse=True):
            row = idx.row()
            if d := next((d for d in self.downloads if d['row'] == row), None):
                if d['thread'] and d['thread'].isRunning(): d['thread'].paused = True
                self.table.removeRow(row); self.downloads.remove(d)
                for other in self.downloads:
                    if other['row'] > row: other['row'] -= 1

    def trigger_conversion(self, target_ext):
        for idx in self.table.selectionModel().selectedRows():
            if d := next((d for d in self.downloads if d['row'] == idx.row()), None):
                bar = self.table.cellWidget(d['row'], 3)
                if bar and bar.text() == "Complete" and d.get('final_path'):
                    bar.setFormat("Converting...")
                    self.converter = ConvertThread(d['id'], d['final_path'], target_ext)
                    self.converter.finished.connect(self.conversion_done)
                    self.converter.start()

    def conversion_done(self, row_id, success, msg):
        if d := self.get_download_by_id(row_id):
            if bar := self.table.cellWidget(d['row'], 3): bar.setFormat(msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLE) 
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    window = InshalDM()
    window.show()
    sys.exit(app.exec())
