import io
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

import stratrum_download_studio


TOKEN = 'b' * 64
ORIGIN = 'chrome-extension://' + ('a' * 32)
OTHER_ORIGIN = 'chrome-extension://' + ('b' * 32)
FIREFOX_ORIGIN = 'moz-extension://12345678-1234-1234-1234-123456789abc'
VALID_BODY = json.dumps({'url': 'https://example.com/video.mp4'}).encode('utf-8')


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

        def emit(self, url):
            self.urls.append(url)

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
    assert server.url_signal.urls == ['https://example.com/video.mp4']


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
    assert (status, result) == (200, 'https://example.com/video.mp4')
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
        [sys.executable, '-c', 'import stratrum_download_studio'],
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

    def successful_run(args, **kwargs):
        Path(args[-1]).touch()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(stratrum_download_studio.subprocess, 'run', successful_run)
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is True
    assert event[3].endswith('video_converted_1.mp3')


def test_conversion_never_uses_y(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    commands = []

    def successful_run(args, **kwargs):
        commands.append(args)
        Path(args[-1]).touch()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(stratrum_download_studio.subprocess, 'run', successful_run)
    assert run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))[1] is True
    assert '-y' not in commands[0]
    assert '-n' in commands[0]


def test_failed_ffmpeg_does_not_report_success(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    monkeypatch.setattr(
        stratrum_download_studio.subprocess,
        'run',
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
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
    monkeypatch.setattr(
        stratrum_download_studio.subprocess,
        'run',
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0),
    )
    event = run_conversion(stratrum_download_studio.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert event[3] == ''


def test_conversion_timeout_reports_failure(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()

    def timeout(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs['timeout'])

    monkeypatch.setattr(stratrum_download_studio.subprocess, 'run', timeout)
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
        [sys.executable, '-c', 'from stratrum_download_studio import StratrumDownloadStudio, DownloadServerHandler'],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not local_app_data.exists()


def test_normal_startup_has_no_automatic_extension_prompt():
    source = Path('stratrum_download_studio.py').read_text(encoding='utf-8')
    assert 'show_extension_install_prompt' not in source
    assert 'Install Extension' not in source


def test_browser_integration_remains_manual_in_options():
    source = inspect.getsource(stratrum_download_studio.StratrumDownloadStudio.show_dummy_msg)
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
    assert Path('stratrum_download_studio.py').is_file()
    assert Path('StratrumDownloadStudio.spec').is_file()


def test_cleanup_paths_do_not_exist():
    for removed_path in handoff_block('deleted-paths'):
        assert not Path(removed_path).exists(), removed_path


def test_final_spec_uses_final_entrypoint_and_executable_name():
    spec = Path('StratrumDownloadStudio.spec').read_text(encoding='utf-8')
    assert "['stratrum_download_studio.py']" in spec
    assert "name='StratrumDownloadStudio'" in spec


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


def test_finished_progress_hook_emits_100_percent(tmp_path):
    source = tmp_path / 'complete.mp4'
    source.touch()
    thread = stratrum_download_studio.DownloadThread('id', 'https://example.com', str(tmp_path / '%(title)s.%(ext)s'), 'best', 'mp4')
    events = []
    thread.progress.connect(lambda *args: events.append(args))
    thread.progress_hook({
        'status': 'finished', 'filename': str(source), 'downloaded_bytes': 100, 'total_bytes': 100,
    })
    assert events[0][2] == 100.0
    assert events[0][7] == 'Completed'


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
