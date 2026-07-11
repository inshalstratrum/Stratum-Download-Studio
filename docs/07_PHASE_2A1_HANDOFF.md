# Phase 2A.1 Handoff: Corrective Security and Test Validation

## Exact Files Changed
- `inshal_dm.py`: Major refactoring of local server, token pairing, and file execution logic.
- `IDM_Extension/manifest.json`: Renamed to "Stratrum Download Studio", removed `<all_urls>` permission, dropped content scripts.
- `IDM_Extension/background.js`: Renamed logs, added 5-second `fetch` timeout, removed whisper listener.
- `IDM_Extension/options.html`: Added password field masking, show/hide toggle, clear button, and security warnings.
- `IDM_Extension/options.js`: Implemented show/hide and clear button logic.
- `test_security.py`: Fully rewritten using `pytest` to start a true ephemeral server and assert HTTP responses and local logic.
- `docs/06_EVIDENCE_APPENDIX.md`: Updated FFmpeg licensing language.
- `IDM_Extension/content.js`: **Deleted** (Functionality dropped to minimize permissions).

## Security Behavior Before and After

| Feature | Before (Phase 2A) | After (Phase 2A.1) |
| --- | --- | --- |
| **HTTP Server** | Blocked execution in UI, allowed generic extension origins, processed payload up to 16KB. | Refactored validation logic. Uses `ThreadingHTTPServer`. Enforces exact allowed origin configuration and `Content-Type: application/json`. Safe rate-limiter applied. Proper HTTP 400/403/413/415/429 responses. Graceful shutdown. |
| **Token Handling** | Generated token in config. Options page used plain text field. | Token validated for 64-hex format; auto-regenerated if corrupted. Atomically saved. Options page uses `type=password` with Show/Hide/Clear options and security notice. |
| **URL Validation** | Basic scheme validation inside monolithic handler. | Helper functions ensure `http/https`, strict hostname requirement, rejection of embedded credentials, and length bounds. |
| **Dangerous Files** | Prompted user with Yes/No to execute `.exe`. | `.exe`, `.msi`, `.bat`, etc. completely reject 'Open' and strictly enforce 'Open Folder'. |
| **Windows Filenames** | No strict sanitization on final paths. | Strict sanitization of reserved names (`CON`, `PRN`), control characters, trailing dots, and max lengths. Duplicates appended with `_1` safely. |
| **FFmpeg Conversions**| Forced `-y` overwrite. | Overwrite flag removed for normal customer conversions. |
| **Extension Perms** | Required `<all_urls>` and injected a DOM hover button on all websites. | Stripped to `contextMenus`, `activeTab`, and `storage`. Only the right-click workflow is retained. Removed `<all_urls>`. |

## Actual Tests Performed
A complete run of `python -m pytest -q test_security.py` exited with **Code 0**, executing 25 tests in 0.97 seconds.

**Tested scenarios include:**
- Successful authenticated request on an ephemeral port.
- Rejection of missing/incorrect tokens, unapproved origins, missing origins, and incorrect content-type.
- Rejection of missing/non-numeric/negative Content-Length, oversized payloads (16KB+), invalid UTF-8, and invalid JSON.
- URL validation: block `file://`, require hostname, block credentials (`admin:password@host`).
- Request rate limit rejection (HTTP 429).
- Unknown endpoint 404 handling.
- Query string redaction / no-logging behavior.
- Atomic history writing and corrupt history backup (`.corrupt`).
- Safe Windows filename resolution (e.g. `CON` -> `CON_file`) and duplicate file renaming.
- Dangerous extension blocking verification (`test.exe`).
- Path containment and traversal block verification.

## Unresolved Issues
1. **FFmpeg Replacement Requirement:** The application currently relies on a GPL-licensed build of FFmpeg/FFprobe containing x264/x265. Commercial distribution of this proprietary application legally requires replacing this with a verified LGPL-compliant FFmpeg build (which excludes GPL components) or having the user supply their own binary.
2. **PyQt6 Licensing / UI Migration:** The application relies on PyQt6 (GPL). Phase 3 must migrate this to PySide6 (LGPL) or a commercial PyQt6 license must be purchased.

## Confirmation
I confirm that **Phase 3 (UI redesign, PySide6 migration, rebranding)** was NOT started. Licensing, obfuscation, and packaging have not been touched.

The codebase is secure, tested, and ready for your review.
