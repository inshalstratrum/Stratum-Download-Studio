# Phase 2A.6A Converter Handoff

## Delivered

- Twelve table-driven output profiles now control yt-dlp postprocessing, FFmpeg commands, extensions, codecs, and FFprobe container expectations.
- Download and conversion completion accept only verified final media; intermediate and incomplete files are retained or removed according to verified success and cancellation rules.
- Conversion support is derived from FFprobe streams/container metadata. Video inputs expose five video and seven audio targets; audio inputs expose seven audio targets plus audio-only MP4.
- The shared conversion worker uses `-progress pipe:1 -nostats`, runs outside the UI thread, reports percentage/elapsed/ETA/source/destination/target/state, sanitizes errors, safely cancels FFmpeg, and never overwrites a source.
- A Tasks-menu and toolbar Converter supports multi-select, drag/drop, detected metadata, output folder, unique/ask/skip behavior, per-file progress, cancel, and open-output/open-folder actions.

## Verification

- Focused converter/output tests: 54 passed.
- Generated local fixtures: 20 video/audio conversion paths passed; MP4/MOV/M4A brands verified as `isom`/`qt`/`M4A`.
- Final gate: Python compilation passed; complete pytest passed (`196 passed`); `git diff --check` passed; targeted active-source security search was clean.
- Extension packaging and manifest/reproducibility checks were intentionally not run; extension files are unchanged.

## Manual checks and blockers

- Still required on Windows: GUI multi-select and drag/drop, visible progress/ETA, mid-conversion Cancel, overwrite prompts, open-output/open-folder, downloaded-file conversion, and authorized live yt-dlp outputs.
- Automated blocker: none.
- Phase 2A.6B and later roadmap work remains unimplemented.
