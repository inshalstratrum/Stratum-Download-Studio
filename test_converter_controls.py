from pathlib import Path

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

import stratum_download_studio as studio


class FakeConversionThread(QObject):
    finished = pyqtSignal(str, bool, str, str)
    progress = pyqtSignal(str, dict)

    def __init__(self, job_id, source, target, output_dir=None, destination=None):
        super().__init__()
        self.job_id = job_id
        self.running = False
        self.paused = False
        self.cancelled = False

    def start(self):
        self.running = True

    def isRunning(self):
        return self.running

    def wait(self, _timeout):
        return not self.running

    def pause(self):
        if not self.running or self.paused or self.cancelled:
            return False
        self.paused = True
        return True

    def resume(self):
        if not self.running or not self.paused or self.cancelled:
            return False
        self.paused = False
        return True

    def cancel(self):
        self.cancelled = True
        self.running = False
        return True


@pytest.fixture
def controller():
    return studio.ConversionJobController(thread_factory=FakeConversionThread)


def test_controller_pause_resume_and_invalid_transitions(controller, tmp_path):
    source = tmp_path / 'source.mp4'; source.write_bytes(b'source')
    assert controller.start('job', source, 'MP3')
    assert not controller.resume('job')
    assert controller.pause('job') and controller.state('job') == 'paused'
    assert not controller.pause('job')
    assert controller.resume('job') and controller.state('job') == 'converting'
    assert not controller.resume('missing')


def test_controller_cancel_rejects_stale_completion(controller, tmp_path):
    source = tmp_path / 'source.mp4'; source.write_bytes(b'source')
    completed = []
    controller.finished.connect(lambda *args: completed.append(args))
    controller.start('job', source, 'MP3')
    job = controller.jobs['job']; old_thread = job['thread']; old_generation = job['generation']
    assert controller.cancel('job', remove=True)
    controller._finished('job', True, 'Conversion complete', str(tmp_path / 'bad.mp3'), old_generation)
    assert completed == [] and 'job' not in controller.jobs and source.read_bytes() == b'source'
    old_thread.finished.emit('job', True, 'Conversion complete', str(tmp_path / 'bad.mp3'))
    assert completed == []


def test_stop_failure_can_never_be_reported_as_success(controller, tmp_path, monkeypatch):
    source = tmp_path / 'source.mp4'; source.write_bytes(b'source')
    results = []
    controller.finished.connect(lambda *args: results.append(args))
    controller.start('job', source, 'MP3')
    job = controller.jobs['job']
    monkeypatch.setattr(job['thread'], 'cancel', lambda: False)
    monkeypatch.setattr(job['thread'], 'wait', lambda _timeout: False)
    assert not controller.cancel('job') and controller.state('job') == 'stop_failed'
    controller._finished('job', True, 'Conversion complete', str(tmp_path / 'bad.mp3'), job['generation'])
    assert results == [('job', False, 'Conversion cancelled', '')]


def test_cancelled_thread_cleans_only_temporary_output(monkeypatch, tmp_path):
    source = tmp_path / 'source.mp4'; source.write_bytes(b'source')
    final = tmp_path / 'source_converted.mp3'; final.write_bytes(b'previous')
    temporary = tmp_path / '.source_converted.token.mp3.part'; temporary.write_bytes(b'incomplete')
    thread = studio.ConvertThread('job', source, 'MP3')
    thread.cancelled = True
    monkeypatch.setattr(studio, 'build_conversion_plan', lambda *args, **kwargs: None)
    thread.run()
    assert source.read_bytes() == b'source' and final.read_bytes() == b'previous'
    temporary.unlink()


def _dialog_with_files(monkeypatch, tmp_path):
    monkeypatch.setattr(studio, 'probe_media_file', lambda *_: {'format_name': 'mov', 'duration': 1, 'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 10, 'height': 10}, {'codec_type': 'audio', 'codec_name': 'aac'}]})
    first = tmp_path / 'first.mp4'; second = tmp_path / 'second.mp4'
    first.write_bytes(b'first'); second.write_bytes(b'second')
    dialog = studio.LocalConverterDialog(); dialog.add_files([first, second])
    return dialog, first, second


def test_per_file_target_and_apply_format_to_all(monkeypatch, tmp_path):
    dialog, _, _ = _dialog_with_files(monkeypatch, tmp_path)
    dialog.table.cellWidget(0, 2).setCurrentText('MP3')
    dialog.table.cellWidget(1, 2).setCurrentText('WAV')
    assert [entry['target'] for entry in dialog.entries] == ['MP3', 'WAV']
    dialog.target_combo.setCurrentText('M4A'); dialog.apply_format_to_all()
    assert [entry['target'] for entry in dialog.entries] == ['M4A', 'M4A']


def test_remove_and_clear_never_delete_sources(monkeypatch, tmp_path):
    dialog, first, second = _dialog_with_files(monkeypatch, tmp_path)
    dialog.table.selectRow(0)
    assert dialog.remove_selected() and first.is_file() and second.is_file()
    assert dialog.clear_list() and first.is_file() and second.is_file() and not dialog.entries


def test_active_removal_cancels_before_row_removal(monkeypatch, tmp_path):
    dialog, first, _ = _dialog_with_files(monkeypatch, tmp_path)
    entry = dialog.entries[0]; dialog.active_job_id = entry['job_id']; entry['state'] = 'converting'
    calls = []
    monkeypatch.setattr(dialog.conversion_controller, 'cancel', lambda job_id, **kwargs: calls.append((job_id, kwargs)) or True)
    dialog.table.selectRow(0)
    assert dialog.remove_selected()
    assert calls == [(entry['job_id'], {'remove': True})] and first.is_file()


def test_active_removal_retains_row_when_stop_unconfirmed(monkeypatch, tmp_path):
    dialog, first, _ = _dialog_with_files(monkeypatch, tmp_path)
    entry = dialog.entries[0]; dialog.active_job_id = entry['job_id']; entry['state'] = 'converting'
    monkeypatch.setattr(dialog.conversion_controller, 'cancel', lambda *args, **kwargs: False)
    dialog.table.selectRow(0)
    assert not dialog.remove_selected() and entry in dialog.entries and first.is_file()


def test_main_window_conversion_uses_shared_controller_and_visible_controls():
    assert 'ConversionJobController' in studio.StratrumDownloadStudio.__init__.__code__.co_names
    popup = studio.DownloadProgressPopup('file.mp4', 'https://example.test', job_id='job')
    popup.set_job_state('converting')
    assert popup.pause_btn.isVisibleTo(popup) is False or popup.pause_btn.isEnabled()
    assert popup.pause_btn.text() == 'Pause' and popup.cancel_btn.text() == 'Cancel'
    popup.set_job_state('paused')
    assert popup.pause_btn.text() == 'Resume' and popup.pause_btn.isEnabled()
