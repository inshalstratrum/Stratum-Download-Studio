import inspect
import json
from pathlib import Path

import pytest

import stratum_dependency_policy as policy


ROOT = Path(__file__).resolve().parent


def test_complete_lock_matches_authoritative_manifest():
    assert policy.APPROVED_YT_DLP_RELEASE == '2026.07.04'
    assert policy.APPROVED_YT_DLP_PACKAGE_VERSION == '2026.7.4'
    assert len(policy.APPROVED_DISTRIBUTIONS) == 18
    policy.verify_lock_file(ROOT / 'requirements-yt-dlp.lock')


def test_bootstrap_isolated_hash_verified_atomic_and_official_only():
    source = (ROOT / 'scripts' / 'bootstrap_ytdlp.ps1').read_text(encoding='utf-8')
    for required in ('--isolated', '--index-url https://pypi.org/simple', '--require-hashes',
                     '--only-binary=:all:', '--no-deps', '--no-cache-dir',
                     '--disable-pip-version-check', '.deps-staging', '.tools-staging',
                     'archive_sha256', 'Move-Item', 'DependencyRollback'):
        assert required in source
    for forbidden in ('yt-dlp -U', '--update-to', 'nightly', 'master-builds', 'pip install --upgrade'):
        assert forbidden not in source


def test_controlled_install_import_and_inventory_are_exact_and_repo_local():
    controlled_root = ROOT / policy.CONTROLLED_DEPENDENCY_DIRECTORY
    distributions = policy.verify_controlled_install(controlled_root)
    module = policy.load_controlled_yt_dlp()
    assert set(distributions) == set(policy.APPROVED_DISTRIBUTIONS)
    assert module.version.__version__ == '2026.07.04'
    assert Path(module.__file__).resolve().is_relative_to(controlled_root.resolve())
    expected = {'brotli', 'certifi', 'mutagen', 'websockets', 'urllib3', 'requests',
                'curl_cffi', 'Cryptodome', 'yt_dlp_ejs'}
    assert expected <= set(module.dependencies.available_dependencies)
    assert not {'Crypto', 'brotlicffi', 'secretstorage', 'xattr'} & set(module.dependencies.available_dependencies)


def test_distribution_lookup_rejects_ambient_or_incomplete_metadata(tmp_path):
    with pytest.raises(policy.DependencyPolicyError, match='Expected one controlled brotli'):
        policy.verify_controlled_install(tmp_path)


def test_frozen_layout_can_coexist_with_unrelated_application_metadata():
    controlled_root = ROOT / policy.CONTROLLED_DEPENDENCY_DIRECTORY
    assert policy.verify_controlled_install(controlled_root, allow_unrelated=True)


def test_runtime_disables_plugins_and_filters_ambient_site_packages():
    source = inspect.getsource(policy.load_controlled_yt_dlp)
    assert 'YTDLP_NO_PLUGINS' in source
    assert 'site-packages' in source
    assert 'Refusing ambient module' in source


def test_deno_manifest_path_version_and_hash_are_verified():
    manifest = json.loads((ROOT / 'controlled-tools.json').read_text(encoding='utf-8'))['deno']
    assert manifest['version'] == '2.8.3'
    assert manifest['official_release_url'].startswith('https://github.com/denoland/deno/releases/download/v2.8.3/')
    deno = policy.verify_controlled_deno(ROOT)
    assert deno == (ROOT / '.tools' / 'deno' / 'deno.exe').resolve()


def test_python_api_selects_only_controlled_deno_and_local_ejs():
    module = policy.load_controlled_yt_dlp()
    options = policy.controlled_yt_dlp_options()
    assert options == {'js_runtimes': {'deno': {'path': str(policy.controlled_deno_path())}},
                       'remote_components': []}
    with module.YoutubeDL({**options, 'quiet': True}) as ydl:
        info = ydl._js_runtimes['deno'].info
        assert info.version == '2.8.3' and info.supported
        assert Path(info.path).resolve() == policy.controlled_deno_path().resolve()
        assert ydl.params['remote_components'] == set()


def test_pyinstaller_collects_verified_capabilities_and_portable_deno():
    spec = (ROOT / 'StratumDownloadStudio.spec').read_text(encoding='utf-8')
    for required in ('verify_controlled_install(CONTROLLED_DEPENDENCIES)',
                     'verify_controlled_deno(REPOSITORY_ROOT, CONTROLLED_DENO)',
                     "collect_data_files(data_module)", "'tools/deno'",
                     'APPROVED_CONTROLLED_MODULES', 'INTENTIONALLY_EXCLUDED_MODULES'):
        assert required in spec
    assert "pathex=[str(CONTROLLED_DEPENDENCIES)]" in spec
