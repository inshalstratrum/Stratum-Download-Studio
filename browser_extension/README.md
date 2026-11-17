# I-DS Browser Companion (Chrome / Edge)

**Tool by InShaLIve.os**

This is the unpacked Manifest V3 extension source for I-DS. It offers **right-click media/link handoff**, **supported video/audio detection**, and an **in-player download button**. Phase 2B beta adds a **default-off opt-in** for ordinary browser downloads (PDF, ZIP, installers, images and other known file types). The desktop must acknowledge queued file ownership before the extension cancels Chrome's paused copy.

## Install for development

1. Start the I-DS desktop application with **START I-DS.cmd**.
2. Open **chrome://extensions** or **edge://extensions** and enable Developer mode.
3. Choose **Load unpacked** and select this **browser_extension** directory, not a ZIP.
4. Click the I-DS extension toolbar icon to open settings.
5. Desktop → **Options → Browser Integration → Copy Token**; paste it into extension settings and save.

If the token is missing, Settings opens automatically. For connection issues, restart the desktop app and verify local pairing. Do not share pairing tokens.

## Usage

- Right-click a page link, video, or audio source and choose **Quick Download with I-DS** or **Download with Options in I-DS**.
- Right-click **Download file with I-DS** for a direct general HTTP(S) file.
- Enable **Automatically use I-DS for supported browser files** in extension settings only if you want ordinary Chrome downloads handed to the desktop. Handoff failures resume the original browser download. Once the desktop has accepted a job, later server failures still require retry in I-DS.
- The **I-DS** button appears on detectable playable media. You can disable it under the extension settings.
- The toolbar icon opens settings; it does not trigger a download by itself.

The extension inspects permitted HTTP/HTTPS pages, frames, and response metadata to identify supported media. It suppresses segmented fragments, avoids unsafe URL schemes, does not send stored browser cookies or auth headers to the desktop app, and keeps candidate metadata inside the extension until a user chooses a download. DRM is unsupported.

## Browser permissions

- HTTP/HTTPS site access: detect supported media elements and response candidates.
- Context menus: show explicit right-click download actions.
- Local storage: remember the masked pairing token, media-button preference and opt-in interception setting. Also retains paused native download IDs for startup recovery (no URLs or files).
- Loopback HTTP on 127.0.0.1:18765: communicate with the desktop application.

The `downloads` permission enables opt-in file interception. The extension first pauses the native Chrome file, waits for an authenticated desktop job acceptance, then cancels the native copy; if acceptance fails, it resumes Chrome. It never accesses browser cookies or credential headers, so private/session-dependent files may fail after desktop acceptance. Interception remains **off by default** and is not yet signed or store-published.

## Tests

Run `node --test *.test.js` from this directory, or `node --test browser_extension/*.test.js` from the repository root.

## Packaging and limitations

Use `powershell -ExecutionPolicy Bypass -File browser_extension/package_extension.ps1` from the repository root for development ZIPs. These are **not** Chrome Web Store, Edge Add-ons, or Firefox-approved releases. Firefox has a separate extension source directory and its own distribution requirements.

## Distribution and safe installation

- **Chrome Web Store** publication is required for normal Chrome consumer installation.
- **Microsoft Edge Add-ons** publication is required for normal Edge consumer installation.
- **Mozilla-signed XPI** is required for normal Firefox self-distribution.
- **Enterprise force-install** applies to managed organizations, not consumer browsers.
- A desktop installer may provide a **user-confirmed** suggestion to install the extension but must not attempt **silent consumer installation**.

## Single development installation

- Choose this `browser_extension/` directory directly through Load unpacked.
- Do not install the unpacked source and an extracted submission package simultaneously. These are separate extension origins and can cause confusing duplicate controls and pairings.
- An inactive Manifest V3 service worker is normal: Chromium suspends it between events. Sleeping is not an error.
