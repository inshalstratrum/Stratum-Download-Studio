# Phase 2A.3 Manual Windows Smoke Test

Status: not yet performed. Run these steps on Windows from the repository root after automated verification passes.

## Browser extension setup

Official Chrome Web Store and Microsoft Edge Add-ons listings are pending. Use the documented **Load unpacked** development workflow; do not attempt silent installation or bypass browser security controls.

1. Start the application with `python stratrum_download_studio.py`.
2. On the optional first-launch prompt, confirm these choices are present: **Install Extension**, **Remind Me Later**, and **Do Not Ask Again**. For this test, choose **Remind Me Later**.
3. Open desktop **Options > Browser Integration** and select **Copy Token**. Confirm the token remains masked in the app and is not printed in the terminal or logs.
4. In Chrome, open `chrome://extensions/`; in Edge, open `edge://extensions/`.
5. Enable Developer mode, choose **Load unpacked**, and select the repository's `browser_extension` directory. Repeat in both browsers when both are available.
6. Open the extension Options page, paste the copied token, select **Save Token**, and clear the clipboard afterward.

## Pairing and request validation

7. Right-click a normal HTTPS link and choose **Download with Stratrum Download Studio**. Confirm the desktop add-download dialog receives the link.
8. Exit the desktop application from its tray **Exit** action. Start it again and send another normal HTTPS link; confirm the stored pairing still works.
9. Open desktop **Options > Browser Integration**, select **Reset Browser Pairing**, confirm the action, then send one normal link from the intended extension. Confirm that the first fully valid request pairs again.
10. In extension Options, temporarily save an incorrect 64-character hexadecimal token and send a link. Confirm the request is rejected and no download dialog opens. Restore the correct token. Confirm neither token is printed or logged.

## Download and safe opening

11. Download a harmless, small HTTPS file into a dedicated test directory. Confirm it completes and the history record retains that configured directory.
12. Use **Open** on the harmless completed file. Confirm exactly that file opens.
13. Use **Open Folder**. Confirm Explorer selects the completed file.
14. Add or download a harmless dummy file with an executable extension such as `.exe` without running it. Confirm **Open** is unavailable or blocked, while **Open Folder** remains available for the valid file.
15. If practical, edit a disposable copy of history so a completed path points outside its recorded directory. Restart and confirm both **Open** and **Open Folder** reject the manipulated path.

## Conversion and shutdown

16. Place a harmless local media sample in the test download directory and ensure a converted filename such as `sample_converted.mp3` already exists.
17. Convert the sample to that format. Confirm the existing file is not overwritten, the new output receives a unique name, success is shown only after the output exists, and **Open Folder** selects the converted output.
18. Exit through the tray **Exit** action.
19. In PowerShell run `Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue`. Confirm it returns no listening socket for the application.

Record browser versions, application commit, each result, and any screenshots or failures in the test execution record. Do not mark this checklist performed until every applicable step has actually been executed.
