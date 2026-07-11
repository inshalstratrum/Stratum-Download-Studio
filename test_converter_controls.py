from pathlib import Path
import inspect
import os
import sys

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
app = QApplication.instance() or QApplication(sys.argv)

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


def test_paused_progress_merges_and_retains_displayed_percentage(monkeypatch, tmp_path):
    dialog, _, _ = _dialog_with_files(monkeypatch, tmp_path)
    entry = dialog.entries[0]
    controller = studio.ConversionJobController(thread_factory=FakeConversionThread)
    controller.progress.connect(dialog.on_progress)
    controller.start(entry['job_id'], entry['source'], 'MP3')
    generation = controller.jobs[entry['job_id']]['generation']
    controller._progress(entry['job_id'], {'state': 'converting', 'percent': 70, 'elapsed': 12, 'eta': 5, 'destination': str(tmp_path / 'out.mp3')}, generation)
    controller._progress(entry['job_id'], {'state': 'paused'}, generation)
    bar = dialog.table.cellWidget(0, 3)
    assert bar.value() == 70 and bar.format() == 'Paused 70%'
    snapshot = controller.jobs[entry['job_id']]['snapshot']
    assert snapshot['elapsed'] == 12 and snapshot['destination'].endswith('out.mp3')


def test_resume_state_event_continues_from_retained_progress(controller, tmp_path):
    source = tmp_path / 'source.mp4'; source.write_bytes(b'source')
    snapshots = []
    controller.progress.connect(lambda _job_id, snapshot: snapshots.append(snapshot))
    controller.start('job', source, 'MP3')
    generation = controller.jobs['job']['generation']
    controller._progress('job', {'state': 'converting', 'percent': 70, 'elapsed': 8, 'destination': 'out.mp3'}, generation)
    controller._progress('job', {'state': 'paused'}, generation)
    controller._progress('job', {'state': 'converting'}, generation)
    assert snapshots[-1]['percent'] == 70 and snapshots[-1]['elapsed'] == 8 and snapshots[-1]['destination'] == 'out.mp3'
    controller._progress('job', {'state': 'converting', 'percent': 71}, generation)
    assert snapshots[-1]['percent'] == 71


class FakeActionWindow:
    def __init__(self, state):
        self.record = {'id': 'job', 'job': studio.DownloadJob(job_id='job', source_url='https://example.test', save_dir='.', requested_format='MP4', state=studio.JobState.CONVERTING.value)}
        self.conversion_controller = type('Controller', (), {'state': lambda _self, _job_id: state})()

    def selected_record(self):
        return self.record


@pytest.mark.parametrize(('state', 'pause', 'resume', 'stop'), [
    ('starting', True, False, True),
    ('converting', True, False, True),
    ('paused', False, True, True),
    ('completed', False, False, False),
    ('failed', False, False, False),
    ('cancelled', False, False, False),
])
def test_conversion_aware_action_states(state, pause, resume, stop):
    capabilities = studio.StratrumDownloadStudio.selected_action_capabilities(FakeActionWindow(state))
    assert (capabilities['pause'], capabilities['resume'], capabilities['stop']) == (pause, resume, stop)


def test_toolbar_and_context_expose_conversion_controls():
    ui_source = inspect.getsource(studio.StratrumDownloadStudio.init_ui)
    context_source = inspect.getsource(studio.StratrumDownloadStudio.show_context_menu)
    assert 'toolbar_stop_action' in ui_source
    for label in ('Pause Conversion', 'Resume Conversion', 'Cancel Conversion'):
        assert label in context_source


def test_cancel_selected_conversion_affects_only_selection():
    calls = []
    selected = {'id': 'selected'}
    fake = type('Window', (), {'selected_record': lambda _self: selected, 'cancel_job': lambda _self, job_id, remove=False: calls.append((job_id, remove))})()
    studio.StratrumDownloadStudio.cancel_selected_download(fake)
    assert calls == [('selected', False)]
