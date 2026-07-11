# Phase 2A.4 Windows Browser and Progress Checklist

Status: not yet performed. Use only media and URLs the tester owns or is authorized to download. Record the commit, Windows/browser versions, and result for every step.

## Desktop startup and Chromium development installation

1. Start `python stratrum_download_studio.py`. Confirm no browser-store or extension-install dialog appears automatically.
2. Open desktop **Options > Browser Integration** and confirm the masked token, paired-origin list, **Remove Selected**, **Reset All Pairings**, and **Open Extension Guide** are available.
3. In Chrome, remove every older Stratrum copy. Open `chrome://extensions/`, enable Developer mode, select **Load unpacked** once, and choose the repository's `browser_extension/` directory directly.
4. Do not extract or install a generated submission ZIP. Confirm only one unpacked Stratrum extension is installed.
5. Open extension Options, save the desktop token, and keep **Show download button on detected media** enabled.

## Automatic media detection and right-click behavior

6. Open an authorized normal HTML5 video page over HTTP or HTTPS. Confirm one small Stratrum button appears near the video and no download starts automatically.
7. Use DevTools on a disposable authorized test page to insert a new `<video controls src="https://authorized.example/sample.mp4">` element. Confirm exactly one new button appears without reloading.
8. Click the button for a direct HTTP/HTTPS media source. Confirm the desktop add-download dialog receives the direct media URL.
9. On an authorized blob/MediaSource/segmented player, click the button and confirm the desktop receives the page URL fallback.
10. Disable **Show download button on detected media** in extension Options. Confirm existing buttons disappear and dynamically added media receives no button. Re-enable it and confirm detection resumes.
11. Right-click an authorized link, video, and audio element and confirm **Download with Stratrum Download Studio** still sends each target.

## Visible connection failures

12. Clear the token in extension Options and click a media button. Confirm a visible message directs the user to extension Options and no token is shown or logged.
13. Restore the token, fully exit the desktop app, and click again. Confirm a visible concise message says the desktop app is unavailable.
14. Restart the desktop app, fill the six-origin pairing limit only in a disposable test configuration, and try another browser origin. Confirm the visible message directs the user to reset browser pairing.
15. Confirm a sleeping Manifest V3 service worker is not reported as an error; it should wake on a context-menu click or media-button message.

## Multiple browsers and Firefox development

16. Load `browser_extension/` unpacked once in Edge, save the same desktop token, and send an authorized URL from Chrome and Edge. Confirm both origins remain paired and both continue working.
17. Run `browser_extension/package_extension.ps1`. In Firefox, open `about:debugging` > **This Firefox** > **Load Temporary Add-on** and select the generated Firefox ZIP.
18. Save the token in Firefox Options and send an authorized URL. Confirm Chrome, Edge, and Firefox appear concurrently in desktop Browser Integration.
19. Confirm documentation does not describe the unsigned Firefox ZIP as customer-ready; production self-distribution requires a Mozilla-signed XPI.
20. Delete `extension_packages/` after testing.

## Real download progress

21. Start an authorized download with a known nonzero size. Confirm the main table and popup replace **Connecting...** with the actual filename.
22. Confirm percentage, downloaded bytes/total bytes, numeric speed, ETA, and **Downloading** status change using real transfer data rather than timer-generated values.
23. Test an authorized fragmented-media download and confirm progress remains bounded from 0% through 100% without jumping above 100.
24. On successful completion, confirm both the main progress bar and last progress state reach 100%, the completed size reads downloaded/total, and existing safe Open/Open Folder behavior remains intact.

## Persistence, reset, and shutdown

25. Restart the app and confirm paired Chrome/Edge/Firefox origins persist.
26. Remove one selected origin; confirm the other browsers still work. Re-pair the removed browser with a fully valid request.
27. Choose **Reset All Pairings**, confirm the list clears, then re-pair one browser.
28. Exit from the tray **Exit** action.
29. Run `Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue` and confirm no application listener remains.

Chrome consumer release requires Chrome Web Store publication, Edge consumer release requires Edge Add-ons publication, and enterprise force-install policies are not a normal-customer installation path. A future desktop installer may offer a user-confirmed extension suggestion after installation, but silent consumer installation is not permitted.
