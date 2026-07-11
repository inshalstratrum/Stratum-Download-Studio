# Stratum Download Studio Browser Extensions

The Chromium Manifest V3 source in this directory supports Google Chrome and Microsoft Edge. It preserves right-click link/video/audio downloads and adds user-controlled detection for HTML5 media, safe embedded extractor pages, direct media, HLS, and DASH.

## Why broad site access is requested

Automatic media detection requires content scripts in permitted HTTP/HTTPS frames and non-blocking response observations on those sites. Chrome and Edge therefore show a broad permission warning. Detection observes media elements, nested sources, safe media links, supported embedded player URLs, resource URLs, and media response types. It does not read forms, cookies, authorization headers, private page contents, or unrelated page text. Candidate metadata remains inside the extension until the user clicks a Stratum button; no telemetry is sent externally.

Direct HTTP/HTTPS media and HLS/DASH manifests are offered once. Segment and chunk floods are suppressed. Blob-only players fall back to the safe page URL; `blob:`, `data:`, extension, file, and script URLs are never sent. DRM/EME media is unsupported. Detection does not claim universal site support and does not cover general files such as images, documents, archives, installers, or ISOs.

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
