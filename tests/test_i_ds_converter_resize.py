"""I-DS FFmpeg converter resizing acceptance (synthetic video only)."""
import json
import os
from pathlib import Path
import subprocess

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication

import pytest
import stratum_download_studio as studio


@pytest.fixture
def synthetic_video(tmp_path):
    source = tmp_path / "source_640x480.mp4"
    args = [
        studio.get_ffmpeg_path(), "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=640x480:rate=15",
        "-t", "1", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(source),
    ]
    subprocess.run(args, check=True, timeout=30, capture_output=True)
    return source


def test_video_resize_command_and_no_upscale(synthetic_video, tmp_path):
    probe = studio.probe_media_file(synthetic_video)
    low = studio.build_conversion_plan(synthetic_video, "MP4", tmp_path, probe, resize_height=360)
    assert ("-vf", "scale=-2:360") == tuple(low.command[low.command.index("-vf"):low.command.index("-vf")+2])
    high = studio.build_conversion_plan(synthetic_video, "MP4", tmp_path, probe, resize_height=1080)
    assert "-vf" not in high.command
    original = studio.build_conversion_plan(synthetic_video, "MP4", tmp_path, probe)
    assert "-vf" not in original.command
    with pytest.raises(ValueError, match="Unsupported resize preset"):
        studio.build_conversion_plan(synthetic_video, "MP4", tmp_path, probe, resize_height=333)
    with pytest.raises(ValueError, match="Unsupported resize preset"):
        studio.build_conversion_plan(synthetic_video, "MP4", tmp_path, probe, resize_height=True)


def test_ui_has_video_size_presets_and_accessible_label():
    app = QApplication.instance() or QApplication([])
    dialog = studio.LocalConverterDialog()
    try:
        assert dialog.resize_combo.count() >= 6
        assert dialog.resize_combo.itemData(0) is None
        assert dialog.resize_combo.accessibleName() == "Resize converted video"
        dialog.resize_combo.setCurrentIndex(dialog.resize_combo.findData(360))
        assert dialog.resize_combo.currentData() == 360
    finally:
        dialog.close()


def test_real_ffmpeg_downscale_and_decode(synthetic_video, tmp_path):
    app = QApplication.instance() or QApplication([])
    results = []
    worker = studio.ConvertThread("synthetic", str(synthetic_video), "MP4",
                                  str(tmp_path), resize_height=360)
    worker.finished.connect(lambda *args: results.append(args))
    worker.run()
    assert results and results[-1][1], results
    output = Path(results[-1][3])
    assert output.exists() and output != synthetic_video
    probe = studio.probe_media_file(output)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["height"] == 360
    assert video["width"] == 480
    assert synthetic_video.is_file()
    subprocess.run([
        studio.get_ffmpeg_path(), "-hide_banner", "-loglevel", "error",
        "-i", str(output), "-frames:v", "1", "-f", "null", "-"
    ], check=True, capture_output=True, timeout=25)
