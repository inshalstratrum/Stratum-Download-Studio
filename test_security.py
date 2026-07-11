import io
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

import stratum_download_studio as stratrum_download_studio


TOKEN = 'b' * 64
ORIGIN = 'chrome-extension://' + ('a' * 32)
OTHER_ORIGIN = 'chrome-extension://' + ('b' * 32)
FIREFOX_ORIGIN = 'moz-extension://12345678-1234-1234-1234-123456789abc'
VALID_BODY = json.dumps({'url': 'https://example.com/video.mp4', 'action': 'quick_download'}).encode('utf-8')


def wait_qt(milliseconds):
    deadline = time.monotonic() + milliseconds / 1000
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)


class CountingLimiter:
    def __init__(self, allowed=True):
        self.calls = 0
        self.allowed = allowed

    def allow(self):
        self.calls += 1
        return self.allowed


@pytest.fixture
def runtime(tmp_path):
    return stratrum_download_studio.initialize_runtime(
        app_data_root=tmp_path / 'appdata',
        auth_token=TOKEN,
        allowed_origin=ORIGIN,
        rate_limiter=CountingLimiter(),
    )


@pytest.fixture
def unpaired_runtime(tmp_path):
    return stratrum_download_studio.initialize_runtime(
        app_data_root=tmp_path / 'appdata',
        auth_token=TOKEN,
        allowed_origin='',
        rate_limiter=CountingLimiter(),
    )


def validate(runtime, body=VALID_BODY, **header_overrides):
    headers = {
        'X-Stratrum-Auth': TOKEN,
        'Origin': ORIGIN,
        'Content-Type': 'application/json',
        'Content-Length': str(len(body)),
    }
    for name, value in header_overrides.items():
        header_name = name.replace('_', '-')
        if value is None:
            headers.pop(header_name, None)
        else:
            headers[header_name] = value
    return stratrum_download_studio.validate_request(headers, io.BytesIO(body), runtime)


@pytest.fixture
def server(runtime):
    httpd = stratrum_download_studio.http.server.ThreadingHTTPServer(('127.0.0.1', 0), stratrum_download_studio.DownloadServerHandler)
    httpd.app_config = runtime

    class SignalSpy:
        def __init__(self):
            self.urls = []

        def emit(self, url, action):
            self.urls.append((url, action))

    httpd.url_signal = SignalSpy()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def http_request(server, body=VALID_BODY, headers=None, path='/add_download'):
    request_headers = {
        'X-Stratrum-Auth': TOKEN,
        'Origin': ORIGIN,
        'Content-Type': 'application/json',
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        f'http://127.0.0.1:{server.server_port}{path}',
        data=body,
        headers=request_headers,
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


# HTTP validation and origin pairing

def test_http_valid_request(server):
    status, _ = http_request(server)
    assert status == 200
    assert server.url_signal.urls == [('https://example.com/video.mp4', 'quick_download')]


def test_http_missing_token(runtime):
    status, _ = validate(runtime, X_Stratrum_Auth=None)
    assert status == 401


def test_http_wrong_token(runtime):
    status, _ = validate(runtime, X_Stratrum_Auth='wrong')
    assert status == 401


def test_http_missing_origin(runtime):
    status, _ = validate(runtime, Origin=None)
    assert status == 403


def test_http_second_valid_origin_pairs(runtime):
    status, _ = validate(runtime, Origin=OTHER_ORIGIN)
    assert status == 200
    assert runtime.allowed_origins == [ORIGIN, OTHER_ORIGIN]


@pytest.mark.parametrize('origin', [
    'chrome-extension://short',
    f'{ORIGIN}/path',
    f'{ORIGIN}?query=1',
    'https://example.com',
    'extension://' + ('a' * 32),
], ids=['short-id', 'path', 'query', 'web-origin', 'unsupported-scheme'])
def test_http_malformed_origin(runtime, origin):
    status, _ = validate(runtime, Origin=origin)
    assert status == 403


def test_http_first_valid_origin_pairing(unpaired_runtime):
    status, result = validate(unpaired_runtime)
    assert (status, result) == (200, {'url': 'https://example.com/video.mp4', 'action': 'quick_download'})
    assert unpaired_runtime.allowed_origin == ORIGIN
    persisted = json.loads(unpaired_runtime.config_path.read_text(encoding='utf-8'))
    assert persisted['allowed_origins'] == [ORIGIN]


def test_http_correct_token_malformed_request_does_not_pair(unpaired_runtime):
    status, _ = validate(unpaired_runtime, body=b'{bad json')
    assert status == 400
    assert unpaired_runtime.allowed_origin == ''
    assert json.loads(unpaired_runtime.config_path.read_text(encoding='utf-8'))['allowed_origins'] == []


def test_http_application_json(runtime):
    assert validate(runtime, Content_Type='application/json')[0] == 200


def test_http_application_json_utf8_charset(runtime):
    assert validate(runtime, Content_Type='application/json; charset=utf-8')[0] == 200


def test_http_application_json_malicious_rejected(runtime):
    assert validate(runtime, Content_Type='application/json-malicious')[0] == 415


def test_http_text_plain_rejected(runtime):
    assert validate(runtime, Content_Type='text/plain')[0] == 415


def test_http_missing_content_type(runtime):
    assert validate(runtime, Content_Type=None)[0] == 415


def test_http_missing_content_length(runtime):
    assert validate(runtime, Content_Length=None)[0] == 400


def test_http_non_numeric_content_length(runtime):
    assert validate(runtime, Content_Length='many')[0] == 400


def test_http_negative_content_length(runtime):
    assert validate(runtime, Content_Length='-1')[0] == 400


def test_http_body_over_16kb(runtime):
    body = b'x' * (stratrum_download_studio.MAX_REQUEST_BODY + 1)
    assert validate(runtime, body=body)[0] == 413


def test_http_invalid_utf8(runtime):
    assert validate(runtime, body=b'\xff\xfe')[0] == 400


def test_http_invalid_json(runtime):
    assert validate(runtime, body=b'{broken')[0] == 400


@pytest.mark.parametrize('url', [
    '',
    'file:///C:/Windows/System32/calc.exe',
    'https:///missing-host',
    'https://user:password@example.com/file',
    'https://example.com/' + ('x' * 2048),
], ids=['empty', 'file-scheme', 'missing-hostname', 'embedded-credentials', 'excessive-length'])
def test_http_invalid_urls(runtime, url):
    body = json.dumps({'url': url}).encode('utf-8')
    assert validate(runtime, body=body)[0] == 400


def test_http_unknown_endpoint(server):
    assert http_request(server, path='/unknown')[0] == 404


def test_rate_limiting_only_after_authentication_and_structural_validation(tmp_path):
    limiter = CountingLimiter()
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN, rate_limiter=limiter)
    assert validate(config, X_Stratrum_Auth='wrong')[0] == 401
    assert validate(config, Content_Type='text/plain')[0] == 415
    assert validate(config, body=b'{bad')[0] == 400
    invalid_url = json.dumps({'url': 'file:///tmp/nope'}).encode()
    assert validate(config, body=invalid_url)[0] == 400
    assert limiter.calls == 0
    assert validate(config)[0] == 200
    assert limiter.calls == 1


def test_rate_limit_failure_does_not_pair(tmp_path):
    limiter = CountingLimiter(allowed=False)
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '', rate_limiter=limiter)
    assert validate(config)[0] == 429
    assert config.allowed_origin == ''


# Configuration and import isolation

