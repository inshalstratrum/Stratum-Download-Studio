# Contributing to I-DS

I-DS is an open-source project maintained under **InShaLIve.os**.

## Report a bug

Create a GitHub Issue with the operating system, Python version, desktop/extension version, the feature used, what you expected, what happened, and steps to reproduce. Attach sanitized console logs only when helpful. Never include login cookies, pairing tokens, private URLs or personal files.

## Suggest a feature

Describe the user problem first, your proposed behavior, and how it could be verified. Current priorities include general file downloads, robust resume/retry, Chrome extension handoff, media compatibility, and accessible desktop UI.

## Submit changes

1. Read [AGENTS.md](AGENTS.md), [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md), and the affected code.
2. Keep changes focused and retain existing download behavior, data formats and local-only pairing.
3. Add regression tests for functional changes and run the relevant Python/JavaScript tests.
4. Open a pull request with a short summary and test evidence. Distinguish manual testing from automated testing.

User safety, site compatibility, and honest release claims take precedence over feature counts. Community members should follow GitHub's standard respectful-collaboration expectations.
