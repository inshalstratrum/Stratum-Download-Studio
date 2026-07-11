# Repository rules

- Preserve working features and security controls.
- Do not start later phases unless explicitly requested.
- Use one agent only.
- Inspect current source, not archived versions or every historical handoff.
- Run targeted tests during implementation and the full suite once at final gate.
- Do not rerun packaging unless packaging/extension files changed.
- Never rename a media extension without real remux/transcode.
- Never claim manual tests were performed unless actually performed.
- Update docs/CURRENT_STATE.md after each committed phase.
- Keep final responses to at most 15 lines.