def test_import_causes_no_filesystem_writes(tmp_path):
    local_app_data = tmp_path / 'localappdata'
    environment = os.environ.copy()
    environment['LOCALAPPDATA'] = str(local_app_data)
    environment['PYTHONPATH'] = str(Path(__file__).parent)
    result = subprocess.run(
        [sys.executable, '-c', 'import stratum_download_studio'],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not local_app_data.exists()


def test_corrupt_temporary_config_regeneration(tmp_path):
    root = tmp_path / 'appdata'
    config_path = root / 'config' / 'config.json'
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{corrupted json', encoding='utf-8')
    (config_path.parent / 'config_orphan.tmp').write_text('{also bad', encoding='utf-8')
    config = stratrum_download_studio.initialize_runtime(root)
    persisted = json.loads(config_path.read_text(encoding='utf-8'))
    assert stratrum_download_studio.validate_token(config.auth_token)
    assert persisted['auth_token'] == config.auth_token


def test_atomic_config_writing(tmp_path, monkeypatch):
    replacements = []
    real_replace = stratrum_download_studio.os.replace

    def replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        return real_replace(source, destination)

    monkeypatch.setattr(stratrum_download_studio.os, 'replace', replace)
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    assert replacements
    source, destination = replacements[-1]
    assert source.suffix == '.tmp'
    assert destination == config.config_path
    assert not source.exists()


@pytest.mark.parametrize(
    'token',
    ['', 'a' * 63, 'g' * 64, None, 123],
    ids=['empty', 'short', 'non-hex', 'none', 'non-string'],
)
def test_token_validation_rejects_invalid_values(token):
    assert not stratrum_download_studio.validate_token(token)


def test_token_validation_accepts_64_hex_characters():
    assert stratrum_download_studio.validate_token('A1' * 32)


def test_pairing_persistence(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    config.pair_origin(ORIGIN)
    assert stratrum_download_studio.initialize_runtime(tmp_path).allowed_origin == ORIGIN


def test_pairing_reset(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.reset_pairing()
    assert config.allowed_origin == ''
    assert stratrum_download_studio.initialize_runtime(tmp_path).allowed_origin == ''


def test_no_real_localappdata_path_touched_with_injected_root(tmp_path, monkeypatch):
    real_local_app_data = tmp_path / 'must-not-exist'
    injected = tmp_path / 'isolated'
    monkeypatch.setenv('LOCALAPPDATA', str(real_local_app_data))
    config = stratrum_download_studio.initialize_runtime(injected, TOKEN, '')
    assert config.app_data_root == injected
    assert not real_local_app_data.exists()


# Completed-file path and Windows opening safety

def make_record(save_dir, final_path):
    return {
        'save_dir': str(save_dir),
        'outtmpl': str(Path(save_dir) / '%(title)s.%(ext)s'),
        'final_path': str(final_path),
    }


def test_safe_open_calls_startfile_exactly_once(tmp_path):
    completed = tmp_path / 'safe.mp4'
    completed.touch()
    calls = []
    stratrum_download_studio.open_download_file(make_record(tmp_path, completed), opener=calls.append)
    assert calls == [str(completed.resolve())]


def test_dangerous_open_never_calls_startfile(tmp_path):
    completed = tmp_path / 'unsafe.exe'
    completed.touch()
    calls = []
    with pytest.raises(PermissionError):
        stratrum_download_studio.open_download_file(make_record(tmp_path, completed), opener=calls.append)
    assert calls == []


def test_missing_file_never_opens(tmp_path):
    calls = []
    with pytest.raises(FileNotFoundError):
        stratrum_download_studio.open_download_file(make_record(tmp_path, tmp_path / 'missing.mp4'), opener=calls.append)
    assert calls == []


def test_out_of_directory_file_never_opens(tmp_path):
    save_dir = tmp_path / 'downloads'
    save_dir.mkdir()
    outside = tmp_path / 'outside.mp4'
    outside.touch()
    calls = []
    with pytest.raises(ValueError):
        stratrum_download_studio.open_download_file(make_record(save_dir, outside), opener=calls.append)
    assert calls == []


def test_valid_open_folder_uses_list_subprocess_arguments(tmp_path):
    completed = tmp_path / 'safe.mp4'
    completed.touch()
    calls = []
    stratrum_download_studio.open_download_folder(make_record(tmp_path, completed), popen=calls.append)
    assert calls == [['explorer', '/select,', str(completed.resolve())]]


def test_dangerous_valid_file_can_open_folder(tmp_path):
    completed = tmp_path / 'unsafe.exe'
    completed.touch()
    calls = []
    stratrum_download_studio.open_download_folder(make_record(tmp_path, completed), popen=calls.append)
    assert calls == [['explorer', '/select,', str(completed.resolve())]]


def test_manipulated_history_path_is_rejected(tmp_path):
    save_dir = tmp_path / 'downloads'
    save_dir.mkdir()
    outside = tmp_path / 'outside.mp4'
    outside.touch()
    manipulated = save_dir / '..' / 'outside.mp4'
    with pytest.raises(ValueError):
        stratrum_download_studio.resolve_recorded_file(make_record(save_dir, manipulated))


# Conversion behavior

def run_conversion(thread):
    events = []
    thread.finished.connect(lambda *args: events.append(args))
    thread.run()
    assert len(events) == 1
    return events[0]


VIDEO_PROBE = {'format_name': 'mov,mp4,m4a,3gp,3g2,mj2', 'duration': 10.0, 'major_brand': 'isom', 'streams': [
    {'codec_type': 'video', 'codec_name': 'h264', 'width': 320, 'height': 180},
    {'codec_type': 'audio', 'codec_name': 'aac'},
]}
AUDIO_PROBE = {'format_name': 'mov,mp4,m4a,3gp,3g2,mj2', 'duration': 10.0, 'major_brand': 'M4A ', 'streams': [
    {'codec_type': 'audio', 'codec_name': 'aac'},
]}


def mock_conversion_pipeline(monkeypatch, probe, returncode=0, stderr='', write_output=True, progress=None):
    commands = []

    class FakePopen:
        def __init__(self, args, **kwargs):
            commands.append(args)
            if write_output:
                Path(args[-1]).write_bytes(b'converted-media')
            lines = progress or ['out_time_us=5000000\n', 'progress=continue\n', 'out_time_us=10000000\n', 'progress=end\n']
            self.stdout = io.StringIO(''.join(lines)); self.stderr = io.StringIO(stderr)
            if hasattr(kwargs.get('stderr'), 'write'):
                kwargs['stderr'].write(stderr); kwargs['stderr'].flush()
            self.returncode = returncode

        def poll(self): return self.returncode
        def wait(self, timeout=None): return self.returncode
        def terminate(self): self.returncode = -15
        def kill(self): self.returncode = -9

    format_by_extension = {
        '.mp4': ('mov,mp4,m4a,3gp,3g2,mj2', 'isom'), '.mov': ('mov,mp4,m4a,3gp,3g2,mj2', 'qt  '),
        '.mkv': ('matroska,webm', ''), '.webm': ('matroska,webm', ''), '.avi': ('avi', ''),
        '.mp3': ('mp3', ''), '.m4a': ('mov,mp4,m4a,3gp,3g2,mj2', 'M4A '), '.aac': ('aac', ''),
        '.wav': ('wav', ''), '.flac': ('flac', ''), '.ogg': ('ogg', ''), '.opus': ('ogg', ''),
    }

    def mocked_probe(path, *args, **kwargs):
        candidate = Path(path)
        if candidate.exists() and candidate.stat().st_size == 0:
            return probe
        format_name, brand = format_by_extension[candidate.suffix.lower()]
        audio_target = candidate.suffix.lower().lstrip('.') in stratrum_download_studio.AUDIO_EXTENSIONS
        streams = [{'codec_type': 'audio', 'codec_name': 'mock'}] if audio_target else VIDEO_PROBE['streams']
        return {'format_name': format_name, 'major_brand': brand, 'duration': 10.0, 'streams': streams}

    monkeypatch.setattr(stratrum_download_studio, 'probe_media_file', mocked_probe)
    monkeypatch.setattr(stratrum_download_studio.subprocess, 'Popen', FakePopen)
    return commands


def test_conversion_missing_input(tmp_path):
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(tmp_path / 'missing.mp4'), 'mp3'))
    assert event[1] is False
    assert event[3] == ''


def test_conversion_unsupported_format(tmp_path):
    source = tmp_path / 'source.mp4'
    source.touch()
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'exe'))
    assert event[1] is False
    assert event[3] == ''


def test_conversion_unique_output(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    (tmp_path / 'video_converted.mp3').touch()

    mock_conversion_pipeline(monkeypatch, VIDEO_PROBE)
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is True
    assert event[3].endswith('video_converted_1.mp3')


def test_conversion_uses_y_only_for_unique_temporary_output(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    commands = mock_conversion_pipeline(monkeypatch, VIDEO_PROBE)
    assert run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))[1] is True
    assert '-y' in commands[0] and '.partial-' in Path(commands[0][-1]).name
    assert Path(commands[0][-1]) != source


