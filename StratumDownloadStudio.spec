# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import copy_metadata


REPOSITORY_ROOT = Path(SPECPATH).resolve()
CONTROLLED_DEPENDENCIES = REPOSITORY_ROOT / '.deps'
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(CONTROLLED_DEPENDENCIES))

from stratum_dependency_policy import (
    APPROVED_YT_DLP_PACKAGE_VERSION,
    UNAPPROVED_YT_DLP_OPTIONAL_MODULES,
    verify_controlled_install,
)

distribution = verify_controlled_install(CONTROLLED_DEPENDENCIES)
if distribution.version != APPROVED_YT_DLP_PACKAGE_VERSION:
    raise RuntimeError('Refusing to package an unapproved yt-dlp version')
yt_dlp_metadata = copy_metadata('yt-dlp')
if not yt_dlp_metadata or any(
    not Path(source).resolve().is_relative_to(CONTROLLED_DEPENDENCIES)
    for source, _destination in yt_dlp_metadata
):
    raise RuntimeError('Refusing to package yt-dlp metadata outside .deps')

a = Analysis(
    ['stratum_download_studio.py'],
    pathex=[str(CONTROLLED_DEPENDENCIES)],
    binaries=[],
    datas=yt_dlp_metadata,
    hiddenimports=['yt_dlp'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=list(UNAPPROVED_YT_DLP_OPTIONAL_MODULES),
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StratumDownloadStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
