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

import inshal_dm


TOKEN = 'b' * 64
ORIGIN = 'chrome-extension://' + ('a' * 32)
OTHER_ORIGIN = 'chrome-extension://' + ('b' * 32)
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
    return inshal_dm.initialize_runtime(
        app_data_root=tmp_path / 'appdata',
        auth_token=TOKEN,
        allowed_origin=ORIGIN,
        rate_limiter=CountingLimiter(),
    )


@pytest.fixture
def unpaired_runtime(tmp_path):
    return inshal_dm.initialize_runtime(
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
    return inshal_dm.validate_request(headers, io.BytesIO(body), runtime)


@pytest.fixture
def server(runtime):
    httpd = inshal_dm.http.server.ThreadingHTTPServer(('127.0.0.1', 0), inshal_dm.IDMServerHandler)
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


def test_http_unapproved_origin(runtime):
    status, _ = validate(runtime, Origin=OTHER_ORIGIN)
    assert status == 403


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
    assert persisted['allowed_origin'] == ORIGIN


def test_http_correct_token_malformed_request_does_not_pair(unpaired_runtime):
    status, _ = validate(unpaired_runtime, body=b'{bad json')
    assert status == 400
    assert unpaired_runtime.allowed_origin == ''
    assert json.loads(unpaired_runtime.config_path.read_text(encoding='utf-8'))['allowed_origin'] == ''


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
    body = b'x' * (inshal_dm.MAX_REQUEST_BODY + 1)
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
    config = inshal_dm.initialize_runtime(tmp_path, TOKEN, ORIGIN, rate_limiter=limiter)
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
    config = inshal_dm.initialize_runtime(tmp_path, TOKEN, '', rate_limiter=limiter)
    assert validate(config)[0] == 429
    assert config.allowed_origin == ''


# Configuration and import isolation

def test_import_causes_no_filesystem_writes(tmp_path):
    local_app_data = tmp_path / 'localappdata'
    environment = os.environ.copy()
    environment['LOCALAPPDATA'] = str(local_app_data)
    environment['PYTHONPATH'] = str(Path(__file__).parent)
    result = subprocess.run(
        [sys.executable, '-c', 'import inshal_dm'],
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
    config = inshal_dm.initialize_runtime(root)
    persisted = json.loads(config_path.read_text(encoding='utf-8'))
    assert inshal_dm.validate_token(config.auth_token)
    assert persisted['auth_token'] == config.auth_token


def test_atomic_config_writing(tmp_path, monkeypatch):
    replacements = []
    real_replace = inshal_dm.os.replace

    def replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        return real_replace(source, destination)

    monkeypatch.setattr(inshal_dm.os, 'replace', replace)
    config = inshal_dm.initialize_runtime(tmp_path, TOKEN, '')
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
    assert not inshal_dm.validate_token(token)


def test_token_validation_accepts_64_hex_characters():
    assert inshal_dm.validate_token('A1' * 32)


def test_pairing_persistence(tmp_path):
    config = inshal_dm.initialize_runtime(tmp_path, TOKEN, '')
    config.pair_origin(ORIGIN)
    assert inshal_dm.initialize_runtime(tmp_path).allowed_origin == ORIGIN


def test_pairing_reset(tmp_path):
    config = inshal_dm.initialize_runtime(tmp_path, TOKEN, ORIGIN)
    config.reset_pairing()
    assert config.allowed_origin == ''
    assert inshal_dm.initialize_runtime(tmp_path).allowed_origin == ''


def test_no_real_localappdata_path_touched_with_injected_root(tmp_path, monkeypatch):
    real_local_app_data = tmp_path / 'must-not-exist'
    injected = tmp_path / 'isolated'
    monkeypatch.setenv('LOCALAPPDATA', str(real_local_app_data))
    config = inshal_dm.initialize_runtime(injected, TOKEN, '')
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
    inshal_dm.open_download_file(make_record(tmp_path, completed), opener=calls.append)
    assert calls == [str(completed.resolve())]


def test_dangerous_open_never_calls_startfile(tmp_path):
    completed = tmp_path / 'unsafe.exe'
    completed.touch()
    calls = []
    with pytest.raises(PermissionError):
        inshal_dm.open_download_file(make_record(tmp_path, completed), opener=calls.append)
    assert calls == []


def test_missing_file_never_opens(tmp_path):
    calls = []
    with pytest.raises(FileNotFoundError):
        inshal_dm.open_download_file(make_record(tmp_path, tmp_path / 'missing.mp4'), opener=calls.append)
    assert calls == []


def test_out_of_directory_file_never_opens(tmp_path):
    save_dir = tmp_path / 'downloads'
    save_dir.mkdir()
    outside = tmp_path / 'outside.mp4'
    outside.touch()
    calls = []
    with pytest.raises(ValueError):
        inshal_dm.open_download_file(make_record(save_dir, outside), opener=calls.append)
    assert calls == []


def test_valid_open_folder_uses_list_subprocess_arguments(tmp_path):
    completed = tmp_path / 'safe.mp4'
    completed.touch()
    calls = []
    inshal_dm.open_download_folder(make_record(tmp_path, completed), popen=calls.append)
    assert calls == [['explorer', '/select,', str(completed.resolve())]]


def test_dangerous_valid_file_can_open_folder(tmp_path):
    completed = tmp_path / 'unsafe.exe'
    completed.touch()
    calls = []
    inshal_dm.open_download_folder(make_record(tmp_path, completed), popen=calls.append)
    assert calls == [['explorer', '/select,', str(completed.resolve())]]


def test_manipulated_history_path_is_rejected(tmp_path):
    save_dir = tmp_path / 'downloads'
    save_dir.mkdir()
    outside = tmp_path / 'outside.mp4'
    outside.touch()
    manipulated = save_dir / '..' / 'outside.mp4'
    with pytest.raises(ValueError):
        inshal_dm.resolve_recorded_file(make_record(save_dir, manipulated))


# Conversion behavior

def run_conversion(thread):
    events = []
    thread.finished.connect(lambda *args: events.append(args))
    thread.run()
    assert len(events) == 1
    return events[0]


def test_conversion_missing_input(tmp_path):
    event = run_conversion(inshal_dm.ConvertThread('id', str(tmp_path / 'missing.mp4'), 'mp3'))
    assert event[1] is False
    assert event[3] == ''


def test_conversion_unsupported_format(tmp_path):
    source = tmp_path / 'source.mp4'
    source.touch()
    event = run_conversion(inshal_dm.ConvertThread('id', str(source), 'exe'))
    assert event[1] is False
    assert event[3] == ''


def test_conversion_unique_output(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    (tmp_path / 'video_converted.mp3').touch()

    def successful_run(args, **kwargs):
        Path(args[-1]).touch()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(inshal_dm.subprocess, 'run', successful_run)
    event = run_conversion(inshal_dm.ConvertThread('id', str(source), 'mp3'))
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

    monkeypatch.setattr(inshal_dm.subprocess, 'run', successful_run)
    assert run_conversion(inshal_dm.ConvertThread('id', str(source), 'mp3'))[1] is True
    overwrite_flag = '-' + 'y'
    assert overwrite_flag not in commands[0]
    assert '-n' in commands[0]


def test_failed_ffmpeg_does_not_report_success(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    monkeypatch.setattr(
        inshal_dm.subprocess,
        'run',
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
    event = run_conversion(inshal_dm.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert event[3] == ''


def test_successful_conversion_output_path_is_stored(tmp_path):
    source = tmp_path / 'video.mp4'
    output = tmp_path / 'video_converted.mp3'
    source.touch()
    output.touch()
    record = make_record(tmp_path, source)
    original = record['final_path']
    stored = inshal_dm.store_conversion_output(record, output)
    assert record['converted_output_path'] == str(stored)
    assert record['final_path'] == original


def test_conversion_output_must_exist_before_success(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()
    monkeypatch.setattr(
        inshal_dm.subprocess,
        'run',
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0),
    )
    event = run_conversion(inshal_dm.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert event[3] == ''


def test_conversion_timeout_reports_failure(tmp_path, monkeypatch):
    source = tmp_path / 'video.mp4'
    source.touch()

    def timeout(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs['timeout'])

    monkeypatch.setattr(inshal_dm.subprocess, 'run', timeout)
    event = run_conversion(inshal_dm.ConvertThread('id', str(source), 'mp3'))
    assert event[1] is False
    assert 'timed out' in event[2].lower()


def test_conversion_signal_and_slot_signatures_match():
    parameters = list(inspect.signature(inshal_dm.InshalDM.conversion_done).parameters)
    assert parameters == ['self', 'row_id', 'success', 'msg', 'output_path']


def test_active_source_has_no_forbidden_legacy_patterns():
    content = Path('inshal_dm.py').read_text(encoding='utf-8')
    for forbidden in (
        'check_' + 'safe_file',
        'IDM ' + 'Clone',
        'Exact ' + 'IDM',
        'IDM ' + 'replica',
        'Access-Control-Allow-Origin:' + ' *',
        'shell' + '=True',
        'os.' + 'system',
        "'-" + "y'",
    ):
        assert forbidden not in content
