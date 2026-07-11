# Firefox Development and Distribution

The Firefox package reuses `media_candidates.js`, `background.js`, `content.js`, `options.html`, and `options.js` from `browser_extension/`; only this manifest and Firefox-specific documentation differ.

For development, run `browser_extension/package_extension.ps1`, open `about:debugging`, choose **This Firefox** > **Load Temporary Add-on**, and select the generated Firefox ZIP. Temporary add-ons disappear when Firefox restarts.

The stable legacy development add-on ID remains `stratrum-download-studio@stratrum.local` for pairing compatibility. The visible product name is Stratum Download Studio, and the manifest declares that the extension collects no data for external transmission or storage.

An unsigned Firefox package is not customer-ready. Firefox self-distribution requires a Mozilla-signed XPI. See Mozilla's [signing guide](https://extensionworkshop.com/documentation/develop/getting-started-with-web-ext/) and [self-distribution guide](https://extensionworkshop.com/documentation/publish/self-distribution/).
