# Stratum Download Studio — User FAQ

## How does browser integration work?

Install the Stratum extension from the `browser_extension` folder, open **Browser Integration** in the desktop app, and copy the masked pairing token into the extension Options page. When a supported player is visible, its own Stratum button sends only that player’s validated page or media route to the desktop app. The extension does not send browser cookies.

## Why does the button say “Detecting video…”?

Some players request their complete HLS, DASH, Shaka, or Brightcove route only after interaction. Stratum waits briefly for that player’s delayed evidence instead of rejecting the click immediately. The wait is bounded; if no complete route appears, Stratum reports that no complete downloadable media was detected.

## Should I play a stream before downloading it?

Yes, when a button appears but no choice is ready. Start playback for a moment, then click the same player’s Stratum button. Playback helps the site request its master stream while keeping detection tied to that player.

## What can I do with a login-required post?

Anonymous extraction is always attempted first. For media you are authorized to access, open **Browser Integration**, explicitly enable authenticated retry, and select Chrome, Edge, or Firefox plus the intended profile. Stratum asks yt-dlp to read that browser session locally only after an authentication-style failure. Cookies are not copied into Stratum, sent through the extension, or reused by Stratum across sites. Disable the setting when it is not needed.

## Why is resolution information unavailable?

Some pages expose a complete route without publishing trustworthy resolution metadata before extraction. **Best available** still lets yt-dlp select the strongest compatible result. A missing resolution label does not mean the media is low quality.

## What do compatible MP4 and WebM mean?

The MP4 profile prefers H.264 video with AAC/M4A audio for normal Windows playback. The WebM profile prefers VP8, VP9, or AV1 video with Opus or Vorbis audio. If the site offers no compatible native combination, Stratum uses its controlled FFmpeg conversion path and FFprobe-verifies the final container and streams before completion.

## Which public media is supported?

Stratum supports public media that yt-dlp can extract plus validated direct files and safe complete master manifests. Current regression coverage includes ordinary Instagram posts and reels, Facebook and TikTok post routes, Dailymotion, Vimeo, CNN, CNBC, Al Jazeera/Brightcove, NLM media and YouTube embeds, DASH-IF, Shaka, direct MP4 files, and signed masters. Site behavior can change, and DRM or access-controlled playback is not supported.

## What do common download or verification errors mean?

- **No complete downloadable media detected:** play the correct visible player briefly and try its own button again.
- **Login or no public formats:** the post may be private, expired, region-limited, or require the optional browser-profile retry.
- **Format inspection failed:** you may still start with **Best available**, but confirm the URL and authorization first.
- **Conversion failed:** FFmpeg could not create the requested compatible profile; check free disk space and retry another output profile.
- **Verification failed:** FFprobe did not confirm the requested final container or required stream, so Stratum correctly refused to mark the job complete.

## What is the safe troubleshooting order?

1. Confirm that you own the media or have permission to save it.
2. Reload the page, play only the intended player, and wait for its Stratum button.
3. Start the desktop app and verify extension pairing if sending fails.
4. Use the public route first; enable authenticated retry only when the site requires your own session.
5. Try **Best available** and compatible MP4 before choosing a specialized profile.
6. Keep signed URLs, pairing tokens, browser profiles, and authentication details out of screenshots and support messages.
7. If FFprobe rejects the output, keep the error summary and retry; do not rename the file extension.
