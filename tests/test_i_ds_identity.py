"""Offline contracts for I-DS branding, compatible launchers, and extension packaging."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "browser_extension"


def test_desktop_name_and_compatibility_launcher():
    source = ast.parse((ROOT / "stratum_download_studio.py").read_text(encoding="utf-8"))
    assignments = {
        target.id: node.value.value
        for node in source.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets
        if isinstance(target, ast.Name) and isinstance(node.value.value, str)
    }
    assert assignments["APP_NAME"] == "I-DS | I.os Download Support"
    assert (ROOT / "START I-DS.cmd").is_file()
    assert "START STRATUM DOWNLOADER.cmd" in (ROOT / "START I-DS.cmd").read_text(encoding="utf-8")
    assert (ROOT / "START STRATUM DOWNLOADER.cmd").is_file()


def test_chrome_firefox_icons_and_legacy_pairing_id():
    manifests = [
        json.loads((ROOT / folder / "manifest.json").read_text(encoding="utf-8"))
        for folder in ("browser_extension", "firefox_extension")
    ]
    for manifest in manifests:
        assert manifest["name"] == "I-DS Download Support"
        assert manifest["manifest_version"] == 3
        assert manifest["version"] == "1.5"
        assert "downloads" in manifest["permissions"]
        assert manifest["action"]["default_title"] == "I-DS Browser Settings"
        for size, relative_path in manifest["icons"].items():
            path = EXTENSION / relative_path
            assert path.is_file(), (size, relative_path)
            assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert manifests[1]["browser_specific_settings"]["gecko"]["id"] == "stratrum-download-studio@stratrum.local"


def test_options_keep_working_controls_and_accessibility():
    html = (EXTENSION / "options.html").read_text(encoding="utf-8")
    for control_id in ("token", "toggle-visibility", "save", "clear", "show-media-buttons", "status"):
        assert f'id="{control_id}"' in html
    for contract in ('role="status"', 'aria-live="polite"', 'for="token"', ':focus-visible', 'prefers-reduced-motion'):
        assert contract in html
    assert "Automatically use I-DS for supported browser files" in html


def test_extension_package_includes_icons_and_brand():
    script = (EXTENSION / "package_extension.ps1").read_text(encoding="utf-8")
    assert "(Join-Path $extensionRoot 'icons')" in script
    for target in ("i-ds-chrome.zip", "i-ds-edge.zip", "i-ds-firefox.zip"):
        assert target in script
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    assert "extensionApi.action.onClicked.addListener" in background
    assert "extensionApi.runtime.openOptionsPage()" in background
    assert (ROOT / "stratum-download-studio-logo.svg").is_file()
    assert (ROOT / "stratum-download-studio.ico").is_file()


def test_dedicated_local_bridge_contract_is_consistent():
    source = (ROOT / "stratum_download_studio.py").read_text(encoding="utf-8")
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    assert "BROWSER_BRIDGE_PORT = 18765" in source
    assert '("127.0.0.1", BROWSER_BRIDGE_PORT)' in source
    assert "self.server_thread.failed.connect(self.browser_bridge_failed)" in source
    assert 'http://127.0.0.1:18765/add_download' in background
    assert 'reply.status === "success"' in background
    for folder in ("browser_extension", "firefox_extension"):
        manifest = json.loads((ROOT / folder / "manifest.json").read_text(encoding="utf-8"))
        assert "http://127.0.0.1:18765/*" in manifest["host_permissions"]
        assert "http://127.0.0.1:8000/*" not in manifest["host_permissions"]
