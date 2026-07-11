# Stratum Download Studio Browser Extensions

The Chromium Manifest V3 source in this directory supports Google Chrome and Microsoft Edge. It preserves right-click link/video/audio downloads and adds a user-controlled button beside detected HTML5 video and audio elements.

## Why broad site access is requested

Automatic media detection requires a content script on `http://*/*` and `https://*/*`. Chrome and Edge therefore show a broad permission warning. The content script observes only added `VIDEO` and `AUDIO` elements. It does not read forms, cookies, browser history, or unrelated page text, and it sends no URL or telemetry until the user clicks a Stratum button.

Direct HTTP/HTTPS media sources are sent directly. Blob, MediaSource, segmented, unavailable, and unsupported sources fall back to the current HTTP/HTTPS page URL so the desktop downloader can resolve them.

The option **Show download button on detected media** is enabled by default and can be disabled in extension Options.

## Chrome and Edge development

1. Open `chrome://extensions/` or `edge://extensions/`.
2. Enable Developer mode.
3. Select **Load unpacked** once.
4. Choose this `browser_extension/` directory directly. Do not extract a generated ZIP for development.
5. Open extension Options, save the masked desktop token, and confirm the media-button option.

Do not install the unpacked source and an extracted submission package simultaneously. They receive different extension origins and create confusing duplicate buttons and pairings.

An inactive Manifest V3 service worker is normal: Chromium sleeps it until an extension event needs it. Sleeping is not an error.

## Connection messages

- Missing token: Options opens and the page shows where to save the token.
- Desktop unavailable: the page shows a concise start-the-desktop-app message.
- Pairing rejected: the page directs the user to reset browser pairing in desktop Options.
- Tokens are never displayed in page messages or written to logs.

## Packaging

Run `powershell -ExecutionPolicy Bypass -File browser_extension/package_extension.ps1` from the repository root. It creates separate Chrome, Edge, and Firefox ZIPs under ignored `extension_packages/`. ZIPs are for store submission/testing, not Chromium unpacked development. Packaging does not create tokens or random add-on IDs.

## Distribution limits

- Chrome consumer release requires publication through the Chrome Web Store.
- Edge consumer release requires publication through Microsoft Edge Add-ons.
- Firefox self-distribution requires a Mozilla-signed XPI; an unsigned development ZIP is not customer-ready.
- Enterprise force-install policies are for managed organizations, not normal consumer installation.
- A future desktop installer may offer a user-confirmed browser-extension suggestion after installation. It must not attempt silent consumer installation.

The desktop application never shows extension-install dialogs during normal startup. Browser Integration remains available manually from desktop Options.

Up to six valid extension origins can be paired concurrently. Use **Remove Selected** to retire one browser origin or **Reset All Pairings** before a broad reinstall.