def test_failed_ffmpeg_does_not_report_success(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    mock_conversion_pipeline(monkeypatch, VIDEO_PROBE, returncode=1, stderr='ffmpeg failed')
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert event[3] == ''


def test_successful_conversion_output_path_is_stored(tmp_path):
    source = tmp_path / 'video.mp4'
    output = tmp_path / 'video_converted.mp3'
    source.touch()
    output.touch()
    record = make_record(tmp_path, source)
    original = record['final_path']
    stored = stratrum_download_studio.store_conversion_output(record, output)
    assert record['converted_output_path'] == str(stored)
    assert record['final_path'] == original


def test_conversion_output_must_exist_before_success(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    mock_conversion_pipeline(monkeypatch, VIDEO_PROBE, write_output=False)
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert event[3] == ''


def test_conversion_timeout_reports_failure(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()

    monkeypatch.setattr(stratrum_download_studio, 'probe_media_file', lambda *args, **kwargs: VIDEO_PROBE)
    monkeypatch.setattr(stratrum_download_studio.subprocess, 'Popen', lambda args, **kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired(args, 1)))
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert 'timed out' in event[2].lower()


def test_conversion_signal_and_slot_signatures_match():
    parameters = list(inspect.signature(stratrum_download_studio.StratrumDownloadStudio.conversion_done).parameters)
    assert parameters == ['self', 'row_id', 'success', 'msg', 'output_path']


def test_active_source_has_no_forbidden_legacy_patterns():
    forbidden = handoff_block('active-forbidden')
    active_files = [
        *Path('.').glob('*.py'),
        *Path('.').glob('*.spec'),
        Path('.gitignore'),
        *Path('browser_extension').glob('*'),
        *Path('firefox_extension').glob('*'),
    ]
    for source_path in active_files:
        if not source_path.is_file():
            continue
        content = source_path.read_text(encoding='utf-8')
        for obsolete in forbidden:
            assert obsolete not in content, f'{obsolete!r} found in {source_path}'


HANDOFF_PATH = Path('docs/10_PHASE_2A_FINAL_CLEANUP_HANDOFF.md')


def handoff_block(name):
    content = HANDOFF_PATH.read_text(encoding='utf-8')
    start = f'<!-- {name}:start -->'
    end = f'<!-- {name}:end -->'
    block = content.split(start, 1)[1].split(end, 1)[0]
    return [line.strip() for line in block.splitlines() if line.strip()]


def test_final_module_import_without_filesystem_writes(tmp_path):
    local_app_data = tmp_path / 'untouched'
    environment = os.environ.copy()
    environment['LOCALAPPDATA'] = str(local_app_data)
    environment['PYTHONPATH'] = str(Path(__file__).parent)
    result = subprocess.run(
        [sys.executable, '-c', 'from stratum_download_studio import StratrumDownloadStudio, DownloadServerHandler'],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not local_app_data.exists()


def test_normal_startup_has_no_automatic_extension_prompt():
    source = Path('stratum_download_studio.py').read_text(encoding='utf-8')
    assert 'show_extension_install_prompt' not in source
    assert 'Install Extension' not in source


def test_browser_integration_remains_manual_in_options():
    source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.show_preferences)
    assert 'BrowserIntegrationDialog' in source


def test_browser_integration_supports_reset_all():
    assert hasattr(stratrum_download_studio.BrowserIntegrationDialog, 'reset_all_pairings')


def test_browser_integration_supports_individual_origin_removal():
    assert hasattr(stratrum_download_studio.BrowserIntegrationDialog, 'remove_selected_origin')


def test_extension_guide_remains_manual():
    assert hasattr(stratrum_download_studio.BrowserIntegrationDialog, 'open_guide')


def test_load_unpacked_guide_opens_real_readme():
    opened = []
    assert stratrum_download_studio.open_browser_extension_guide(opener=opened.append)
    assert opened == [(Path('browser_extension') / 'README.md').resolve()]
    assert opened[0].is_file()


def test_final_module_class_handler_and_spec_names():
    assert stratrum_download_studio.StratrumDownloadStudio.__name__ == 'StratrumDownloadStudio'
    assert stratrum_download_studio.DownloadServerHandler.__name__ == 'DownloadServerHandler'
    assert Path('stratum_download_studio.py').is_file()
    assert Path('StratumDownloadStudio.spec').is_file()


def test_cleanup_paths_do_not_exist():
    for removed_path in handoff_block('deleted-paths'):
        assert not Path(removed_path).exists(), removed_path


def test_final_spec_uses_final_entrypoint_and_executable_name():
    spec = Path('StratumDownloadStudio.spec').read_text(encoding='utf-8')
    assert "['stratum_download_studio.py']" in spec
    assert "name='StratumDownloadStudio'" in spec


def test_generated_directories_are_ignored():
    ignore_rules = set(Path('.gitignore').read_text(encoding='utf-8').splitlines())
    assert {'__pycache__/', '.pytest_cache/', 'build/', 'dist/', 'extension_packages/', 'downloads/'} <= ignore_rules


# Phase 2A.4 multi-browser pairing

def test_legacy_allowed_origin_migrates_to_allowed_origins(tmp_path):
    config_path = tmp_path / 'config' / 'config.json'
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({'auth_token': TOKEN, 'allowed_origin': ORIGIN}), encoding='utf-8')
    config = stratrum_download_studio.initialize_runtime(tmp_path)
    persisted = json.loads(config_path.read_text(encoding='utf-8'))
    assert config.allowed_origins == [ORIGIN]
    assert persisted['allowed_origins'] == [ORIGIN]
    assert 'allowed_origin' not in persisted


def test_chrome_edge_and_firefox_origins_pair_concurrently(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    for origin in (ORIGIN, OTHER_ORIGIN, FIREFOX_ORIGIN):
        assert config.pair_origin(origin)
    assert config.allowed_origins == [ORIGIN, OTHER_ORIGIN, FIREFOX_ORIGIN]


def test_duplicate_origin_is_not_added_twice(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    assert config.pair_origin(ORIGIN)
    assert config.pair_origin(ORIGIN) is False
    assert config.allowed_origins == [ORIGIN]


def test_paired_origin_limit_is_enforced(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    origins = [f"chrome-extension://{chr(ord('a') + index) * 32}" for index in range(stratrum_download_studio.MAX_PAIRED_ORIGINS + 1)]
    for origin in origins[:-1]:
        config.pair_origin(origin)
    with pytest.raises(stratrum_download_studio.PairingLimitError):
        config.pair_origin(origins[-1])
    assert len(config.allowed_origins) == stratrum_download_studio.MAX_PAIRED_ORIGINS


def test_unauthorized_request_cannot_pair_new_origin(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    status, _ = validate(config, X_Stratrum_Auth='wrong', Origin=OTHER_ORIGIN)
    assert status == 401
    assert config.allowed_origins == []


def test_reset_all_origins_persists(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '', allowed_origins=[ORIGIN, OTHER_ORIGIN, FIREFOX_ORIGIN])
    config.reset_all_origins()
    assert config.allowed_origins == []
    assert stratrum_download_studio.initialize_runtime(tmp_path).allowed_origins == []


def test_individual_origin_removal_persists(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '', allowed_origins=[ORIGIN, OTHER_ORIGIN])
    assert config.remove_origin(ORIGIN)
    assert config.allowed_origins == [OTHER_ORIGIN]
    assert stratrum_download_studio.initialize_runtime(tmp_path).allowed_origins == [OTHER_ORIGIN]


def test_malformed_and_duplicate_stored_origins_are_filtered(tmp_path):
    config = stratrum_download_studio.initialize_runtime(
        tmp_path, TOKEN, '', allowed_origins=[ORIGIN, ORIGIN, 'https://example.com', FIREFOX_ORIGIN]
    )
    assert config.allowed_origins == [ORIGIN, FIREFOX_ORIGIN]


# Phase 2A.4 numeric progress and UI propagation

def test_numeric_byte_progress_snapshot():
    snapshot = stratrum_download_studio.build_progress_snapshot({
        'status': 'downloading', 'filename': 'C:/downloads/video.mp4',
        'downloaded_bytes': 500, 'total_bytes': 1000, 'speed': 2048, 'eta': 65,
    })
    assert snapshot == {
        'filename': 'video.mp4', 'percent': 50.0, 'downloaded': '500.00 B',
        'total': '1000.00 B', 'speed': '2.00 KB/s', 'eta': '00:01:05', 'status': 'Downloading'
    }


def test_numeric_progress_hook_emits_all_transfer_fields(tmp_path):
    thread = stratrum_download_studio.DownloadThread('id', 'https://example.com', str(tmp_path / '%(title)s.%(ext)s'), 'best', 'mp4')
    events = []
    thread.progress.connect(lambda *args: events.append(args))
    thread.progress_hook({
        'status': 'downloading', 'filename': str(tmp_path / 'video.mp4'),
        'downloaded_bytes': 500, 'total_bytes': 1000, 'speed': 2048, 'eta': 65,
    })
    assert events == [('id', 'video.mp4', 50.0, '500.00 B', '1000.00 B', '2.00 KB/s', '00:01:05', 'Downloading')]


def test_estimated_total_size_progress():
    snapshot = stratrum_download_studio.build_progress_snapshot({
        'downloaded_bytes': 3_000, 'total_bytes_estimate': 12_000,
    })
    assert snapshot['percent'] == 25.0
    assert snapshot['total'] == '11.72 KB'


def test_ansi_formatted_percent_fallback():
    snapshot = stratrum_download_studio.build_progress_snapshot({
        '_percent_str': '\x1b[0;32m42.5%\x1b[0m',
        '_speed_str': '\x1b[0;32m1.2 MiB/s\x1b[0m',
        '_eta_str': '\x1b[0;32m00:04\x1b[0m',
    })
    assert snapshot['percent'] == 42.5
    assert snapshot['speed'] == '1.2 MiB/s'
    assert snapshot['eta'] == '00:04'


def test_progress_without_total_size_is_safe():
    snapshot = stratrum_download_studio.build_progress_snapshot({'downloaded_bytes': 1024})
    assert snapshot['percent'] == 0.0
    assert snapshot['downloaded'] == '1.00 KB'
    assert snapshot['total'] == 'N/A'


@pytest.mark.parametrize(('downloaded', 'total', 'expected'), [
    (200, 100, 100.0),
    (-20, 100, 0.0),
])
def test_progress_percent_is_clamped(downloaded, total, expected):
    snapshot = stratrum_download_studio.build_progress_snapshot({
        'downloaded_bytes': downloaded, 'total_bytes': total,
    })
    assert snapshot['percent'] == expected


def test_popup_filename_and_downloaded_label_update():
    popup = stratrum_download_studio.DownloadProgressPopup('Connecting...', 'https://example.com')
    popup.update_stats('actual-video.mp4', 50.0, '5.00 MB', '10.00 MB', '1.00 MB/s', '00:00:05', 'Downloading')
    assert popup.filename == 'actual-video.mp4'
    assert popup.windowTitle() == '50% actual-video.mp4'
    assert popup.downloaded_lbl.text() == '5.00 MB / 10.00 MB (50.0%)'
    popup.close()


def test_transfer_size_format_used_by_main_table_and_popup():
    assert stratrum_download_studio.format_transfer_size('5.00 MB', '10.00 MB') == '5.00 MB / 10.00 MB'
    assert stratrum_download_studio.format_transfer_size('5.00 MB', 'N/A') == '5.00 MB / unknown total'


def test_finished_progress_hook_enters_postprocessing_not_completion(tmp_path):
    source = tmp_path / 'complete.mp4'
    source.touch()
    thread = stratrum_download_studio.DownloadThread('id', 'https://example.com', str(tmp_path / '%(title)s.%(ext)s'), 'best', 'mp4')
    events = []
    thread.progress.connect(lambda *args: events.append(args))
    thread.progress_hook({
        'status': 'finished', 'filename': str(source), 'downloaded_bytes': 100, 'total_bytes': 100,
    })
    assert events[0][2] == 100.0
    assert events[0][7] == 'Postprocessing'


def test_fragmented_media_uses_numeric_aggregate_progress():
    snapshot = stratrum_download_studio.build_progress_snapshot({
        'fragment_index': 4, 'fragment_count': 10,
        'downloaded_bytes': 4_000_000, 'total_bytes_estimate': 10_000_000,
    })
    assert snapshot['percent'] == 40.0


def test_malformed_progress_input_does_not_crash():
    malformed = {
        'status': 'downloading',
        'filename': object(), 'downloaded_bytes': 'broken', 'total_bytes': {},
        'speed': float('nan'), 'eta': [], '_percent_str': 'not a percent', 'info_dict': 'bad',
    }
    snapshot = stratrum_download_studio.build_progress_snapshot(malformed)
    assert snapshot['percent'] == 0.0
    assert snapshot['total'] == 'N/A'
    thread = stratrum_download_studio.DownloadThread('id', 'https://example.com', 'unused', 'best', 'mp4')
    events = []
    thread.progress.connect(lambda *args: events.append(args))
    thread.progress_hook(malformed)
    assert len(events) == 1


def test_progress_signal_and_main_slot_signatures_match():
    parameters = list(inspect.signature(stratrum_download_studio.StratrumDownloadStudio.update_progress).parameters)
    assert parameters == ['self', 'id', 'filename', 'percent', 'downloaded', 'total', 'speed', 'eta', 'status']


# Phase 2A.4 extension sources and packaging

def test_chromium_manifest_enables_http_https_media_detection():
    manifest = json.loads(Path('browser_extension/manifest.json').read_text(encoding='utf-8'))
    assert manifest['manifest_version'] == 3
    assert manifest['background'] == {'service_worker': 'background.js'}
    assert manifest['content_scripts'][0]['matches'] == ['http://*/*', 'https://*/*']
    assert manifest['content_scripts'][0]['js'] == ['content.js']


def test_firefox_manifest_has_stable_id_and_background_script():
    manifest = json.loads(Path('firefox_extension/manifest.json').read_text(encoding='utf-8'))
    gecko = manifest['browser_specific_settings']['gecko']
    assert manifest['manifest_version'] == 3
    assert manifest['background'] == {'scripts': ['background.js']}
    assert gecko['id'] == 'stratrum-download-studio@stratrum.local'
    assert gecko['data_collection_permissions']['required'] == ['none']


def test_media_content_script_is_dynamic_deduplicated_and_click_driven():
    content = Path('browser_extension/content.js').read_text(encoding='utf-8')
    for required in ('MutationObserver', 'addedNodes', 'video, audio', 'mediaButtons.has', 'currentSrc', 'addEventListener("click"', 'stratrum-download-request'):
        assert required in content
    request_body = content.split('async function requestDownload', 1)[1].split('function positionButtons', 1)[0]
    assert 'chooseDownloadUrl(mediaElement)' in request_body


def test_media_content_script_uses_page_fallback_without_sensitive_reads():
    content = Path('browser_extension/content.js').read_text(encoding='utf-8')
    assert 'window.location.href' in content
    assert 'm3u8|mpd|m4s' in content
    assert 'mediaElement.srcObject' in content
    for forbidden in ('document.cookie', 'localStorage', 'browsingData', 'history.search', 'querySelectorAll("input'):
        assert forbidden not in content


def test_media_button_option_is_default_enabled_and_persisted():
    html = Path('browser_extension/options.html').read_text(encoding='utf-8')
    script = Path('browser_extension/options.js').read_text(encoding='utf-8')
    assert 'id="show-media-buttons" checked' in html
    assert 'showMediaButtons !== false' in script
    assert 'showMediaButtons: event.target.checked' in script


def test_extension_connection_errors_are_visible_and_token_is_not_logged():
    background = Path('browser_extension/background.js').read_text(encoding='utf-8')
    for code in ('missing_token', 'desktop_unavailable', 'pairing_rejected', 'openOptionsPage', 'stratrum-status'):
        assert code in background
    assert 'console.' not in background


def test_right_click_workflow_remains_registered():
    background = Path('browser_extension/background.js').read_text(encoding='utf-8')
    assert 'contexts: ["link", "video", "audio"]' in background
    assert 'info.linkUrl || info.srcUrl || info.pageUrl' in background


def test_packaging_script_creates_three_packages_without_random_ids():
    script = Path('browser_extension/package_extension.ps1').read_text(encoding='utf-8')
    for browser in ('chrome.zip', 'edge.zip', 'firefox.zip'):
        assert browser in script
    for forbidden in ('New-Guid', '[guid]::NewGuid', 'token_hex', 'random'):
        assert forbidden not in script


def test_distribution_documentation_records_browser_limits():
    readme = Path('browser_extension/README.md').read_text(encoding='utf-8')
    for required in ('Chrome Web Store', 'Microsoft Edge Add-ons', 'Mozilla-signed XPI', 'Enterprise force-install', 'user-confirmed'):
        assert required in readme
    assert 'silent consumer installation' in readme


def test_chromium_development_uses_single_unpacked_source():
    readme = Path('browser_extension/README.md').read_text(encoding='utf-8')
    assert 'Choose this `browser_extension/` directory directly' in readme
    assert 'Do not install the unpacked source and an extracted submission package simultaneously' in readme
    assert 'Sleeping is not an error' in readme


# Phase 2A.5 output profiles, final tracking, and resolution selection

PROFILE_PROBES = {
    'MP4': ('mov,mp4,m4a,3gp,3g2,mj2', ['video', 'audio']),
    'MKV': ('matroska,webm', ['video', 'audio']),
    'WEBM': ('matroska,webm', ['video', 'audio']),
    'AVI': ('avi', ['video', 'audio']),
    'MOV': ('mov,mp4,m4a,3gp,3g2,mj2', ['video', 'audio']),
    'MP3': ('mp3', ['audio']),
    'M4A': ('mov,mp4,m4a,3gp,3g2,mj2', ['audio']),
    'AAC': ('aac', ['audio']),
    'WAV': ('wav', ['audio']),
    'FLAC': ('flac', ['audio']),
    'OGG': ('ogg', ['audio']),
    'OPUS': ('ogg', ['audio']),
}


def probe_result(format_name, stream_types):
    brand_by_extension = {'.mp4': 'isom', '.mov': 'qt  ', '.m4a': 'M4A '}
    payload = {
        'streams': [{'codec_type': stream_type, 'codec_name': 'mock', 'height': 1080 if stream_type == 'video' else None} for stream_type in stream_types],
    }

    def runner(command, **kwargs):
        payload['format'] = {'format_name': format_name, 'tags': {'major_brand': brand_by_extension.get(Path(command[-1]).suffix.lower(), '')}}
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload).encode(), stderr=b'')

    return runner


@pytest.mark.parametrize('profile_name', list(PROFILE_PROBES))
def test_each_output_profile_resolves_real_final_path(tmp_path, profile_name):
    profile = stratrum_download_studio.output_profile(profile_name)
    output = tmp_path / f'finished.{profile.extension}'
    output.write_bytes(b'media')
    format_name, streams = PROFILE_PROBES[profile_name]
    resolved, probe = stratrum_download_studio.resolve_final_media(
        {}, [str(output)], tmp_path, profile_name, probe_runner=probe_result(format_name, streams)
    )
    assert resolved == output.resolve()
    assert resolved.suffix == f'.{profile.extension}'
    assert probe['format_name'] == format_name


@pytest.mark.parametrize('profile_name', list(PROFILE_PROBES))
def test_mocked_extractor_pipeline_returns_requested_actual_output(tmp_path, profile_name, monkeypatch):
    profile = stratrum_download_studio.output_profile(profile_name)
    output = tmp_path / f'extractor-final.{profile.extension}'
    format_name, stream_types = PROFILE_PROBES[profile_name]

    class MockYDL:
        def __init__(self, options): self.options = options; self.params = options
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def extract_info(self, url, download=True):
            output.write_bytes(b'final-media')
            for hook in self.options['postprocessor_hooks']:
                hook({'status': 'finished', 'filepath': str(output), 'info_dict': {'filepath': str(output)}})
            return {'filepath': str(output)}

    monkeypatch.setattr(stratrum_download_studio.yt_dlp, 'YoutubeDL', MockYDL)
    monkeypatch.setattr(stratrum_download_studio, 'probe_media_file', lambda path, runner=None: {
        'format_name': format_name,
        'major_brand': {'MP4': 'isom', 'MOV': 'qt  ', 'M4A': 'M4A '}.get(profile_name, ''),
        'streams': [{'codec_type': stream_type, 'codec_name': 'mock', 'height': 1080 if stream_type == 'video' else None} for stream_type in stream_types],
    })
    thread = stratrum_download_studio.DownloadThread(
        'id', 'https://example.com/media', str(tmp_path / '%(title)s.%(ext)s'),
        None, profile_name, requested_height=1080, metadata=sample_format_info(), save_dir=tmp_path,
    )
    events = []; thread.finished.connect(lambda *args: events.append(args)); thread.run()
    assert events == [('id', True, '', str(output.resolve()))]
    assert Path(events[0][3]).suffix == f'.{profile.extension}'


def test_output_profiles_cover_exact_video_and_audio_sets():
    assert set(stratrum_download_studio.OUTPUT_PROFILES) == {'MP4', 'MKV', 'WEBM', 'AVI', 'MOV', 'MP3', 'M4A', 'AAC', 'WAV', 'FLAC', 'OGG', 'OPUS'}
    assert {name for name, profile in stratrum_download_studio.OUTPUT_PROFILES.items() if profile.media_kind == 'video'} == {'MP4', 'MKV', 'WEBM', 'AVI', 'MOV'}
    assert {name for name, profile in stratrum_download_studio.OUTPUT_PROFILES.items() if profile.media_kind == 'audio'} == {'MP3', 'M4A', 'AAC', 'WAV', 'FLAC', 'OGG', 'OPUS'}


def test_download_engine_never_changes_media_format_by_extension_rename():
    source = inspect.getsource(stratrum_download_studio.DownloadThread.run)
    assert 'os.replace' not in source
    assert 'resolve_final_media' in source


def test_download_template_uses_stable_job_suffix_for_no_overwrite():
    source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.start_new_download)
    assert 'download_id[:8]' in source
    assert "'overwrites': False" in inspect.getsource(stratrum_download_studio.build_download_options)


def test_profile_options_use_real_postprocessors(tmp_path):
    compatible = {'formats': [{'ext': 'mp4', 'vcodec': 'avc1.640028', 'height': 1080}, {'ext': 'm4a', 'acodec': 'mp4a.40.2'}]}
    mp4 = stratrum_download_studio.build_download_options('MP4', 'out', 1080, compatible)
    fallback_mp4 = stratrum_download_studio.build_download_options('MP4', 'out', 1080, {})
    assert mp4['merge_output_format'] == 'mp4' and 'postprocessors' not in mp4
    assert fallback_mp4['postprocessors'][0] == {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}
    assert stratrum_download_studio.build_download_options('AVI', 'out')['postprocessors'][0]['key'] == 'FFmpegVideoConvertor'
    assert stratrum_download_studio.build_download_options('MOV', 'out')['postprocessors'][0]['key'] == 'FFmpegVideoConvertor'
    assert stratrum_download_studio.build_download_options('MKV', 'out')['postprocessors'][0]['key'] == 'FFmpegVideoRemuxer'
    assert stratrum_download_studio.build_download_options('WEBM', 'out')['merge_output_format'] == 'webm'
    for audio in ('MP3', 'M4A', 'AAC', 'WAV', 'FLAC', 'OGG', 'OPUS'):
        options = stratrum_download_studio.build_download_options(audio, 'out')
        expected_codec = {'OGG': 'vorbis'}.get(audio, audio.lower())
        assert options['postprocessors'][0]['preferredcodec'] == expected_codec


def test_postprocessor_hook_path_is_final_candidate():
    event = {'status': 'finished', 'info_dict': {'filepath': 'C:/downloads/final.mp4'}}
    assert stratrum_download_studio.postprocessor_output_path(event) == 'C:/downloads/final.mp4'
    assert stratrum_download_studio.postprocessor_output_path({'status': 'started', 'filename': 'intermediate.webm'}) is None


def test_thumbnail_is_rejected_as_completed_media(tmp_path):
    thumbnail = tmp_path / 'video.webp'; thumbnail.touch()
    with pytest.raises(ValueError, match='Thumbnail'):
        stratrum_download_studio.validate_final_media(thumbnail, tmp_path, 'MP4')


@pytest.mark.parametrize('filename,profile', [('video.f140.m4a', 'M4A'), ('video.f251.webm', 'WEBM')])
def test_intermediate_stream_is_rejected(filename, profile, tmp_path):
    intermediate = tmp_path / filename; intermediate.touch()
    with pytest.raises(ValueError, match='Intermediate'):
        stratrum_download_studio.validate_final_media(intermediate, tmp_path, profile)


@pytest.mark.parametrize('profile,streams,error', [('MP4', ['audio'], 'video stream'), ('MP3', ['video'], 'audio stream')])
def test_stream_validation_requires_requested_media_kind(profile, streams, error, tmp_path):
    extension = stratrum_download_studio.output_profile(profile).extension
    output = tmp_path / f'bad.{extension}'; output.touch()
    format_name = PROFILE_PROBES[profile][0]
    with pytest.raises(ValueError, match=error):
        stratrum_download_studio.validate_final_media(output, tmp_path, profile, probe_runner=probe_result(format_name, streams))


def test_wrong_container_is_rejected_even_with_matching_extension(tmp_path):
    output = tmp_path / 'fake.mp4'; output.touch()
    with pytest.raises(ValueError, match='container'):
        stratrum_download_studio.validate_final_media(output, tmp_path, 'MP4', probe_runner=probe_result('matroska', ['video']))


@pytest.mark.parametrize('filename,profile,brand', [('fake.mp4', 'MP4', 'qt  '), ('fake.mov', 'MOV', 'isom')])
def test_mp4_and_mov_brand_mismatch_is_rejected(filename, profile, brand, tmp_path):
    output = tmp_path / filename; output.touch()
    payload = {'format': {'format_name': 'mov,mp4,m4a,3gp,3g2,mj2', 'tags': {'major_brand': brand}}, 'streams': [{'codec_type': 'video'}]}
    runner = lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload).encode(), stderr=b'')
    with pytest.raises(ValueError, match='brand'):
        stratrum_download_studio.validate_final_media(output, tmp_path, profile, probe_runner=runner)


