import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parent
EXTENSION = ROOT / "browser_extension"


def test_deterministic_media_candidate_model():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for deterministic extension model tests")
    result = subprocess.run(
        [node, "--test", str(EXTENSION / "media_candidates.test.js")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_event_driven_dom_detection_and_picker_contract():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    for required in (
        'video, audio, a[href]',
        'querySelectorAll("source")',
        "MutationObserver",
        'attributeFilter: ["src", "poster", "href"]',
        '"currentSrc-change"',
        'addEventListener("encrypted"',
        "PerformanceObserver",
        'history[method]',
        '"pushState", "replaceState"',
        'stratum-candidate-picker',
        "candidates.length === 1",
        "showPicker(candidates, button)",
    ):
        assert required in content
    assert "setInterval" not in content
    assert 'element.matches("iframe")' not in content


def test_direct_media_document_and_trusted_frame_contract():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    assert "document.contentType" in content
    assert '"top-level-media-document"' in content
    assert "window.top === window" in content
    assert "topLevelDocument," in content
    assert "candidateApi.applyTrustedOwner({ ...message.candidate, pageUrl }, tabId, frameId)" in background
    assert 'details.type === "main_frame" ? "webRequest-main-frame"' in background
    assert "trustedSenderPage(message.pageUrl, sender)" in background
    assert "reassignFramePage(tabId, frameId, stable)" in background


def test_picker_uses_safe_model_labels_not_raw_signed_urls():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    picker = content.split("function candidateLabel", 1)[1].split("async function handleControlClick", 1)[0]
    assert "candidate.label" in picker
    assert "candidate.safeTarget" in picker
    assert "choice.title = candidate.url" not in picker


def test_one_token_and_desktop_default_action_are_unchanged():
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    assert background.count('"authToken"') == 1
    assert '"X-Stratrum-Auth": token' in background
    assert 'sendToDesktopApp(message.url, "default")' in background


def test_manifest_frame_and_webrequest_detection_contract():
    chromium = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    firefox = json.loads((ROOT / "firefox_extension" / "manifest.json").read_text(encoding="utf-8"))
    for manifest in (chromium, firefox):
        content = manifest["content_scripts"][0]
        assert content["all_frames"] is True
        assert content["js"] == ["media_candidates.js", "content.js"]
        assert "webRequest" in manifest["permissions"]
        assert "http://*/*" in manifest["host_permissions"]
        assert "https://*/*" in manifest["host_permissions"]
    assert firefox["background"]["scripts"] == ["media_candidates.js", "background.js"]


def test_response_observation_is_non_blocking_and_private():
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    listener = background.split("onHeadersReceived.addListener", 1)[1]
    assert '"responseHeaders"' in listener
    assert "onBeforeRequest" not in background
    assert "onBeforeSendHeaders" not in background
    for forbidden in ("requestBody", "requestHeaders", "Cookie", "Authorization", "document.cookie"):
        assert forbidden not in background


def test_tiny_media_and_unsupported_general_files_are_excluded():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    assert "rect.width >= 160" in content
    assert 'element.tagName === "AUDIO" || element.tagName === "A" ? 28 : 80' in content
    assert "ResizeObserver" in content
    assert "pdf" not in content.lower()
    assert "zip" not in content.lower()
    assert "iso" not in content.lower()
