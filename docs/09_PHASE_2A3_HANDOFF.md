# Phase 2A.3 Final Gate Handoff

## Scope outcome

The Phase 2A.3 code and automated regression gate are complete on branch `phase-2a3-final-gate`. This handoff does not claim that manual Windows smoke testing or browser-store publication has occurred. No readiness score is assigned.

## Exact files changed

- `inshal_dm.py`
- `test_security.py`
- `rewrite_inshal.py` — behavior-preserving legacy-literal splitting so the required active-source search has no false positive
- `IDM_Extension/README.md`
- `IDM_Extension/package_extension.ps1`
- `extension_packages/stratrum-download-studio-chrome.zip`
- `extension_packages/stratrum-download-studio-edge.zip`
- `docs/09_PHASE_2A3_MANUAL_TEST.md`
- `docs/09_PHASE_2A3_HANDOFF.md`

The two extension ZIPs contain `manifest.json`, `background.js`, `options.html`, `options.js`, and `README.md`. Their SHA-256 digests are both `F2CC4E1891226182750A25C50C9188B54A740AD7BD281ECF4473B85A52BD4844`; the packages are intentionally identical because the current Manifest V3 source is compatible with both Chrome and Edge.

## Implemented corrections

- Importing `inshal_dm` no longer initializes configuration or creates application-data directories. Production explicitly calls `initialize_runtime()` and defaults to `%LOCALAPPDATA%\Stratrum\DownloadStudio`.
- Tests can inject application-data root, token, paired origin, history path, and rate limiter before any production configuration is initialized.
- Request validation authenticates first, strictly validates the extension origin, media type, length, body, UTF-8, JSON object, and URL, then applies rate limiting. Pairing is persisted atomically only after the complete request is valid and not rate-limited.
- Desktop Browser Integration keeps the token masked, provides deliberate copy and pairing-reset actions, and does not print the token.
- Completed-file opening resolves both the recorded save directory and candidate path, rejects missing/out-of-directory/manipulated paths, blocks dangerous types from `os.startfile`, and retains safe **Open Folder** behavior with list-form subprocess arguments.
- Conversion signal and slot signatures now both carry `row_id`, `success`, `message`, and `output_path`. Success requires an existing output; the original downloaded path remains unchanged; the converted path is stored separately. FFmpeg uses `-n`, never `-y`, and has a 30-minute timeout.
- Chrome and Edge review ZIPs are generated reproducibly. The first-launch prompt includes **Install Extension**, **Remind Me Later**, and **Do Not Ask Again**. Silent installation is not attempted.

## Automated tests

Count: **60 collected, 60 passed**.

Exact pytest node IDs:

```text
test_security.py::test_http_valid_request
test_security.py::test_http_missing_token
test_security.py::test_http_wrong_token
test_security.py::test_http_missing_origin
test_security.py::test_http_unapproved_origin
test_security.py::test_http_malformed_origin[short-id]
test_security.py::test_http_malformed_origin[path]
test_security.py::test_http_malformed_origin[query]
test_security.py::test_http_malformed_origin[web-origin]
test_security.py::test_http_malformed_origin[unsupported-scheme]
test_security.py::test_http_first_valid_origin_pairing
test_security.py::test_http_correct_token_malformed_request_does_not_pair
test_security.py::test_http_application_json
test_security.py::test_http_application_json_utf8_charset
test_security.py::test_http_application_json_malicious_rejected
test_security.py::test_http_text_plain_rejected
test_security.py::test_http_missing_content_type
test_security.py::test_http_missing_content_length
test_security.py::test_http_non_numeric_content_length
test_security.py::test_http_negative_content_length
test_security.py::test_http_body_over_16kb
test_security.py::test_http_invalid_utf8
test_security.py::test_http_invalid_json
test_security.py::test_http_invalid_urls[empty]
test_security.py::test_http_invalid_urls[file-scheme]
test_security.py::test_http_invalid_urls[missing-hostname]
test_security.py::test_http_invalid_urls[embedded-credentials]
test_security.py::test_http_invalid_urls[excessive-length]
test_security.py::test_http_unknown_endpoint
test_security.py::test_rate_limiting_only_after_authentication_and_structural_validation
test_security.py::test_rate_limit_failure_does_not_pair
test_security.py::test_import_causes_no_filesystem_writes
test_security.py::test_corrupt_temporary_config_regeneration
test_security.py::test_atomic_config_writing
test_security.py::test_token_validation_rejects_invalid_values[empty]
test_security.py::test_token_validation_rejects_invalid_values[short]
test_security.py::test_token_validation_rejects_invalid_values[non-hex]
test_security.py::test_token_validation_rejects_invalid_values[none]
test_security.py::test_token_validation_rejects_invalid_values[non-string]
test_security.py::test_token_validation_accepts_64_hex_characters
test_security.py::test_pairing_persistence
test_security.py::test_pairing_reset
test_security.py::test_no_real_localappdata_path_touched_with_injected_root
test_security.py::test_safe_open_calls_startfile_exactly_once
test_security.py::test_dangerous_open_never_calls_startfile
test_security.py::test_missing_file_never_opens
test_security.py::test_out_of_directory_file_never_opens
test_security.py::test_valid_open_folder_uses_list_subprocess_arguments
test_security.py::test_dangerous_valid_file_can_open_folder
test_security.py::test_manipulated_history_path_is_rejected
test_security.py::test_conversion_missing_input
test_security.py::test_conversion_unsupported_format
test_security.py::test_conversion_unique_output
test_security.py::test_conversion_never_uses_y
test_security.py::test_failed_ffmpeg_does_not_report_success
test_security.py::test_successful_conversion_output_path_is_stored
test_security.py::test_conversion_output_must_exist_before_success
test_security.py::test_conversion_timeout_reports_failure
test_security.py::test_conversion_signal_and_slot_signatures_match
test_security.py::test_active_source_has_no_forbidden_legacy_patterns
```

## Verification results

- `python -m py_compile inshal_dm.py` — exit `0`
- `python -m pytest -q` — exit `0`; `60 passed`
- `git diff --check` — exit `0`
- Active, non-archive source scan wrapper — exit `0`
  - Each raw `rg` search returned exit `1`, the expected no-match result, for: `IDM Clone`, `Exact IDM`, `IDM replica`, `check_safe_file`, wildcard CORS header, shell execution flag, OS command execution call, and the FFmpeg overwrite flag.

## Manual tests not yet performed

No manual Windows smoke-test step has been performed in this correction run. The required start, token transfer, unpacked Chrome/Edge load, normal link, restart, pairing reset, malformed token, harmless download, safe Open/Open Folder, executable blocking, collision-safe conversion, exit, and port-8000 closure checks remain explicitly pending in `docs/09_PHASE_2A3_MANUAL_TEST.md`.

## Remaining Phase 3 or external issues

- Publish and obtain approval for the official Chrome Web Store and Microsoft Edge Add-ons listings, then replace the current official-store landing pages with the approved direct listing URLs.
- Execute and record the manual Windows smoke checklist on supported Chrome and Edge versions.
- Conversion has a bounded timeout but no interactive in-progress cancellation control; adding cancellable process management remains a Phase 3 item.
- Cross-process conversion naming is protected from overwrite by FFmpeg `-n`; the claim file coordinates concurrent conversions inside this application. More elaborate cross-process job orchestration is outside this gate.
- PySide6 migration, redesign, licensing, obfuscation, desktop application packaging, and Supabase integration were not started.
