"""Offline contract tests for the functional I-DS native UI refinement."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import Qt, QByteArray, QPoint
from PyQt6.QtGui import QFont
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QTableWidgetItem, QPushButton

import ids_ui_components as ui
import stratum_download_studio as studio


def test_brand_assets_match_native_and_extension():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    assert QSvgRenderer(QByteArray(ui.BRAND_SVG.encode("utf-8"))).isValid()
    for glyph in ("video", "file", "convert", "play", "pause", "cancel",
                  "pause-all", "trash", "clear", "settings", "share",
                  "sidebar", "help", "narrow", "wide", "folder",
                  "audio", "archive", "document", "clock", "check"):
        assert not ui.icon(glyph).isNull()
    root = Path(__file__).resolve().parents[1]
    assert (root / "stratum-download-studio-logo.svg").read_text(encoding="utf-8").strip() == ui.BRAND_SVG.strip()
    for size in (16, 32, 48, 128):
        png = root / "browser_extension" / "icons" / f"i-ds-{size}.png"
        assert png.is_file() and png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_desktop_navigation_text_size_empty_and_data_state(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    original_font = QFont(app.font())
    app.setStyle("Fusion")
    app.setStyleSheet(studio.MODERN_STYLE)
    app.setFont(QFont("Segoe UI", 10))
    conf = studio.initialize_runtime(app_data_root=tmp_path / "mock-app")
    monkeypatch.setattr(studio.StratrumDownloadStudio, "init_server", lambda self: None)
    window = studio.StratrumDownloadStudio(conf)
    try:
        window.resize(1150, 700)
        window.show()
        app.processEvents()
        assert window.download_pages.currentWidget() is window.empty_page
        assert window.dashboard_metrics["active"].text() == "Active  0"
        assert window.sidebar_panel.isVisible()
        assert len(window.toolbar_actions) == 11
        assert not window.toolbar_actions["Download file"].icon().isNull()
        assert window.sidebar_toggle_button.accessibleName()
        assert window.text_scale_combo.accessibleName()

        window.sidebar_toggle_button.click()
        app.processEvents()
        assert not window.sidebar_panel.isVisible()
        assert conf.sidebar_visible is False
        window.sidebar_toggle_button.click()
        app.processEvents()
        assert window.sidebar_panel.isVisible()
        assert conf.sidebar_visible is True

        window.set_sidebar_width(275)
        app.processEvents()
        assert window.splitter.sizes()[0] >= 240
        window.set_sidebar_width(174)
        app.processEvents()
        assert window.splitter.sizes()[0] <= 220

        window.text_scale_combo.setCurrentIndex(window.text_scale_combo.findData(130))
        app.processEvents()
        assert conf.ui_text_scale == 130
        assert app.font().pointSize() == 13
        assert window.sidebar_panel.minimumWidth() == 225
        window.resize(760, 480)
        app.processEvents()
        assert window.toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert window.toolbar.actionGeometry(window.toolbar_actions["Share"]).right() <= window.toolbar.width()
        for button in window.empty_page.findChildren(QPushButton):
            position = button.mapTo(window.empty_page, QPoint(0, 0))
            assert 0 <= position.y() and position.y() + button.height() <= window.empty_page.height()
        window.resize(800, 545)
        app.processEvents()
        assert window.toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert window.sidebar_toggle_button.isVisible()
        assert window.text_scale_combo.isVisible()
        saved = studio.initialize_runtime(app_data_root=tmp_path / "mock-app")
        assert saved.ui_text_scale == 130 and saved.sidebar_visible

        job = studio.DownloadJob(
            job_id="a" * 32, source_url="https://example.org/test.pdf",
            save_dir=str(tmp_path), requested_format="FILE",
            state=studio.JobState.COMPLETED.value,
        )
        window.table.insertRow(0)
        window.table.setItem(0, 0, QTableWidgetItem("synthetic-test.pdf"))
        window.downloads.append({"id": job.job_id, "row": 0, "job": job, "thread": None})
        window.refresh_dashboard()
        assert window.download_pages.currentWidget() is window.table
        assert window.dashboard_metrics["done"].text() == "Finished  1"
        window.delete_completed()
        assert window.table.rowCount() == 0
        assert window.download_pages.currentWidget() is window.empty_page
    finally:
        window.tray_icon.hide()
        window.hide()
        app.setFont(original_font)
