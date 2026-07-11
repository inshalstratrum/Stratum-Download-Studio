# Stratrum Download Studio Browser Extension

This Manifest V3 extension adds **Download with Stratrum Download Studio** to the link, video, and audio context menus. The same source package is compatible with Google Chrome and Microsoft Edge.

## Security model

- The extension talks only to `http://127.0.0.1:8000/add_download`.
- Requests require the 64-character local token copied from desktop **Options > Browser Integration**.
- The token is stored in browser-local extension storage and is not written to logs.
- The desktop app pairs the first strictly valid extension origin only after the entire authenticated request passes validation.
- Use **Reset Browser Pairing** in desktop Options before reinstalling the extension under a different origin.

## Load unpacked for development

Official Chrome Web Store and Edge Add-ons listings do not exist yet. Do not claim that store installation is available until those listings are published.

### Chrome

1. Open `chrome://extensions/`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose this `IDM_Extension` directory.
5. Open the extension's **Options**, paste the desktop token, and select **Save Token**.

### Microsoft Edge

1. Open `edge://extensions/`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose this `IDM_Extension` directory.
5. Open the extension's **Options**, paste the desktop token, and select **Save Token**.

## Packaged review builds

Run `powershell -ExecutionPolicy Bypass -File IDM_Extension/package_extension.ps1` from the repository root. It produces:

- `extension_packages/stratrum-download-studio-chrome.zip`
- `extension_packages/stratrum-download-studio-edge.zip`

These ZIP files are review/submission artifacts. Browser security policies still require normal store review or explicit developer-mode loading; the desktop app never attempts silent installation.

## Store publication gate

Before changing the first-launch prompt from the manual workflow to direct installation:

1. Submit the Chrome ZIP to the Chrome Web Store.
2. Submit the Edge ZIP to Microsoft Edge Add-ons.
3. Complete each store's review process.
4. Replace the official-store landing-page constants in `inshal_dm.py` with the two approved listing URLs.
5. Re-run the manual checklist in `docs/09_PHASE_2A3_MANUAL_TEST.md`.

## Local connection checks

- Start the desktop app before using the context menu.
- Confirm the token was saved in extension Options.
- If a reinstall changes the extension origin, reset browser pairing in the desktop app and send one fully valid link again.
- If port 8000 is unavailable, exit the desktop app fully and confirm no stale process is listening before restarting.
