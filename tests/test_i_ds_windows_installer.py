"""Installer and FFmpeg location regressions; no real installs or browser profiles."""
import importlib.util
import sys
from pathlib import Path

import stratum_download_studio as studio

ROOT=Path(__file__).resolve().parents[1]


def test_media_executable_location_is_absolute_for_ytdlp(tmp_path,monkeypatch):
    ffmpeg=tmp_path/"ffmpeg.exe"
    ffprobe=tmp_path/"ffprobe.exe"
    ffmpeg.write_bytes(b"media-test")
    ffprobe.write_bytes(b"probe-test")
    paths={"ffmpeg":str(ffmpeg),"ffprobe":str(ffprobe)}
    monkeypatch.setattr(studio.shutil,"which",paths.get)
    assert studio.get_ffmpeg_path()==str(ffmpeg)
    assert studio.get_ffprobe_path()==str(ffprobe)
    options=studio.build_download_options("MP3",str(tmp_path/"test.%(ext)s"))
    assert options["ffmpeg_location"]==str(ffmpeg)
    assert options["postprocessors"][0]["preferredcodec"]=="mp3"


def test_frozen_executable_resolves_bundled_media_tools(tmp_path,monkeypatch):
    for n in ("ffmpeg.exe","ffprobe.exe"):
        (tmp_path/n).write_bytes(b"embedded-binary-fixture")
    monkeypatch.setattr(studio.sys,"_MEIPASS",str(tmp_path),raising=False)
    monkeypatch.setattr(studio.shutil,"which",lambda _:None)
    assert Path(studio.get_ffmpeg_path()).samefile(tmp_path/"ffmpeg.exe")
    assert Path(studio.get_ffprobe_path()).samefile(tmp_path/"ffprobe.exe")


def test_staged_installer_hash_verifies_no_data_migration(tmp_path):
    source=ROOT/"scripts"/"ids_installer_gui.py"
    spec=importlib.util.spec_from_file_location("i_ds_installer_tests",source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    first=tmp_path/"first.exe"
    second=tmp_path/"second.exe"
    first.write_bytes(b"fixture-a")
    second.write_bytes(b"fixture-a")
    assert module.matching_binary(first,second)
    second.write_bytes(b"fixture-b")
    assert not module.matching_binary(first,second)
    assert not module.matching_binary(first,tmp_path/"missing")


def test_windows_release_contract_is_non_destructive_and_staged():
    src=(ROOT/"scripts"/"install_ids_windows.ps1").read_text(encoding="utf-8")
    uninstall=(ROOT/"scripts"/"uninstall_ids_windows.ps1").read_text(encoding="utf-8")
    build=(ROOT/"scripts"/"build_windows_installer.ps1").read_text(encoding="utf-8")
    assert "Programs\\I-DS" in src and "I_DS_TEST_INSTALLROOT" in src
    assert "I-DS Download Support.lnk" in src
    assert "synthetic-user" not in src
    assert "Stratrum\\DownloadStudio" not in uninstall
    assert "source" not in uninstall.lower() or "downloads" in uninstall.lower()
    assert "Unsigned staging only" in build
    assert "--add-data" in build and "--distpath" in build
    assert "THIRD_PARTY_NOTICES.txt" in build
    assert "GNU GENERAL PUBLIC LICENSE" in build
    assert "Copy-Item -LiteralPath $FFmpegLicensePath -Destination $licenses" in build
    assert "ffmpeg -L | Out-File" not in build
    assert "KeepIntermediates" in build
    assert "app-build.log" in build and "setup-build.log" in build
    assert "$ErrorActionPreference='Continue'" in build
    assert "THIRD_PARTY_NOTICES.txt" in src
    assert "THIRD_PARTY_NOTICES.txt" in uninstall
    assert (ROOT / "THIRD_PARTY_NOTICES.txt").is_file()
