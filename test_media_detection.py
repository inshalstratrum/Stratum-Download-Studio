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
        'video, audio',
        'querySelectorAll("source")',
        "MutationObserver",
        'attributeFilter: ["src", "poster", "class", "style", "open", "aria-hidden"]',
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
    assert "candidateApi.applyTrustedOwner({ ...message.candidate, pageUrl }, tabId, frameId, playerId, documentGeneration)" in background
    assert 'details.type === "main_frame" ? "webRequest-main-frame"' in background
    assert "trustedSenderPage(message.pageUrl, sender)" in background
    assert "reassignFramePage(tabId, frameId, stable)" in background


def test_picker_uses_safe_model_labels_not_raw_signed_urls():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    picker = content.split("function candidateLabel", 1)[1].split("async function handleControlClick", 1)[0]
    assert "candidate.label" in picker
    assert "choice.textContent = candidateLabel(candidate)" in picker
    assert "choice.title = candidateLabel(candidate)" in picker
    assert "candidate.safeTarget" not in picker
    assert "choice.title = candidate.url" not in picker


def test_customer_labels_never_use_source_number_disambiguation():
    model = (EXTENSION / "media_candidates.js").read_text(encoding="utf-8")
    assert "deduplicateLabels(candidates)" in model
    assert "Source ${" not in model


def test_one_token_and_desktop_default_action_are_unchanged():
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    assert background.count('"authToken"') == 1
    assert '"X-Stratrum-Auth": token' in background
    assert 'sendToDesktopApp(selected.url, "default", trustedHandoff(selected, pageUrl))' in background


def test_complete_source_policy_and_fragment_evidence_contract():
    model = (EXTENSION / "media_candidates.js").read_text(encoding="utf-8")
    for required in (
        "explicitDomSource",
        "verifiedMainFrameMedia",
        "verifiedDocumentMedia",
        "completeAttachment",
        "ADAPTIVE_REPRESENTATION_PATH",
        "contentRange",
        "statusCode",
        "isNetworkFragment",
    ):
        assert required in model
    assert "raw.allowPage" not in model
    assert 'sourcePage && isExtractorPage(sourcePage)' in model
    assert 'raw.articleFallback && raw.visiblePlayer && sourcePage' in model


def test_overlay_targets_are_frame_local_and_proxy_iframes_are_capability_gated():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    model = (EXTENSION / "media_candidates.js").read_text(encoding="utf-8")
    assert "isOverlayTargetDescriptor" in content
    assert 'tagName === "VIDEO" || tagName === "AUDIO"' in model
    assert 'tagName === "IFRAME" && descriptor && descriptor.frameProxy === true' in model
    assert 'querySelectorAll("video, audio")' in content
    assert 'querySelectorAll("video, audio, iframe' not in content
    assert 'event.data.type !== "stratrum-frame-capability"' in content
    assert 'event.data.hasNativeMedia === true || event.data.hasCustomPlayer !== true' in content
    assert 'frame.contentWindow === source' in content


def test_overlay_layering_shadow_roots_and_delayed_detection_contract():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    model = (EXTENSION / "media_candidates.js").read_text(encoding="utf-8")
    assert 'position: "fixed"' in content
    assert 'visibleModal()' in content
    assert 'composedContains(activeModal, element)' in content
    assert 'shouldShowPlayerOverlay' in model
    assert 'element.shadowRoot' in content and 'observeRoot(root)' in content
    assert '"Detecting video…"' in content
    assert 'DETECTION_WAIT_MS = 1600' in content
    assert 'Date.now() < deadline' in content


def test_background_routes_only_stored_complete_candidates():
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    handler = background.split('message.type === "stratrum-download-request"', 1)[1].split("return true", 1)[0]
    assert "candidateStore.list({ tabId, frameId, documentGeneration: message.documentGeneration, pageUrl, playerId: message.playerId }).find" in handler
    assert "ownsPlayer(tabId, frameId, message.documentGeneration, message.playerId, pageUrl)" in handler
    assert "candidate.id === message.candidateId" in handler
    assert 'code: "invalid_candidate"' in handler
    assert '"No complete downloadable media detected."' in handler
    for required in ("content-range", "statusCode: details.statusCode", "requestType: details.type"):
        assert required in background
    assert 'message.type === "stratrum-frame-blocked"' in background
    assert 'type: "stratrum-frame-blocked"' in content
    assert "DRM or access-controlled media is not supported." in content


def test_player_registry_provenance_and_lease_contracts_replace_sole_player_gate():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    background = (EXTENSION / "background.js").read_text(encoding="utf-8")
    model = (EXTENSION / "media_candidates.js").read_text(encoding="utf-8")
    for required in ("PlayerRegistry", "documentGeneration", "leaseUntil", "lastActivity", "correlate(raw)", "QuarantineStore"):
        assert required in model
    for required in ("nearestPermalink", "canonicalUrl", "ogUrl", "jsonLdUrl", 'type: "stratrum-player-state"'):
        assert required in content
    assert "soleConnectedPlayerId" not in content
    assert "players.length !== 1" not in background
    assert "quarantineStore.observe" in background
    assert "promoteQuarantinedEvidence" in background
    assert "takeMatching" in model and "evidenceMatches" in model


def test_direct_audio_and_spa_reuse_rotate_player_ownership_without_replacing_button():
    content = (EXTENSION / "content.js").read_text(encoding="utf-8")
    assert 'contentType.startsWith("audio/") ? "audio" : "video"' in content
    assert 'reportPlayerState(element, "direct-media-document", false)' in content
    assert 'function refreshPlayerOwnership(element)' in content
    refresh = content.split('function refreshPlayerOwnership(element)', 1)[1].split('function elementCandidates', 1)[0]
    assert 'retirePlayer(element)' in refresh and 'playerIdFor(element)' in refresh
    assert 'button.remove()' not in refresh


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
    assert firefox["background"]["scripts"] == ["media_candidates.js", "file_interception.js", "background.js"]


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
    model = (EXTENSION / "media_candidates.js").read_text(encoding="utf-8")
    assert "rect.width >= 160" in content
    assert 'element.tagName === "AUDIO" ? 28 : 80' in content
    assert "ResizeObserver" in content
    direct_extensions = next(line for line in model.splitlines() if "const DIRECT_EXTENSIONS" in line).lower()
    for forbidden in ("pdf", "zip", "iso"):
        assert forbidden not in direct_extensions
