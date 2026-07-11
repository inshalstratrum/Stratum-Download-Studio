document.addEventListener('DOMContentLoaded', () => {
    chrome.storage.local.get(['authToken'], (result) => {
        if (result.authToken) {
            document.getElementById('token').placeholder = 'A token is currently saved';
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
    const status = document.getElementById('status');

    if (!/^[a-fA-F0-9]{64}$/.test(token)) {
        status.style.color = '#d13438';
        status.textContent = 'Error: Token must be exactly 64 hexadecimal characters.';
        return;
    }

    chrome.storage.local.set({ authToken: token }, () => {
        status.style.color = 'green';
        status.textContent = 'Token saved successfully.';
        document.getElementById('token').value = '';
        document.getElementById('token').placeholder = 'A token is currently saved';
        setTimeout(() => { status.textContent = ''; }, 2000);
    });
});

document.getElementById('clear').addEventListener('click', () => {
    document.getElementById('token').value = '';
    document.getElementById('token').placeholder = 'Paste 64-character hex token here';
    chrome.storage.local.remove('authToken', () => {
        const status = document.getElementById('status');
        status.style.color = '#d13438';
        status.textContent = 'Token cleared.';
        setTimeout(() => { status.textContent = ''; }, 2000);
    });
});
