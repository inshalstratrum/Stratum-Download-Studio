"""Isolated Windows Qt integration checks for terminal popups and browser foreground.

Each test executes in a separate process because Win32 Qt widget ownership
can otherwise contaminate unrelated GUI cases during an all-in-one pytest run.
"""
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

REPO = Path(__file__).resolve().parents[1]


def _run_qt_check(script, folder):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", dedent(script), str(folder)],
        cwd=REPO, env=env, capture_output=True, text=True,
        timeout=30, check=False,
    )
    assert result.returncode == 0, (result.stdout[-700:], result.stderr[-1100:])


def test_failed_job_closes_progress_after_acknowledgment(tmp_path):
    _run_qt_check("""
        import sys
        from PyQt6.QtWidgets import QApplication, QMessageBox
        import stratum_download_studio as s
        app = QApplication.instance() or QApplication([])
        conf = s.initialize_runtime(app_data_root=sys.argv[1], auth_token='a'*64)
        s.StratrumDownloadStudio.init_server = lambda self: None
        s.StratrumDownloadStudio.start_queued_jobs = lambda self: None
        QMessageBox.warning = lambda *args: QMessageBox.StandardButton.Ok
        window = s.StratrumDownloadStudio(conf)
        try:
            assert window.start_http_download('https://example.org/manual.pdf', sys.argv[1], show_popup=True)
            app.processEvents()
            row = window.downloads[-1]
            popup = window.popups[row['id']]
            assert popup.isVisible()
            window.download_finished(row['id'], False, 'HTTP Error 403: Forbidden', '')
            app.processEvents()
            assert row['id'] not in window.popups
            assert not popup.isVisible()
            assert row['job'].state == 'failed'
        finally:
            window.tray_icon.hide()
            window.hide()
    """, tmp_path)


def test_terminal_close_does_not_prompt_to_remove_partials(tmp_path):
    _run_qt_check("""
        from PyQt6.QtWidgets import QApplication, QMessageBox
        import stratum_download_studio as s
        app = QApplication.instance() or QApplication([])
        popup = s.DownloadProgressPopup('test.pdf','https://example.org/test.pdf',job_id='z'*32)
        sent = []
        popup.cancel_requested.connect(lambda *args: sent.append(args))
        QMessageBox.exec = lambda self: (_ for _ in ()).throw(AssertionError('unexpected cancel prompt'))
        popup.show()
        popup.set_job_state('failed')
        assert popup.cancel_btn.text()=='Close'
        popup.cancel_btn.click()
        assert not popup.isVisible()
        assert not sent
        popup.close()
    """, tmp_path)


def test_browser_options_foreground_without_main_window(tmp_path):
    _run_qt_check("""
        import sys
        from PyQt6.QtWidgets import QApplication, QDialog
        import stratum_download_studio as s
        app=QApplication.instance() or QApplication([])
        cfg=s.initialize_runtime(app_data_root=sys.argv[1],auth_token='b'*64)
        s.StratrumDownloadStudio.init_server=lambda self:None
        window=s.StratrumDownloadStudio(cfg)
        actions=[]
        class Dialog:
            def __init__(self,*args,**kwargs):actions.append('created')
            def setWindowFlag(self,*args):actions.append('front-dialog-only')
            def exec(self):actions.append('exec');return QDialog.DialogCode.Rejected
        s.DownloadFileInfoDialog=Dialog
        window.show_normal=lambda **kw:actions.append('main-window-raised')
        try:
            window.open_add_dialog('https://example.org/media',request_foreground=True)
            assert actions==['created','front-dialog-only','exec'], actions
        finally:
            window.tray_icon.hide()
            window.hide()
    """, tmp_path)