def test_preexisting_output_is_not_accepted_as_new_final(tmp_path):
    output = tmp_path / 'existing.mp4'; output.touch()
    candidates = stratrum_download_studio.collect_output_candidates({}, [str(output)], tmp_path, 'mp4', {str(output.resolve())})
    assert candidates == []


def test_postprocessing_failure_retains_intermediate_and_never_completes(tmp_path, monkeypatch):
    intermediate = tmp_path / 'video.f140.m4a'

    class FailingYDL:
        def __init__(self, options): self.options = options; self.params = options
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def extract_info(self, url, download=True):
            intermediate.write_bytes(b'useful partial')
            raise RuntimeError('merge failed https://example.com/media?secret=hidden')

    monkeypatch.setattr(stratrum_download_studio.yt_dlp, 'YoutubeDL', FailingYDL)
    thread = stratrum_download_studio.DownloadThread('id', 'https://example.com/media', str(tmp_path / '%(title)s.%(ext)s'), 'best', 'MP4', save_dir=tmp_path)
    statuses, events = [], []
    thread.status.connect(lambda *args: statuses.append(args))
    thread.finished.connect(lambda *args: events.append(args))
    thread.run()
    assert intermediate.exists()
    assert events[0][1] is False
    assert '[URL omitted]' in events[0][2]
    assert all(status[1] != 'Completed' for status in statuses)


