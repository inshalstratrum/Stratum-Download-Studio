# Current State

- Phase: 2A.6B.1 — browser download-mode ownership centralized in desktop Browser Integration settings.
- Branch: `phase-2a6b-quick-download`.
- Commit: `Phase 2A.6B.1: Centralize browser download mode in desktop settings` (this phase commit; use `git rev-parse HEAD` for its immutable hash).
- Entry points: `StratumDownloadStudio.pyw` (Windows development launcher) and `stratum_download_studio.py` (`main()`).
- Test command: `python -m pytest -q`; current expected count: 239 passed.
- Working features: Phase 2A.6B behavior remains intact; desktop Browser Integration is the single source of truth for the ordinary extension-button action; the extension sends neutral `default`, retains one shared token and extension-specific controls, and keeps explicit Quick/Options context-menu overrides compatible.
- Unresolved blockers: no automated blockers. Manual Windows GUI, drag/drop, pause/resume/cancel, close-during-conversion, open-output, and authorized live-download checks remain required.
- Next task: Phase 2A.6C only when explicitly authorized.

## Roadmap — record only

- Phase 2A.6B: Popup completion, foreground activation, source URL and Quick Download.
- Phase 2A.6C: Restore broad browser media detection.
- Phase 2B — General download engine: HTTP/HTTPS files, images, documents, ZIP/RAR, installers and ISOs; resume, redirects, filenames, checksums and browser interception.
- Phase 2B.1 — Queue and performance: priorities, concurrency, per-host limits, real speed limiting, bounded retry and multi-connection segmented downloads.
- Phase 2B.2 — Link collector: collect detected links into a review screen, group into packages, choose files and destination, then move them into the queue.
- Phase 2C — Advanced tools: scheduler, archive extraction, clipboard monitoring, authenticated sites, proxy support and restricted site grabbing.
- Phase 3 — Commercial UI and packaging: PySide6 migration, original modern responsive interface, installer, console-free executable, extension onboarding, licensing and accessibility.
