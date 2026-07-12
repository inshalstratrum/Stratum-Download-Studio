import inspect
from pathlib import Path

import pytest

import stratum_dependency_policy as policy


ROOT = Path(__file__).resolve().parent


def test_approved_release_and_official_wheel_hash_are_exactly_pinned():
    lock = (ROOT / 'requirements-yt-dlp.lock').read_text(encoding='utf-8')
    assert policy.APPROVED_YT_DLP_RELEASE == '2026.07.04'
    assert policy.APPROVED_YT_DLP_PACKAGE_VERSION == '2026.7.4'
    assert policy.APPROVED_YT_DLP_WHEEL_SHA256 == 'f11f2b11d5a8ac4059f9bdf29fa4407dc7c6bb00c5097e95ca22a7a9db518266'
    assert 'yt-dlp==2026.7.4' in lock
    assert f'--hash=sha256:{policy.APPROVED_YT_DLP_WHEEL_SHA256}' in lock
    assert '--only-binary=:all:' in lock


def test_bootstrap_isolated_hash_verified_and_official_pypi_only():
    bootstrap = (ROOT / 'scripts' / 'bootstrap_ytdlp.ps1').read_text(encoding='utf-8')
    for required in ('--isolated', '--index-url https://pypi.org/simple', '--require-hashes',
                     '--only-binary=:all:', '--no-deps', '--no-cache-dir'):
        assert required in bootstrap
    for forbidden in ('yt-dlp -U', '--update-to', 'nightly', 'master-builds'):
        assert forbidden not in bootstrap


def test_controlled_install_and_import_are_exact_and_repo_local():
    controlled_root = ROOT / policy.CONTROLLED_DEPENDENCY_DIRECTORY
    distribution = policy.verify_controlled_install(controlled_root)
    module = policy.load_controlled_yt_dlp()
    assert distribution.version == '2026.7.4'
    assert module.version.__version__ == '2026.07.04'
    assert Path(module.__file__).resolve().is_relative_to(controlled_root.resolve())
    ambient = set(policy.UNAPPROVED_YT_DLP_OPTIONAL_MODULES)
    assert not ambient.intersection(module.dependencies.available_dependencies)


def test_distribution_lookup_does_not_accept_ambient_metadata(tmp_path):
    with pytest.raises(policy.DependencyPolicyError, match='found 0'):
        policy.verify_controlled_install(tmp_path)


def test_runtime_disables_ambient_plugins_before_use():
    source = inspect.getsource(policy.load_controlled_yt_dlp)
    assert 'import yt_dlp' in source
    assert 'YTDLP_NO_PLUGINS' in source
    assert '"site-packages" not in entry.lower()' in source
    assert 'sys.path[:] = [str(root)' in source


def test_pyinstaller_collects_only_verified_repo_local_dependency():
    spec = (ROOT / 'StratumDownloadStudio.spec').read_text(encoding='utf-8')
    for required in ("CONTROLLED_DEPENDENCIES = REPOSITORY_ROOT / '.deps'",
                     'verify_controlled_install(CONTROLLED_DEPENDENCIES)',
                     "copy_metadata('yt-dlp')", "hiddenimports=['yt_dlp']"):
        assert required in spec
    assert "pathex=[str(CONTROLLED_DEPENDENCIES)]" in spec
    assert 'excludes=list(UNAPPROVED_YT_DLP_OPTIONAL_MODULES)' in spec