def test_verified_success_removes_only_known_intermediates(tmp_path):
    final = tmp_path / 'final.mp4'; final.touch()
    video_part = tmp_path / 'video.f137.mp4'; video_part.touch()
    audio_part = tmp_path / 'video.f140.m4a'; audio_part.touch()
    unrelated = tmp_path / 'keep.txt'; unrelated.touch()
    removed = stratrum_download_studio.cleanup_verified_intermediates(
        [video_part, audio_part, unrelated], final, tmp_path
    )
    assert set(removed) == {video_part.resolve(), audio_part.resolve()}
    assert final.exists() and unrelated.exists()


def sample_format_info():
    return {'formats': [
        {'format_id': 'v2160', 'height': 2160, 'vcodec': 'vp9', 'acodec': 'none', 'ext': 'webm', 'filesize': 40_000_000},
        {'format_id': 'v1080', 'height': 1080, 'vcodec': 'avc1', 'acodec': 'none', 'ext': 'mp4', 'filesize_approx': 20_000_000},
        {'format_id': 'v720', 'height': 720, 'vcodec': 'avc1', 'acodec': 'none', 'ext': 'mp4', 'filesize': 10_000_000},
        {'format_id': 'a1', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'ext': 'm4a', 'filesize': 2_000_000},
    ]}


def test_resolution_availability_uses_stream_height_and_details():
    options = stratrum_download_studio.available_resolution_options(sample_format_info())
    assert [item['height'] for item in options] == [2160, 1080, 720]
    assert options[1]['vcodec'] == 'avc1' and options[1]['acodec'] == 'mp4a.40.2'
    detail = stratrum_download_studio.format_resolution_detail(options[1])
    assert '1080p / Full HD' in detail and 'avc1' in detail and 'mp4a' in detail and 'MB' in detail


def test_unavailable_resolution_falls_back_to_highest_below():
    options = stratrum_download_studio.available_resolution_options(sample_format_info())
    assert stratrum_download_studio.choose_resolution(options, 1440)['height'] == 1080
    assert stratrum_download_studio.choose_resolution(options, 4320)['height'] == 2160
    assert stratrum_download_studio.choose_resolution(options, None)['height'] == 2160


def test_format_selector_uses_height_not_width():
    selector = stratrum_download_studio.build_format_selector('MP4', 1080)
    assert '[height<=1080]' in selector
    assert 'width' not in selector


def test_audio_profile_disables_resolution_selection(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    dialog = stratrum_download_studio.DownloadFileInfoDialog(app_config=config)
    dialog.resolution_options = stratrum_download_studio.available_resolution_options(sample_format_info())
    dialog.ext_combo.setCurrentText('MP3')
    dialog.on_ext_changed('MP3')
    assert not dialog.resolution_combo.isEnabled()
    assert 'Audio-only profile' in dialog.info_lbl.text()
    dialog.close()


def test_format_discovery_is_debounced_and_stale_results_ignored(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    dialog = stratrum_download_studio.DownloadFileInfoDialog(app_config=config)
    dialog.schedule_format_fetch(); first = dialog.fetch_generation
    dialog.schedule_format_fetch(); second = dialog.fetch_generation
    assert second == first + 1 and dialog.fetch_timer.isActive()
    dialog.on_formats_ready(first, sample_format_info())
    assert dialog.format_info == {}
    dialog.close()


# Phase 2A.5 job model, queue, capabilities, and preferences

def make_job(tmp_path, state=stratrum_download_studio.JobState.QUEUED.value, extension='mp4'):
    final_path = tmp_path / f'final.{extension}'
    if state == stratrum_download_studio.JobState.COMPLETED.value:
        final_path.touch()
    return stratrum_download_studio.DownloadJob(
        job_id='job-' + uuid.uuid4().hex, package_id='package-1', source_url='https://example.com/media?token=secret',
        save_dir=str(tmp_path), requested_format=extension.upper(), requested_resolution=1080,
        final_output_path=str(final_path) if final_path.exists() else '', state=state,
    )


def test_explicit_job_states_include_pipeline_and_terminal_states():
    assert {state.value for state in stratrum_download_studio.JobState} == {
        'queued', 'resolving', 'connecting', 'downloading', 'paused', 'merging', 'converting',
        'verifying', 'completed', 'cancelled', 'retrying', 'failed'
    }


def test_job_model_persists_required_foundation_fields(tmp_path):
    job = make_job(tmp_path)
    payload = job.to_dict()
    for field_name in ('job_id', 'package_id', 'source_url', 'final_output_path', 'temporary_paths', 'requested_format',
                       'requested_resolution', 'actual_format', 'total_bytes', 'downloaded_bytes', 'speed', 'eta',
                       'priority', 'queue_name', 'state', 'retry_count', 'error_summary', 'resumable',
                       'created_at', 'started_at', 'completed_at'):
        assert field_name in payload


@pytest.mark.parametrize('state,capability,expected', [
    ('downloading', 'pause', True), ('paused', 'resume', True), ('completed', 'convert', True),
    ('completed', 'open', True), ('converting', 'delete', False), ('queued', 'edit', True),
])
def test_capability_based_commands(state, capability, expected, tmp_path):
    job = make_job(tmp_path, state)
    assert stratrum_download_studio.job_capabilities(job)[capability] is expected


def test_conversion_enablement_rejects_audio_to_video(tmp_path):
    audio = tmp_path / 'audio.m4a'; audio.touch()
    video = tmp_path / 'video.webm'; video.touch()
    assert stratrum_download_studio.conversion_supported(audio, 'mp4', AUDIO_PROBE)
    assert not stratrum_download_studio.conversion_supported(audio, 'mkv', AUDIO_PROBE)
    assert stratrum_download_studio.conversion_supported(audio, 'mp3', AUDIO_PROBE)
    assert stratrum_download_studio.conversion_supported(audio, 'wav', AUDIO_PROBE)
    assert stratrum_download_studio.conversion_supported(audio, 'm4a', AUDIO_PROBE)
    assert stratrum_download_studio.conversion_supported(video, 'mp4', VIDEO_PROBE)


@pytest.mark.parametrize(('source_ext', 'target_ext'), [('m4a', 'mp3'), ('m4a', 'wav'), ('webm', 'mp4')])
def test_required_conversions_produce_unique_real_output(source_ext, target_ext, tmp_path, monkeypatch):
    source = tmp_path / f'input.{source_ext}'; source.touch()
    mock_conversion_pipeline(monkeypatch, AUDIO_PROBE if source_ext == 'm4a' else VIDEO_PROBE)
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), target_ext))
    assert event[1] is True
    assert Path(event[3]).suffix == f'.{target_ext}'
    assert Path(event[3]).is_file()


