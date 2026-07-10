let currentBtn = null;
let hoverTimer = null;

document.addEventListener('mouseover', (e) => {
    // If we're hovering over a video OR our own button, keep it alive
    if (e.target.tagName === 'VIDEO' || (e.target.className && e.target.className === 'idm-grabber-btn')) {
        
        clearTimeout(hoverTimer); // Cancel any pending removals

        if (!currentBtn) {
            currentBtn = document.createElement('button');
            currentBtn.innerText = '⬇ Download this video';
            currentBtn.className = 'idm-grabber-btn';
            
            // IDM-style styling
            Object.assign(currentBtn.style, {
                position: 'absolute',
                zIndex: '2147483647', // Maximum possible z-index to stay above YouTube UI
                backgroundColor: '#f1f1f1',
                color: '#333',
                border: '1px solid #ccc',
                padding: '4px 8px',
                cursor: 'pointer',
                borderRadius: '3px',
                fontSize: '12px',
                fontFamily: 'Arial, sans-serif',
                fontWeight: 'bold',
                boxShadow: '2px 2px 5px rgba(0,0,0,0.3)',
                display: 'block'
            });

            // Append directly to the body to escape YouTube's hidden overflow containers
            document.body.appendChild(currentBtn);

            // Click Handler
            currentBtn.addEventListener('click', (event) => {
                // VERY IMPORTANT: Stop YouTube from pausing the video when we click the button
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                
                let urlToDownload = window.location.href; 
                if (e.target.src && !e.target.src.startsWith('blob:')) {
                    urlToDownload = e.target.src;
                }
                
                // Change text to show it's working
                currentBtn.innerText = "⏳ Sending...";
                
                chrome.runtime.sendMessage({ action: "SEND_TO_IDM", url: urlToDownload }, (response) => {
                    if (chrome.runtime.lastError || !response || !response.success) {
                        alert("Error: IDM Clone must be open and running.");
                        currentBtn.innerText = '⬇ Download this video';
                    } else {
                        currentBtn.innerText = '✅ Sent to IDM';
                        setTimeout(() => removeButton(), 2000);
                    }
                });
            }, true); // Use capture phase
        }

        // Calculate position based on the video element we are hovering over
        let targetVideo = e.target.tagName === 'VIDEO' ? e.target : document.elementFromPoint(e.clientX, e.clientY);
        
        if (targetVideo && targetVideo.tagName === 'VIDEO') {
            let rect = targetVideo.getBoundingClientRect();
            // Position just OUTSIDE the top right corner of the video
            let topPos = rect.top + window.scrollY - 30; 
            
            // If the video is at the very top of the page, push it inside slightly so it's not off-screen
            if (topPos < 0) topPos = 10;
            
            currentBtn.style.top = topPos + 'px';
            currentBtn.style.left = (rect.right + window.scrollX - 160) + 'px'; // 160px is approx button width
        }
    }
});

// Remove logic
document.addEventListener('mouseout', (e) => {
    if (e.target.tagName === 'VIDEO' || (e.target.className && e.target.className === 'idm-grabber-btn')) {
        // Don't remove immediately, give the user time to move their mouse to the button
        hoverTimer = setTimeout(() => {
            removeButton();
        }, 1500); 
    }
});

function removeButton() {
    if (currentBtn && currentBtn.parentNode) {
        currentBtn.parentNode.removeChild(currentBtn);
        currentBtn = null;
    }
}