# 05 IMPLEMENTATION PLAN

## Stage 1: Stabilization & Security (Phase 2)
1. **Clean Codebase:** Delete `main.py`, `uiux_reference`, and redundant `idm_history.json`.
2. **Path Resolution:** Migrate `inshaldm_history.json` to `%APPDATA%\StratrumDownloadStudio\history.json`.
3. **Security Fixes:**
   - Secure the local TCP server (remove `Access-Control-Allow-Origin: *` or implement an auth token).
   - Fix command injection in `subprocess.Popen` by using list arguments: `['explorer', '/select,', path]`.
   - Add a warning prompt before executing files via `os.startfile()`.
4. **Resiliency:** Improve error handling in `load_downloads_from_file` and yt-dlp execution.

## Stage 2: Legal & Rebranding (Phase 3)
1. **Framework Migration:** Migrate from `PyQt6` to `PySide6` to comply with LGPL for commercial use.
2. **Rebranding:** Rename the application to "Stratrum Download Studio".
3. **UI Modernization:** Implement a clean, professional dashboard replacing the IDM-clone UI.
4. **Legal Notice:** Inject the mandatory disclaimer: *"Download or convert only content that you own..."* into the About page and first-launch screen.

## Stage 3: Licensing & Obfuscation (Phase 4)
1. **Licensing Server Contract:** Design a standard REST API for checking machine fingerprints against a Supabase backend.
2. **Client Implementation:** Add an Activation window that generates a machine-specific hardware ID, validates via HTTP, and stores a signed JWT token locally for offline grace periods.
3. **Code Protection:** Implement `Cython` to compile critical Python files (like the licensing module) into `.pyd` extensions, combined with PyInstaller, to prevent trivial decompilation.

## Stage 4: Packaging & Release (Phase 5)
1. **Build Scripts:** Create `START_DEV.bat`, `RUN_TESTS.bat`, `BUILD_RELEASE.bat`, `PACKAGE_INSTALLER.bat`.
2. **Installer:** Write an Inno Setup script (`.iss`) to compile the executable into a professional Windows installer.
3. **Documentation:** Generate EULA, third-party notices, and quick-start guides.

## Stage 5: Testing (Phase 6)
1. Write automated `pytest` suites for URL extraction, file writing, and licensing logic.
2. Perform manual integration tests across Windows 10/11 environments.
