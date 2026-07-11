# IDM Extension Debug & Testing Guide

## File Structure
```
IDM_Extension/
├── manifest.json   # Extension configuration
├── background.js   # Background script (handles communication)
├── content.js      # Content script (runs on web pages)
└── README.md       # This file
```

## Debug Steps

### 1. Enable Debug Logging
Open browser console (F12) and run:
```javascript
localStorage.setItem('idm_debug', 'true');
```
Refresh the page to see debug messages.

### 2. Test Content Script Loading
1. Open Chrome Extensions (`chrome://extensions/`)
2. Enable "Developer mode"
3. Load unpacked extension from `IDM_Extension` folder
4. Visit a page with a video (e.g., YouTube)
5. Open DevTools Console - you should see: `[IDM Clone] Content script initialized`

### 3. Test Button Appearance
- Hover over any `<video>` element
- Button should appear above the video with "⬇ Download Video" text
- Button should have blue background (#0078D7)

### 4. Test Communication Flow
1. Start `idm_clone.py` (the Python server)
2. Hover over video and click the download button
3. Check DevTools console for messages:
   - "⏳ Sending..." → button state
   - "✅ Sent!" → success
   - "❌ Try Again" → connection failed

## Common Issues & Solutions

### Issue: Button Not Appearing
**Causes:**
- Video element has no `src` attribute
- Video is in a shadow DOM (YouTube uses this)
- Parent container has `overflow: hidden`

**Solution:** The enhanced script appends to `document.body` and uses `position: fixed` to avoid clipping.

### Issue: Click Not Working
**Causes:**
- Event consumed by YouTube's player
- Event bubbling issues

**Solution:** Use `event.stopPropagation()` and attach to `document.body` instead of video container.

### Issue: "Connection Failed"
**Causes:**
- Python server not running
- Port 8000 blocked by Windows Firewall
- CORS headers missing

**Solution:**
1. Run `python idm_clone.py` first
2. Check Windows Firewall allows connections on port 8000
3. Verify server responds: `curl http://127.0.0.1:8000/`

### Issue: Blob URLs (blob:null/...)
**Cause:** YouTube and some sites use blob URLs for video streams
**Solution:** Script filters blob URLs and falls back to page URL

## Testing Checklist

- [ ] Extension loads without errors in `chrome://extensions/`
- [ ] Content script logs in console on video pages
- [ ] Button appears on hover over `<video>` elements
- [ ] Button position is correct and visible
- [ ] Button click triggers message to background script
- [ ] Background script sends request to Python server
- [ ] Python server receives and processes URL

## Manifest Permissions Explained

```json
{
  "permissions": [
    "contextMenus",  // Right-click menu
    "activeTab"      // Current tab access
  ],
  "host_permissions": [
    "<all_urls>",              // Run content script everywhere
    "http://127.0.0.1:8000/*"  // Connect to Python server
  ]
}
```
