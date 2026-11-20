---
type: Project UI design contract
title: I-DS desktop and browser interface
updated_at: "2026-11-21T03:35:37+05:00"
revisions:
  - at: "2026-11-21T03:35:37+05:00"
    by: "chatgpt/gpt-6"
    change: "Verified native private installer browser-setup screen and new standard file dialog; captured six owner-requested interactions and acceptance limits."
  - at: "2026-11-19T23:15:08+05:00"
    by: "chatgpt/gpt-6"
    change: "Verified private Windows installer screen at 200% DPI and removed clipped setup wording."
  - at: "2026-11-18T21:27:05+05:00"
    by: "chatgpt/gpt-6"
    change: "Added responsive converter resize controls and real native Windows verification."
  - at: 2026-11-17T10:25:00+05:00
    change: Initial tested I-DS PyQt6 and extension visual refinement
---

# I-DS interface — design and acceptance

**Product:** I-DS — I.os Download Support, Tool by InShaLIve.os. A Windows file/media downloader and companion browser extension. Source of truth for actual rendering: `ids_ui_components.py`, `stratum_download_studio.py`, and `browser_extension/options.html`.

**Authority:** [AGENTS.md](../AGENTS.md), [current state](CURRENT_STATE.md), and the owner's global [08 Interactive Interface UX Minimum Standards](https://drive.google.com/file/d/1bup0f-rSL2Dm7gxH-HWlfoTjIscsUXcY/view). This is a *project-specific* application, not a competing universal master.

## Intent and visual direction

- Users should identify **Add media**, **Download file**, or **Convert** immediately, see queued/active/completed state, and find categories without reading technical setup prose.
- Preserve native **PyQt6**, current downloader jobs, auth, history, converters, service binding, and browser contracts. Do not migrate to React/shadcn simply to use a web UI library.
- Design direction: purposeful **navy + teal**, independent white task surface, consistent vector icons, clean segmented actions, soft offset shadows. Current local QtSvg renderer replaces inconsistent native icon mixes.
- Tokens in `ids_ui_components.COLORS`: navy `#112742`, deep `#0d1f37`, teal `#087e86`, light teal `#d8f4ee`, text `#16314b`, muted `#526a80`; user-facing statuses continue to include labels in addition to color.
- Logo: native Qt-rendered vector `ids_ui_components.BRAND_SVG`, exported to existing Windows ICO and browser PNG sizes (16/32/48/128) by `scripts/build_ids_brand_assets.py`. This does not change extension IDs or security headers.

## Interaction requirements and checks

| Requirement | Behavior | Automated/rendered evidence |
|---|---|---|
| Primary tasks | Toolbar and useful empty state provide media/file/converter actions | `tests/test_i_ds_ui.py`; native Windows render |
| Sidebar | Categories selected, two width presets, collapse and reopen; divider remains draggable | Native rendered script and pytest |
| Text size | 100%, 115%, 130%; saved for subsequent launches | Native test at 760×480 with 130% |
| State | Active, Waiting, Finished computed from real job records; empty/data views switch | Native pytest |
| Layout | On narrow windows toolbar becomes icon-only, tooltips preserved; header keeps navigation and text-scale controls visible | Native render 1170×740, 800×545 and 760×480 |
| Browser | Same I-DS mark, shorter descriptions, toggles, keyboard-opened help, original pairing behavior | Playwright Chrome on desktop/mobile/minimal 260px and simulated 200% zoom |
| Focus | Qt buttons/combo remain keyboard focusable; browser focus rings and help summary support Enter | Native and Playwright tests |
| Scroll/overflow | Download table may scroll horizontally at narrow widths; settings page must not overflow | Render and browser scroll-width checks |
| Media converter | Select Original size or up-to-height presets; keep aspect ratio; don't upscale; disable invalid conversions | 320-test full suite; real FFmpeg re-encode/FFprobe/decode |
| Narrow converter | Break options and actions into short rows; keep action buttons reachable at 760×480 with 130% text | Actual native Windows rendered screenshot |
| Windows installer at 200% DPI | Short notice, readable text, 44px+ tall buttons, no text clipping at 480×340 logical / 960×680 physical | Actual native Windows Qt rendered and inspected 2026-11-19, PASS; end-user acceptance pending |
| Installer completion | Guided browser setup steps, stable extension folder, real Chrome/Edge extensions pages, separate Close and Open app auto-close | Qt source rendered at 200%, automated Qt tests, private packaged installation PASS; owner clicks UNTESTED |
| Desktop launcher | Branded icon on redirected Desktop and Start Menu, no terminal, owned-only uninstall cleanup | Synthetic + actual private setup sandbox PASS |
| Direct file download | One dialog for URL, safe custom name, folder selection, Browse, validation | Qt form + existing queue regression PASS, native file dialog rendering inspected offscreen |
| Completion popup lifecycle | Close/Open/Open Folder closes completed job progress, not main window; no duplicate cancel prompts | Isolated Qt regression PASS |

**Not applicable:** custom canvas zoom/pan and a resizable multiline composer (this product has neither a spatial canvas nor a text editor). Desktop app is Windows-native; mobile responsive checks apply to the browser settings page, not a nonexistent mobile desktop client.

## Verification boundaries

**Automated:** tests verify behaviors and basic layout, not every visual accessibility property. **Rendered:** Windows desktop screenshots and isolated Chrome/Playwright page screenshots in `C:\Users\ROC STORE\Documents\Stratum_Safety_Backups\i-ds-ux-20261117`. **Owner acceptance:** still required. **Newly verified (2026-11-18):** Isolated Edge MV3 extension accepted a synthetic link through the real Qt bridge into exactly one queue job, while prior fallback checks preserved the native browser download. Actual user-profile browser installation and full content transfer are not yet accepted. Converter was rendered at 900×560 and 760×480 at 130% text and passed real FFmpeg re-encode/decode checks. **Still not claimed:** installed Chrome acceptance, full public YouTube playback, signed production installer, or all Windows display scale combinations.

Avoid assigning development to a second active agent while this repository has the `AGENTS.md` one-writer rule. Reuse local skills selectively; do not install unrelated toolkits into the app.
