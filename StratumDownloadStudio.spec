# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


REPOSITORY_ROOT = Path(SPECPATH).resolve()
CONTROLLED_DEPENDENCIES = REPOSITORY_ROOT / '.deps'
CONTROLLED_DENO = REPOSITORY_ROOT / '.tools' / 'deno' / 'deno.exe'
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(CONTROLLED_DEPENDENCIES))

from stratum_dependency_policy import (
    APPROVED_CONTROLLED_MODULES,
    APPROVED_DISTRIBUTIONS,
    FORBIDDEN_AMBIENT_RUNTIME_MODULES,
    INTENTIONALLY_EXCLUDED_MODULES,
    verify_controlled_deno,
    verify_controlled_install,
)

verified = verify_controlled_install(CONTROLLED_DEPENDENCIES)
verify_controlled_deno(REPOSITORY_ROOT, CONTROLLED_DENO)
if set(verified) != set(APPROVED_DISTRIBUTIONS):
    raise RuntimeError('Refusing to package an incomplete dependency manifest')

datas = [(str(REPOSITORY_ROOT / 'controlled-tools.json'), '.')]
for distribution_name in APPROVED_DISTRIBUTIONS:
    metadata = copy_metadata(distribution_name)
    if not metadata or any(
        not Path(source).resolve().is_relative_to(CONTROLLED_DEPENDENCIES)
        for source, _destination in metadata
    ):
        raise RuntimeError(f'Refusing metadata for {distribution_name} outside .deps')
    datas.extend(metadata)

hiddenimports = []
for module_name in APPROVED_CONTROLLED_MODULES:
    hiddenimports.append(module_name)
    hiddenimports.extend(collect_submodules(
        module_name, filter=lambda name: not name.startswith('Cryptodome.SelfTest')))
for data_module in ('certifi', 'curl_cffi', 'yt_dlp_ejs'):
    package_data = collect_data_files(data_module)
    if any(not Path(source).resolve().is_relative_to(CONTROLLED_DEPENDENCIES) for source, _ in package_data):
        raise RuntimeError(f'Refusing package data for {data_module} outside .deps')
    datas.extend(package_data)

a = Analysis(
    ['stratum_download_studio.py'],
    pathex=[str(CONTROLLED_DEPENDENCIES)],
    binaries=[(str(CONTROLLED_DENO), 'tools/deno')],
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=list(INTENTIONALLY_EXCLUDED_MODULES + FORBIDDEN_AMBIENT_RUNTIME_MODULES) + ['Cryptodome.SelfTest'],
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
