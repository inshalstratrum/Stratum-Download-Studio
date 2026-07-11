document.addEventListener('DOMContentLoaded', () => {
    chrome.storage.local.get(['authToken'], (result) => {
        if (result.authToken) {
            document.getElementById('token').value = result.authToken;
        }
    });
});

document.getElementById('toggle-visibility').addEventListener('click', () => {
    const tokenInput = document.getElementById('token');
    const toggleBtn = document.getElementById('toggle-visibility');
    if (tokenInput.type === 'password') {
        tokenInput.type = 'text';
        toggleBtn.textContent = 'Hide';
    } else {
        tokenInput.type = 'password';
        toggleBtn.textContent = 'Show';
    }
});

document.getElementById('save').addEventListener('click', () => {
    const token = document.getElementById('token').value.trim();
    chrome.storage.local.set({ authToken: token }, () => {
        const status = document.getElementById('status');
        status.style.color = 'green';
        status.textContent = 'Token saved successfully.';
        setTimeout(() => { status.textContent = ''; }, 2000);
    });
});

document.getElementById('clear').addEventListener('click', () => {
    document.getElementById('token').value = '';
    chrome.storage.local.remove('authToken', () => {
        const status = document.getElementById('status');
        status.style.color = '#d13438';
        status.textContent = 'Token cleared.';
        setTimeout(() => { status.textContent = ''; }, 2000);
    });
});