def test_conversion_failure_includes_safe_ffmpeg_summary(tmp_path, monkeypatch):
    source = tmp_path / 'input.m4a'; source.touch()
    mock_conversion_pipeline(monkeypatch, AUDIO_PROBE, returncode=1, stderr='ffmpeg failed https://signed.example/file?token=secret')
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert '[URL omitted]' in event[2]
    assert 'token=secret' not in event[2]


def test_conversion_can_be_cancelled_before_ffmpeg_starts(tmp_path, monkeypatch):
    source = tmp_path / 'input.m4a'; source.touch()
    called = []
    monkeypatch.setattr(stratrum_download_studio.subprocess, 'Popen', lambda *args, **kwargs: called.append(args))
    thread = stratrum_download_studio.ConvertThread('id', str(source), 'mp3'); thread.cancel()
    event = run_conversion(thread)
    assert event[1] is False and 'cancelled' in event[2].lower()
    assert called == []


@pytest.mark.parametrize('target', list(stratrum_download_studio.OUTPUT_PROFILES))
def test_table_driven_conversion_command_for_every_target(target, tmp_path):
    source = tmp_path / 'input.mp4'; source.touch()
    plan = stratrum_download_studio.build_conversion_plan(source, target, tmp_path, VIDEO_PROBE)
    profile = stratrum_download_studio.output_profile(target)
    assert plan.destination.suffix == f'.{profile.extension}'
    assert '-progress' in plan.command and 'pipe:1' in plan.command and '-nostats' in plan.command
    assert tuple(profile.ffmpeg_video_args if profile.media_kind == 'video' else profile.ffmpeg_audio_args)
    assert str(plan.temporary_output) == plan.command[-1] and '.partial-' in plan.temporary_output.name


def test_probe_based_video_audio_and_same_format_capabilities():
    video_caps = stratrum_download_studio.conversion_target_capabilities(VIDEO_PROBE)
    audio_caps = stratrum_download_studio.conversion_target_capabilities(AUDIO_PROBE)
    assert all(item['enabled'] for item in video_caps.values())
    assert audio_caps['MP4']['enabled'] and audio_caps['OPUS']['enabled']
    assert not audio_caps['MKV']['enabled'] and 'video stream' in audio_caps['MKV']['reason']
    assert audio_caps['M4A']['enabled'] and 'new file' in audio_caps['M4A']['reason']


def test_audio_only_mp4_plan_uses_audio_stream_and_never_source(tmp_path):
    source = tmp_path / 'source.m4a'; source.touch()
    plan = stratrum_download_studio.build_conversion_plan(source, 'MP4', tmp_path, AUDIO_PROBE)
    assert plan.required_stream == 'audio' and '-vn' in plan.command
    assert plan.destination != source


def test_progress_parser_reports_percent_elapsed_and_eta():
    snapshot = stratrum_download_studio.parse_ffmpeg_progress({'out_time_us': '2500000', 'progress': 'continue'}, 10, 100, 102)
    assert snapshot['percent'] == 25.0 and snapshot['elapsed'] == 2
    assert snapshot['eta'] == 6
    assert stratrum_download_studio.parse_ffmpeg_progress({'progress': 'end'}, 10, 100, 104)['percent'] == 100


def test_verification_failure_removes_incomplete_temporary_output(tmp_path, monkeypatch):
    source = tmp_path / 'input.mp4'; source.touch()
    commands = mock_conversion_pipeline(monkeypatch, VIDEO_PROBE)
    monkeypatch.setattr(stratrum_download_studio, 'validate_final_media', lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('wrong container')))
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert not event[1] and 'wrong container' in event[2]
    assert commands and not Path(commands[0][-1]).exists()


def test_running_conversion_cancellation_terminates_and_cleans_temp(tmp_path, monkeypatch):
    source = tmp_path / 'input.mp4'; source.touch(); holder = {}
    monkeypatch.setattr(stratrum_download_studio, 'probe_media_file', lambda *args, **kwargs: VIDEO_PROBE)

    class CancellingPopen:
        def __init__(self, args, **kwargs):
            self.args = args; self.returncode = None; self.stderr = io.StringIO(''); Path(args[-1]).write_bytes(b'partial')
            self.stdout = self
        def __iter__(self):
            yield 'out_time_us=1000000\n'
            holder['thread'].cancel()
            yield 'progress=continue\n'
        def poll(self): return self.returncode
        def wait(self, timeout=None): return self.returncode if self.returncode is not None else 0
        def terminate(self): self.returncode = -15
        def kill(self): self.returncode = -9

    monkeypatch.setattr(stratrum_download_studio.subprocess, 'Popen', CancellingPopen)
    thread = stratrum_download_studio.ConvertThread('id', str(source), 'mp3'); holder['thread'] = thread
    event = run_conversion(thread)
    assert not event[1] and 'cancelled' in event[2].lower()
    assert not list(tmp_path.glob('*.partial-*.mp3'))


def test_dedicated_converter_job_creation_uses_shared_plans_and_unique_names(tmp_path, monkeypatch):
    first = tmp_path / 'one' / 'clip.mp4'; second = tmp_path / 'two' / 'clip.mp4'; output = tmp_path / 'out'
    first.parent.mkdir(); second.parent.mkdir(); output.mkdir(); first.touch(); second.touch()
    monkeypatch.setattr(stratrum_download_studio, 'probe_media_file', lambda *args, **kwargs: VIDEO_PROBE)
    jobs = stratrum_download_studio.create_converter_jobs([first, second], 'MP3', output)
    assert len(jobs) == 2 and len({job['job_id'] for job in jobs}) == 2
    assert jobs[0]['plan'].destination != jobs[1]['plan'].destination
    assert all(job['plan'].target_name == 'MP3' for job in jobs)


def test_converter_overwrite_behaviors_are_explicit(tmp_path):
    source = tmp_path / 'source.wav'; source.touch(); existing = tmp_path / 'source_converted.mp3'; existing.touch()
    unique = stratrum_download_studio.conversion_destination_for_behavior(source, 'MP3', tmp_path, 'unique')
    assert unique.name == 'source_converted_1.mp3'
    with pytest.raises(FileExistsError, match='Skipped'):
        stratrum_download_studio.conversion_destination_for_behavior(source, 'MP3', tmp_path, 'skip')
    with pytest.raises(PermissionError, match='Confirmation'):
        stratrum_download_studio.conversion_destination_for_behavior(source, 'MP3', tmp_path, 'ask')


def test_local_converter_is_available_from_toolbar_and_tasks_menu(tmp_path):
    source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.init_ui)
    assert 'Convert local media...' in source and 'Converter' in source
    assert stratrum_download_studio.LocalConverterDialog.dragEnterEvent


def test_local_converter_disables_only_incompatible_targets_with_reason(tmp_path, monkeypatch):
    source = tmp_path / 'audio.bin'; source.write_bytes(b'audio')
    monkeypatch.setattr(stratrum_download_studio, 'probe_media_file', lambda *args, **kwargs: AUDIO_PROBE)
    dialog = stratrum_download_studio.LocalConverterDialog(); dialog.add_files([source])
    mkv_index = dialog.target_combo.findText('MKV'); mp4_index = dialog.target_combo.findText('MP4')
    assert not dialog.target_combo.model().item(mkv_index).isEnabled()
    assert 'video stream' in dialog.target_combo.model().item(mkv_index).toolTip()
    assert dialog.target_combo.model().item(mp4_index).isEnabled()
    dialog.close()


def test_recent_folders_are_unique_mru_bounded_and_persisted(tmp_path):
    config_root = tmp_path / 'config-root'; folders = []
    config = stratrum_download_studio.initialize_runtime(config_root, TOKEN, '')
    for index in range(12):
        folder = tmp_path / f'folder-{index}'; folder.mkdir(); folders.append(folder)
        assert config.add_recent_folder(folder)
    config.add_recent_folder(folders[5])
    assert len(config.recent_folders) == 10
    assert config.recent_folders[0] == str(folders[5].resolve())
    assert len(config.recent_folders) == len(set(config.recent_folders))
    assert stratrum_download_studio.initialize_runtime(config_root).recent_folders == config.recent_folders


