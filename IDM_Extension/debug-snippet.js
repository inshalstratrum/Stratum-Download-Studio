// ==========================================
// DEBUG SNIPPET - Run in browser console
// ==========================================

// Quick test functions for debugging the extension

window.IDM_Debug = {
    // Check if content script is loaded
    checkLoaded: () => {
        const btn = document.getElementById('idm-download-btn');
        console.log('IDM Button in DOM:', !!btn);
        return !!btn;
    },

    // Force create a test button
    testButton: () => {
        const videos = document.querySelectorAll('video');
        console.log('Found videos:', videos.length);

        if (videos.length > 0) {
            const video = videos[0];
            const rect = video.getBoundingClientRect();
            console.log('Video rect:', rect);

            // Create test button
            const btn = document.createElement('button');
            btn.textContent = 'Test Download';
            btn.style.cssText = `
                position: fixed;
                top: ${rect.top + 10}px;
                left: ${rect.left + 10}px;
                z-index: 2147483647;
                background: #0078D7;
                color: white;
                padding: 10px;
                cursor: pointer;
            `;

            btn.onclick = () => {
                chrome.runtime.sendMessage(
                    { action: 'SEND_TO_IDM', url: window.location.href },
                    (response) => console.log('Response:', response)
                );
            };

            document.body.appendChild(btn);
            console.log('Test button created');
            return true;
        }
        console.log('No video elements found');
        return false;
    },

    // Check video sources
    checkVideoSources: () => {
        const videos = document.querySelectorAll('video');
        videos.forEach((v, i) => {
            console.log(`Video ${i}:`, {
                src: v.src || v.querySelector('source')?.src,
                hasSrc: !!v.src,
                blob: v.src.startsWith('blob:')
            });
        });
    },

    // Test server connection
    testServer: async () => {
        try {
            const response = await fetch('http://127.0.0.1:8000/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: window.location.href })
            });
            console.log('Server response:', response.status);
            return response.ok;
        } catch (e) {
            console.error('Connection failed:', e.message);
            return false;
        }
    }
};

console.log('IDM Debug loaded. Run IDM_Debug.testButton() to test');

// Auto-run check
setTimeout(() => {
    console.log('[IDM] Checking videos...');
    IDM_Debug.checkVideoSources();
}, 1000);
