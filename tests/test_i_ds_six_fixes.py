"""Regression checks for the six owner-reported setup/download UX corrections."""
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def qt_case(source, test_directory):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [sys.executable, "-c", dedent(source), str(test_directory)],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=45,
    )
    assert result.returncode == 0, (result.stdout[-900:], result.stderr[-1400:])


def test_standard_file_download_dialog_validates_folder_name_and_url(tmp_path):
    qt_case("""
        import sys
        from PyQt6.QtWidgets import QApplication,QDialog,QMessageBox
        import stratum_download_studio as app
        qt=QApplication([])
        d=app.StandardFileDownloadDialog(default_folder=sys.argv[1],recent_folders=[sys.argv[1]])
        assert d.folder_combo.currentText()==sys.argv[1]
        assert d.url_edit.accessibleName()=="File download URL"
        issues=[]
        QMessageBox.warning=lambda _,title,msg: issues.append((title,msg))
        d.url_edit.setText('ftp://example.org/file.zip')
        d.validate_and_accept()
        assert issues and d.result()!=QDialog.DialogCode.Accepted
        d.url_edit.setText('https://example.org/archive.zip')
        d.folder_combo.setCurrentText(sys.argv[1])
        d.name_edit.setText(r'C:\\fake\\new:name.zip')
        d.validate_and_accept()
        assert d.result()==QDialog.DialogCode.Accepted
        url,folder,name=d.get_data()
        assert url=='https://example.org/archive.zip'
        assert folder==sys.argv[1]
        assert name=='new_name.zip',name
        d.close()
    """, tmp_path)


def test_manual_dialog_flows_into_original_file_queue(tmp_path):
    qt_case("""
        import sys
        from pathlib import Path
        from PyQt6.QtWidgets import QApplication,QDialog
        import stratum_download_studio as app
        qt=QApplication([])
        config=app.initialize_runtime(app_data_root=Path(sys.argv[1])/'config',auth_token='f'*64)
        app.StratrumDownloadStudio.init_server=lambda _:None
        app.StratrumDownloadStudio.start_queued_jobs=lambda _:None
        window=app.StratrumDownloadStudio(config)
        class FakeDialog:
            def __init__(self,*args,**kwargs): pass
            def exec(self):return QDialog.DialogCode.Accepted
            def get_data(self):return ('https://example.org/file.pdf',sys.argv[1],'custom.pdf')
        app.StandardFileDownloadDialog=FakeDialog
        try:
            window.open_file_dialog()
            assert len(window.downloads)==1
            record=window.downloads[0]
            assert record['job'].requested_format=='FILE'
            assert record['job'].file_name_hint=='custom.pdf'
            assert record['save_dir']==sys.argv[1]
            assert record['id'] in window.popups
        finally:
            window.tray_icon.hide()
            window.hide()
    """, tmp_path)


def test_frozen_extension_guide_resolves_installed_folder(tmp_path):
    qt_case("""
        import sys
        from pathlib import Path
        import stratum_download_studio as studio
        base=Path(sys.argv[1])
        target=base/'Browser Extension'
        target.mkdir()
        (target/'manifest.json').write_text('{"name":"I-DS Download Support"}')
        sys.frozen=True
        sys.executable=str(base/'I-DS.exe')
        assert studio.browser_extension_directory()==target
        assert studio.browser_extension_guide_path()==target
        assert studio.open_browser_extension_guide(opener=lambda p:None)
        assert not studio.open_browser_extensions_settings('invalid')
    """,tmp_path)


def test_setup_shows_browser_steps_and_open_closes_installer(tmp_path):
    qt_case("""
        import importlib.util,sys
        from pathlib import Path
        from PyQt6.QtWidgets import QApplication
        path=Path('scripts/ids_installer_gui.py').resolve()
        spec=importlib.util.spec_from_file_location('ids_setup',path)
        setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
        qt=QApplication([])
        window=setup.SetupWindow()
        window.show()
        qt.processEvents()
        assert not window.browser_group.isVisible()
        window.installed_ok(str(Path(sys.argv[1])/'I-DS.exe'))
        qt.processEvents()
        assert window.browser_group.isVisible()
        assert window.install_btn.text()=='Open I-DS'
        launches=[]
        setup.subprocess.Popen=lambda args,**kwargs:launches.append((args,kwargs))
        window.launch_installed()
        qt.processEvents()
        assert len(launches)==1
        assert not window.isVisible()
        window.launch_installed()
        assert len(launches)==1
    """,tmp_path)


def test_owned_shortcut_and_extension_bundling_contracts():
    installer=(ROOT/"scripts"/"install_ids_windows.ps1").read_text(encoding="utf-8")
    uninstaller=(ROOT/"scripts"/"uninstall_ids_windows.ps1").read_text(encoding="utf-8")
    build=(ROOT/"scripts"/"build_windows_installer.ps1").read_text(encoding="utf-8")
    assert "I_DS_TEST_DESKTOPROOT" in installer
    assert "GetFolderPath('DesktopDirectory')" in installer
    assert "Browser Extension" in installer and "manifest.json" in installer
    assert "GetFolderPath('DesktopDirectory')" in uninstaller
    assert "Browser Extension" in uninstaller
    assert "browser_extension" in build and "stratum-download-studio.ico" in build
