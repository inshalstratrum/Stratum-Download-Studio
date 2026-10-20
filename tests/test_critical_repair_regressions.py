"""Production-caller regression tests for output ownership and cancellation.
No network, GUI or real FFmpeg required; source DownloadThread.run is executed.
"""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import stratum_download_studio as studio


COMPATIBLE = {
    "format_name": "mov,mp4,m4a",
    "streams": [
        {"codec_type": "video", "codec_name": "h264"},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
}
INCOMPATIBLE = {
    "format_name": "mov,mp4,m4a",
    "streams": [
        {"codec_type": "video", "codec_name": "hevc"},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
}


def make_download_thread(tmp_path, job_id):
    return studio.DownloadThread(
        job_id, "https://example.invalid/media",
        str(studio.build_safe_output_template(tmp_path, job_id)),
        "best", "MP4", save_dir=tmp_path
    )


def patch_youtube_dl(monkeypatch, factory):
    class FakeYoutubeDL:
        def __init__(self, options):
            self.params = options

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def extract_info(self, url, download=False):
            assert download
            return factory()

    monkeypatch.setattr(studio.yt_dlp, "YoutubeDL", FakeYoutubeDL)


def test_real_download_thread_never_claims_newer_output_from_another_job(tmp_path, monkeypatch):
    own_id, other_id = "a" * 32, "b" * 32
    own = tmp_path / f"Title [shared-video-id]-{own_id[:8]}.mp4"
    other = tmp_path / f"Title [shared-video-id]-{other_id[:8]}.mp4"

    def downloaded_info():
        own.write_bytes(b"correct-job-media")
        other.write_bytes(b"other-job-media")
        os.utime(own, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
        os.utime(other, ns=(1_700_000_100_000_000_000, 1_700_000_100_000_000_000))
        # Extractor ID is shared, and no output hint was returned by yt-dlp.
        return {"id": "shared-video-id"}

    patch_youtube_dl(monkeypatch, downloaded_info)
    monkeypatch.setattr(
        studio, "validate_final_media",
        lambda path, directory, profile, *args, **kwargs: (Path(path).resolve(), COMPATIBLE),
    )
    thread = make_download_thread(tmp_path, own_id)
    events = []
    thread.finished.connect(lambda *args: events.append(args))
    thread.run()

    assert len(events) == 1
    assert events[0][1] is True
    assert events[0][3] == str(own.resolve()), "Do not select the other download job's newest file"
    assert own.exists() and other.exists(), "Do not delete or overwrite the other job's output"


def test_real_download_thread_with_no_extractor_id_cannot_claim_other_job(tmp_path, monkeypatch):
    own_id = "c" * 32
    foreign = tmp_path / ("SomeoneElse [other]-" + "d" * 8 + ".mp4")

    def downloaded_info():
        foreign.write_bytes(b"not-owned")
        return {}  # No extractor ID or explicit own output.

    patch_youtube_dl(monkeypatch, downloaded_info)
    monkeypatch.setattr(
        studio, "validate_final_media",
        lambda path, directory, profile, *args, **kwargs: (Path(path).resolve(), COMPATIBLE),
    )
    thread = make_download_thread(tmp_path, own_id)
    events = []
    thread.finished.connect(lambda *args: events.append(args))
    thread.run()

    assert len(events) == 1
    assert events[0][1] is False
    assert not thread.final_filename
    assert foreign.exists(), "Never consume or clean up another job's only output"


def test_real_download_thread_cancelled_during_ffmpeg_is_not_completed(tmp_path, monkeypatch):
    job_id = "e" * 32
    source = tmp_path / f"Title [video]-{job_id[:8]}.mp4"
    dest = tmp_path / f"Title [video]-{job_id[:8]}_converted.mp4"
    partial = tmp_path / "private-ffmpeg.partial-abcd1234.mp4"

    def downloaded_info():
        source.write_bytes(b"input-preserve-me")
        return {"id": "video", "filepath": str(source)}

    patch_youtube_dl(monkeypatch, downloaded_info)

    def fake_validate(path, directory, profile, *args, **kwargs):
        path = Path(path)
        assert path.exists(), f"validated file must exist: {path}"
        return path.resolve(), INCOMPATIBLE if path == source else COMPATIBLE

    monkeypatch.setattr(studio, "validate_final_media", fake_validate)
    monkeypatch.setattr(
        studio, "build_conversion_plan",
        lambda *args, **kwargs: studio.ConversionPlan(
            source, dest, partial, "MP4", "video", 10.0, ("fake-ffmpeg", "-i", str(source), str(partial))
        ),
    )
    thread = make_download_thread(tmp_path, job_id)
    finished, statuses = [], []
    thread.finished.connect(lambda *args: finished.append(args))
    thread.status.connect(lambda *args: statuses.append(args[1]))

    # Demonstrate the old blocking subprocess.run path creates a success result
    # even though a concurrent cancel arrives during the mocked FFmpeg operation.
    def blocked_run(*args, **kwargs):
        partial.write_bytes(b"converted")
        thread.cancel()
        return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")

    monkeypatch.setattr(studio.subprocess, "run", blocked_run)

    class SlowProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = None
            self.terminated = False

        def communicate(self, timeout=None):
            assert timeout is not None
            thread.cancel()
            raise subprocess.TimeoutExpired(cmd="fake-ffmpeg", timeout=timeout)

        def terminate(self):
            self.terminated = True
            self.returncode = -15

        def wait(self, timeout=None):
            self.returncode = -15
            return self.returncode

        def kill(self):
            self.returncode = -9

    processes = []

    def fake_popen(*args, **kwargs):
        p = SlowProcess(*args, **kwargs)
        processes.append(p)
        return p

    monkeypatch.setattr(studio.subprocess, "Popen", fake_popen)
    thread.run()

    assert len(finished) == 1, "Cancellation must yield one finished event"
    assert finished[0][1] is False
    assert finished[0][2] == "Cancelled"
    assert "Completed" not in statuses
    assert source.is_file(), "The original source must survive cancelled conversion"
    assert not partial.exists(), "Cancelled FFmpeg temporary output must be cleaned"
    assert not dest.exists(), "Cancelled output must never be promoted to Completed"
    assert processes and processes[0].terminated, "Cancellation must actually terminate FFmpeg"



def test_real_download_thread_rejects_explicit_foreign_hint(tmp_path, monkeypatch):
    job_id = "f" * 32
    own = tmp_path / f"owned-title [shared]-{job_id[:8]}.mp4"
    other = tmp_path / ("foreign-title [shared]-" + "a" * 8 + ".mp4")

    def downloaded_info():
        own.write_bytes(b"ours")
        other.write_bytes(b"theirs")
        return {"id": "shared", "filepath": str(other)}

    patch_youtube_dl(monkeypatch, downloaded_info)
    monkeypatch.setattr(
        studio, "validate_final_media",
        lambda path, directory, profile, *args, **kwargs: (Path(path).resolve(), COMPATIBLE),
    )
    worker = make_download_thread(tmp_path, job_id)
    outcomes = []
    worker.finished.connect(lambda *args: outcomes.append(args))
    worker.run()
    assert len(outcomes) == 1 and outcomes[0][1] is True
    assert outcomes[0][3] == str(own.resolve())
    assert other.is_file()


def test_cancel_after_ffmpeg_promoted_output_preserves_original(tmp_path, monkeypatch):
    source = tmp_path / "original.mp4"
    final = tmp_path / "converted.mp4"
    temp = tmp_path / "converted.partial-deadbeef.mp4"
    source.write_bytes(b"original must survive")
    cancelled = [False]
    monkeypatch.setattr(
        studio, "build_conversion_plan",
        lambda *args, **kwargs: studio.ConversionPlan(
            source, final, temp, "MP4", "video", 10, ("fake-ffmpeg", str(temp))
        ),
    )

    def verify(path, *args, **kwargs):
        p = Path(path)
        assert p.exists()
        if p == final:
            cancelled[0] = True  # Late cancel just after the atomic rename.
        return p, COMPATIBLE

    monkeypatch.setattr(studio, "validate_final_media", verify)

    def run_conversion(*args, **kwargs):
        temp.write_bytes(b"converted output")
        return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")

    with pytest.raises(studio.CancelException):
        studio.convert_incompatible_profile_output(
            source, "MP4", tmp_path, probe=INCOMPATIBLE,
            runner=run_conversion, cancel_check=lambda: cancelled[0],
        )
    assert source.read_bytes() == b"original must survive"
    assert not final.exists()
    assert not temp.exists()