def test_nonexistent_recent_folders_are_removed_and_clear_works(tmp_path):
    existing = tmp_path / 'existing'; existing.mkdir()
    root = tmp_path / 'root'; config_path = root / 'config' / 'config.json'; config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({'auth_token': TOKEN, 'allowed_origins': [], 'recent_folders': [str(existing), str(tmp_path / 'missing')]}), encoding='utf-8')
    config = stratrum_download_studio.initialize_runtime(root)
    assert config.recent_folders == [str(existing.resolve())]
    config.clear_recent_folders(); assert config.recent_folders == []


def test_download_manager_queue_priority_retry_and_recovery(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path / 'config', TOKEN, '')
    queue_path = tmp_path / 'queue.json'; manager = stratrum_download_studio.DownloadManager(config, queue_path)
    first, second = make_job(tmp_path), make_job(tmp_path)
    manager.add_job(first); manager.add_job(second); manager.move(second.job_id, -1)
    assert manager.queue[0] == second.job_id
    manager.set_state(first.job_id, stratrum_download_studio.JobState.DOWNLOADING)
    assert manager.active_count() == 1
    manager.set_state(first.job_id, stratrum_download_studio.JobState.FAILED, 'network failed')
    assert manager.retry(first.job_id) and first.retry_count == 1
    recovered = stratrum_download_studio.DownloadManager(config, queue_path)
    assert recovered.jobs[first.job_id].state in {'paused', 'queued'}


def test_queue_concurrency_and_stop_after_current(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path / 'config', TOKEN, '')
    config.max_simultaneous_downloads = 1
    manager = stratrum_download_studio.DownloadManager(config, tmp_path / 'queue.json')
    first, second = make_job(tmp_path), make_job(tmp_path); manager.add_job(first); manager.add_job(second)
    manager.set_state(first.job_id, stratrum_download_studio.JobState.DOWNLOADING)
    assert not manager.can_start_more()
    manager.set_state(first.job_id, stratrum_download_studio.JobState.COMPLETED)
    assert manager.can_start_more()
    manager.stop_after_current = True
    assert not manager.can_start_more()


def test_sanitized_source_url_removes_credentials_and_fragment_but_keeps_public_id():
    sanitized = stratrum_download_studio.sanitize_source_url('https://user:pass@example.com/video?id=secret#part')
    assert sanitized == 'https://example.com/video?id=secret'


# Phase 2A.5 popup, menu, launcher, and responsive foundation

def test_popup_pause_and_resume_route_exact_job_id():
    popup = stratrum_download_studio.DownloadProgressPopup('file.mp4', 'https://example.com', job_id='job-123')
    paused, resumed = [], []
    popup.pause_requested.connect(paused.append); popup.resume_requested.connect(resumed.append)
    popup.set_job_state('downloading'); popup.pause_btn.click()
    popup.set_job_state('paused'); popup.pause_btn.click()
    assert paused == ['job-123'] and resumed == ['job-123']
    popup.close()


def test_popup_cancel_routes_partial_choice(monkeypatch):
    popup = stratrum_download_studio.DownloadProgressPopup('file.mp4', 'https://example.com', job_id='job-456')
    emitted = []; popup.cancel_requested.connect(lambda *args: emitted.append(args))

    class FakeMessageBox:
        ButtonRole = stratrum_download_studio.QMessageBox.ButtonRole
        def __init__(self, parent=None): self.buttons = []
        def setWindowTitle(self, value): pass
        def setText(self, value): pass
        def addButton(self, text, role):
            button = object(); self.buttons.append((text, button)); return button
        def exec(self): pass
        def clickedButton(self): return self.buttons[1][1]

    monkeypatch.setattr(stratrum_download_studio, 'QMessageBox', FakeMessageBox)
    popup.request_cancel()
    assert emitted == [('job-456', True)]
    popup.close()


def test_popup_speed_limit_and_completion_actions():
    popup = stratrum_download_studio.DownloadProgressPopup('file.mp4', 'https://example.com', job_id='job-speed')
    limits = []; popup.speed_limit_changed.connect(lambda *args: limits.append(args))
    popup.speed_unit_combo.setCurrentText('MB/s'); popup.speed_value_spin.setValue(2); popup.apply_speed_limit()
    assert limits == [('job-speed', 2 * 1024 * 1024)]
    index = popup.completion_combo.findData('convert_mp3'); popup.completion_combo.setCurrentIndex(index)
    assert popup.completion_action() == 'convert_mp3'
    assert not hasattr(popup, 'conn_table')
    popup.close()


def test_visible_menu_actions_are_functional_or_disabled():
    source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.init_ui)
    for functional in ('Quick Start', 'Supported Sites', 'Open Logs / Diagnostics', 'About {APP_NAME}', 'Reset Column Layout'):
        assert functional in source
    assert 'setEnabled(False)' in source
    assert 'coming soon' not in source.lower()


def test_share_requires_selection_and_offers_copy_and_open():
    source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.share_link)
    assert 'Select a download row' in source
    assert 'Copy Source URL' in source
    assert 'Open Source Page' in source


def test_progress_updates_are_throttled_to_at_most_about_ten_hz():
    source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.update_progress)
    assert '< 0.12' in source


def test_ui_preferences_are_atomic_config_fields(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, '')
    config.window_size = [900, 600]; config.splitter_sizes = [180, 720]; config.column_widths = [300, 50]
    config.hidden_columns = [6]; config.preferred_format = 'MKV'; config.preferred_resolution = 720
    config.max_simultaneous_downloads = 3; config.speed_limit_bps = 1024; config.completion_action = 'open_folder'; config.persist()
    restored = stratrum_download_studio.initialize_runtime(tmp_path)
    assert restored.window_size == [900, 600] and restored.splitter_sizes == [180, 720]
    assert restored.hidden_columns == [6] and restored.preferred_format == 'MKV' and restored.preferred_resolution == 720
    assert restored.max_simultaneous_downloads == 3 and restored.speed_limit_bps == 1024 and restored.completion_action == 'open_folder'


def test_no_console_launcher_calls_testable_main_and_spec_stays_windowed():
    launcher = Path('StratumDownloadStudio.pyw').read_text(encoding='utf-8')
    spec = Path('StratumDownloadStudio.spec').read_text(encoding='utf-8')
    assert 'from stratum_download_studio import main' in launcher
    assert 'SystemExit(main())' in launcher
    assert 'console=False' in spec


def test_diagnostics_and_properties_sanitize_sensitive_urls():
    diagnostics = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.export_diagnostics)
    properties = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.show_properties)
    assert 'sanitize_source_url' in diagnostics and 'sanitize_source_url' in properties
    assert 'auth_token' not in diagnostics and 'cookies' not in diagnostics


# Phase 2A.6B popup lifecycle, browser actions, foreground routing, URLs, and branding

def test_http_rejects_missing_or_unknown_action(runtime):
    missing = json.dumps({'url': 'https://example.com/video'}).encode()
    unknown = json.dumps({'url': 'https://example.com/video', 'action': 'surprise'}).encode()
    assert validate(runtime, body=missing)[0] == 400
    assert validate(runtime, body=unknown)[0] == 400


def test_popup_closes_only_after_verified_completion(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    popup = stratrum_download_studio.DownloadProgressPopup('file.mp4', 'https://example.com', job_id='verified', app_config=config)
    closed = []
    popup.set_job_state('verifying')
    assert popup.schedule_verified_close(lambda: closed.append(True), 10)
    wait_qt(20)
    assert closed == []
    popup.set_job_state('completed')
    popup.schedule_verified_close(lambda: closed.append(True), 10)
    wait_qt(20)
    assert closed == [True]
    popup.close()


def test_keep_open_preference_prevents_auto_close(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.keep_completed_window_open = True
    popup = stratrum_download_studio.DownloadProgressPopup('file.mp4', 'https://example.com', job_id='kept', app_config=config)
    popup.set_job_state('completed')
    assert popup.schedule_verified_close(lambda: None, 1) is False
    popup.close()


@pytest.mark.parametrize('state', ['failed', 'cancelled'])
def test_failure_and_cancellation_invalidate_auto_close(state):
    popup = stratrum_download_studio.DownloadProgressPopup('file.mp4', 'https://example.com', job_id=state)
    closed = []
    popup.set_job_state('completed'); popup.schedule_verified_close(lambda: closed.append(True), 10)
    popup.set_job_state(state); wait_qt(20)
    assert closed == []
    popup.close()


def test_stale_popup_timer_cannot_close_restarted_job():
    popup = stratrum_download_studio.DownloadProgressPopup('file.mp4', 'https://example.com', job_id='restart')
    closed = []
    popup.set_job_state('completed'); popup.schedule_verified_close(lambda: closed.append(True), 10)
    popup.set_job_state('resolving'); popup.set_job_state('completed')
    wait_qt(20)
    assert closed == []
    popup.close()


def test_quick_download_starts_immediately_with_valid_desktop_defaults(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.recent_folders = [str(tmp_path)]
    calls = []
    fake = type('Window', (), {'app_config': config, 'show_normal': lambda self, **kw: calls.append(('show', kw)),
        'start_new_download': lambda self, *args: calls.append(('start', args)),
        'open_add_dialog': lambda self, *args, **kw: calls.append(('options', args, kw)),
        'quick_download_defaults': stratrum_download_studio.StratrumDownloadStudio.quick_download_defaults})()
    assert stratrum_download_studio.StratrumDownloadStudio.handle_browser_request(fake, 'https://example.com/v', 'quick_download')
    assert [item[0] for item in calls] == ['show', 'start']


def test_download_with_options_waits_for_start_and_quick_uses_safe_defaults(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.recent_folders = []
    calls = []
    fake = type('Window', (), {'app_config': config, 'show_normal': lambda self, **kw: calls.append(('show', kw)),
        'start_new_download': lambda self, *args: calls.append(('start', args)),
        'open_add_dialog': lambda self, *args, **kw: calls.append(('options', args, kw)),
        'quick_download_defaults': lambda self: (str(tmp_path), None, 'MP4')})()
    method = stratrum_download_studio.StratrumDownloadStudio.handle_browser_request
    method(fake, 'https://example.com/a', 'download_with_options')
    method(fake, 'https://example.com/b', 'quick_download')
    assert [item[0] for item in calls] == ['options', 'show', 'start']


def test_browser_requests_route_via_qt_signal_and_intentional_foreground_only():
    server_source = inspect.getsource(stratrum_download_studio.ServerThread)
    handler_source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.handle_browser_request)
    assert 'pyqtSignal(str, str)' in server_source and '.connect(self.handle_browser_request)' in inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.init_server)
    assert 'request_foreground=True' in handler_source
    assert 'request_foreground=True' not in inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.start_queued_jobs)


def test_source_url_preserves_youtube_id_and_redacts_sensitive_values():
    url = 'https://www.youtube.com/watch?v=VIDEO_ID&token=secret&signature=signed&list=PUBLIC'
    assert stratrum_download_studio.sanitize_source_url(url) == 'https://www.youtube.com/watch?v=VIDEO_ID&list=PUBLIC'
    assert stratrum_download_studio.sanitize_source_url('https://youtu.be/VIDEO_ID?auth=x') == 'https://youtu.be/VIDEO_ID'


def test_original_and_resolved_media_urls_are_separate():
    job = stratrum_download_studio.DownloadJob('id', 'https://youtube.com/watch?v=abc', '.', 'MP4',
                                               resolved_media_url='https://cdn.example/video?sig=secret')
    assert job.source_url != job.resolved_media_url
    assert 'cdn.example' not in stratrum_download_studio.sanitize_source_url(job.source_url)


def test_phase_2a6b_preferences_persist_and_default_safely(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    assert config.primary_browser_action == 'quick_download' and config.keep_completed_window_open is False
    config.primary_browser_action = 'download_with_options'; config.keep_completed_window_open = True; config.persist()
    restored = stratrum_download_studio.initialize_runtime(tmp_path)
    assert restored.primary_browser_action == 'download_with_options' and restored.keep_completed_window_open is True


def test_visible_active_branding_uses_stratum_and_legacy_security_names_remain():
    active = [Path('browser_extension/manifest.json'), Path('firefox_extension/manifest.json'),
              Path('browser_extension/options.html'), Path('browser_extension/background.js'), Path('browser_extension/content.js')]
    for path in active:
        text = path.read_text(encoding='utf-8')
        assert 'Stratum Download Studio' in text or 'Stratum' in text
        assert 'Stratrum Download Studio' not in text
    assert 'X-Stratrum-Auth' in Path('browser_extension/background.js').read_text(encoding='utf-8')


# Phase 2A.6B.1 desktop-owned browser mode

def test_one_shared_authentication_token_accepts_both_explicit_actions(runtime):
    for action in ('quick_download', 'download_with_options'):
        body = json.dumps({'url': 'https://example.com/video', 'action': action}).encode()
        status, result = validate(runtime, body=body)
        assert status == 200 and result['action'] == action
    background = Path('browser_extension/background.js').read_text(encoding='utf-8')
    assert background.count('"authToken"') == 1
    assert 'X-Stratrum-Auth": token' in background


def test_extension_normal_button_sends_neutral_default_action():
    background = Path('browser_extension/background.js').read_text(encoding='utf-8')
    normal_handler = background.split('runtime.onMessage.addListener', 1)[1]
    assert 'sendToDesktopApp(message.url, "default")' in normal_handler
    assert 'primaryAction' not in background


@pytest.mark.parametrize('desktop_mode, expected', [
    ('quick_download', ['show', 'start']),
    ('download_with_options', ['options']),
])
def test_desktop_resolves_default_action_from_saved_preference(tmp_path, desktop_mode, expected):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.recent_folders = [str(tmp_path)]
    config.primary_browser_action = desktop_mode
    calls = []
    fake = type('Window', (), {'app_config': config, 'show_normal': lambda self, **kw: calls.append(('show', kw)),
        'start_new_download': lambda self, *args: calls.append(('start', args)),
        'open_add_dialog': lambda self, *args, **kw: calls.append(('options', args, kw)),
        'quick_download_defaults': stratrum_download_studio.StratrumDownloadStudio.quick_download_defaults})()
    stratrum_download_studio.StratrumDownloadStudio.handle_browser_request(fake, 'https://example.com/video', 'default')
    assert [call[0] for call in calls] == expected


@pytest.mark.parametrize('action, expected', [
    ('quick', ['show', 'start']),
    ('quick_download', ['show', 'start']),
    ('options', ['options']),
    ('download_with_options', ['options']),
])
def test_explicit_action_compatibility_does_not_change_desktop_default(tmp_path, action, expected):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.recent_folders = [str(tmp_path)]
    config.primary_browser_action = 'download_with_options'
    calls = []
    fake = type('Window', (), {'app_config': config, 'show_normal': lambda self, **kw: calls.append(('show', kw)),
        'start_new_download': lambda self, *args: calls.append(('start', args)),
        'open_add_dialog': lambda self, *args, **kw: calls.append(('options', args, kw)),
        'quick_download_defaults': stratrum_download_studio.StratrumDownloadStudio.quick_download_defaults})()
    stratrum_download_studio.StratrumDownloadStudio.handle_browser_request(fake, 'https://example.com/video', action)
    assert [call[0] for call in calls] == expected
    assert config.primary_browser_action == 'download_with_options'


def test_browser_mode_change_persists_without_changing_token(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    dialog = stratrum_download_studio.BrowserIntegrationDialog(config)
    dialog.default_action_combo.setCurrentIndex(dialog.default_action_combo.findData('download_with_options'))
    restored = stratrum_download_studio.initialize_runtime(tmp_path)
    assert restored.primary_browser_action == 'download_with_options'
    assert restored.auth_token == TOKEN
    dialog.close()


def test_extension_action_dropdown_removed_and_reload_only_reads_saved_token():
    html = Path('browser_extension/options.html').read_text(encoding='utf-8')
    script = Path('browser_extension/options.js').read_text(encoding='utf-8')
    load_handler = script.split('DOMContentLoaded', 1)[1].split('});', 1)[0]
    assert 'primary-action' not in html and 'primaryAction' not in script
    assert html.count('id="token"') == 1
    assert 'storage.local.get(["authToken", "showMediaButtons"])' in load_handler
    assert 'storage.local.set' not in load_handler and 'storage.local.remove' not in load_handler


def test_quick_and_options_flow_remains_start_vs_confirmation_gated():
    handler = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.handle_browser_request)
    dialog = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.open_add_dialog)
    assert 'self.start_new_download' in handler
    assert 'dialog.exec() == QDialog.DialogCode.Accepted' in dialog
    assert 'self.start_new_download' in dialog


# Phase 2A.6B.2 end-to-end default routing regression

def test_combo_selection_persists_quick_immediately_in_memory_and_on_disk(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.primary_browser_action = 'download_with_options'; config.persist()
    dialog = stratrum_download_studio.BrowserIntegrationDialog(config)
    dialog.default_action_combo.setCurrentIndex(dialog.default_action_combo.findData('quick_download'))
    assert config.primary_browser_action == 'quick_download'
    restored = stratrum_download_studio.initialize_runtime(tmp_path)
    assert restored.primary_browser_action == 'quick_download' and restored.auth_token == TOKEN
    dialog.close()


def test_initially_absent_quick_preferences_use_downloads_mp4_and_best(tmp_path):
    downloads = tmp_path / 'Downloads'; downloads.mkdir()
    config = stratrum_download_studio.initialize_runtime(tmp_path / 'config-root', TOKEN, ORIGIN)
    config.recent_folders = []
    config.preferred_format = 'invalid'
    config.preferred_resolution = 999
    fake = type('Window', (), {'app_config': config})()
    defaults = stratrum_download_studio.StratrumDownloadStudio.quick_download_defaults(fake, home_directory=tmp_path)
    assert defaults == (str(downloads.resolve()), None, 'MP4')


def test_default_setting_change_affects_the_next_request_without_restart(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.recent_folders = [str(tmp_path)]
    config.primary_browser_action = 'download_with_options'
    calls = []
    fake = type('Window', (), {'app_config': config, 'show_normal': lambda self, **kw: calls.append('show'),
        'start_new_download': lambda self, *args: calls.append('start'),
        'open_add_dialog': lambda self, *args, **kw: calls.append('options'),
        'quick_download_defaults': stratrum_download_studio.StratrumDownloadStudio.quick_download_defaults})()
    handler = stratrum_download_studio.StratrumDownloadStudio.handle_browser_request
    handler(fake, 'https://example.com/first', 'default')
    config.primary_browser_action = 'quick_download'; config.persist()
    handler(fake, 'https://example.com/second', 'default')
    assert calls == ['options', 'show', 'start']
    assert config.auth_token == TOKEN


def test_quick_reports_clear_error_only_when_no_safe_folder_exists(tmp_path):
    config = stratrum_download_studio.initialize_runtime(tmp_path / 'config-root', TOKEN, ORIGIN)
    config.recent_folders = [str(tmp_path / 'missing')]
    fake = type('Window', (), {'app_config': config})()
    with pytest.raises(ValueError, match='saved folder and your Downloads folder are unavailable'):
        stratrum_download_studio.StratrumDownloadStudio.quick_download_defaults(fake, home_directory=tmp_path)
    handler = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.handle_browser_request)
    assert 'Quick Download Unavailable' in handler and 'open_add_dialog' not in handler.split("if resolved_action == 'quick_download':", 1)[1].split('return True', 1)[0]
