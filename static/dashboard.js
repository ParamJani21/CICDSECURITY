/* ============================================
   CICDSECURITY Dashboard JavaScript
   ============================================ */

// ============ Tab Management ============
document.addEventListener('DOMContentLoaded', function() {
    sendClientLog('page_domcontentloaded', { url: window.location.pathname, activeTab: localStorage.getItem('activeTab') || 'overview' });
    initializeTabs();
    updateTimestamps();
    loadDynamicContent();
    setInterval(updateTimestamps, 1000);
});

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    sendClientLog('initializeTabs', { tabButtons: tabButtons.length, tabContents: tabContents.length });

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            sendClientLog('tab_button_clicked', { tabName });
            switchTab(tabName);
        });
    });

    // Load last active tab from localStorage or default to 'overview'
    const lastActiveTab = localStorage.getItem('activeTab') || 'overview';
    switchTab(lastActiveTab);
}

function switchTab(tabName) {
    sendClientLog('switchTab_start', { tabName });
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active class from all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    const selectedTab = document.getElementById(tabName + '-tab');
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Add active class to corresponding button
    const tabButton = document.querySelector(`[data-tab="${tabName}"]`);
    if (tabButton) {
        tabButton.classList.add('active');
    }

    // Save active tab to localStorage
    localStorage.setItem('activeTab', tabName);

    // Load content if needed
    loadTabContent(tabName);
    sendClientLog('switchTab_complete', { tabName });
}

// ============ Dynamic Content Loading ============
// Client logging helper (global)
function sendClientLog(event, details = {}, level = 'info') {
    const payload = { event, details, level };
    const url = '/api/log';
    try {
        if (navigator && navigator.sendBeacon) {
            const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
            navigator.sendBeacon(url, blob);
            return;
        }
    } catch (e) {
        // ignore and fallback to fetch
    }

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).catch(() => {});
}

function instrumentFetchLogging() {
    if (window.__fetchLoggingInstrumented) return;
    window.__fetchLoggingInstrumented = true;

    const originalFetch = window.fetch.bind(window);
    window.fetch = function(resource, init) {
        const url = typeof resource === 'string' ? resource : (resource && resource.url) ? resource.url : 'unknown';
        const method = (init && init.method) || (resource && resource.method) || 'GET';

        if (url !== '/api/log') {
            sendClientLog('fetch_start', { url, method }, 'debug');
        }

        return originalFetch(resource, init)
            .then(response => {
                if (url !== '/api/log') {
                    sendClientLog('fetch_complete', { url, method, status: response.status }, response.ok ? 'info' : 'warning');
                }
                return response;
            })
            .catch(error => {
                if (url !== '/api/log') {
                    sendClientLog('fetch_error', { url, method, message: error.message || String(error) }, 'error');
                }
                throw error;
            });
    };
}

function loadDynamicContent() {
    sendClientLog('loadDynamicContent_start');
    loadTabContent('overview');
    loadRepositories();
    renderScansChart();
    loadCurrentScanningRepos();
    sendClientLog('loadDynamicContent_complete');
}

function loadTabContent(tabName) {
    sendClientLog('loadTabContent', { tabName });
    switch(tabName) {
        case 'repos':
            // Repositories are loaded on page refresh only, not on tab switch
            break;
        case 'history':
            loadHistory();
            break;
        case 'settings':
            loadSettings();
            break;
        default:
            break;
    }
}

function renderScansChart() {
    const ctx = document.getElementById('scansChart');
    if (!ctx) return;

    // Chart will be populated from API data
    // To be implemented with actual backend data via /api/overview
    // Chart will display vertical stacked bar chart with repositories on x-axis
}

function loadCurrentScanningRepos() {
    const scanningReposList = document.getElementById('scanning-repos-list');
    if (!scanningReposList) return;

    // Will be populated from API data
    // To be implemented with actual backend data via /api/overview
    scanningReposList.innerHTML = '<p style="color: #64748b; text-align: center; padding: 2rem 1rem;">Waiting for scan data...</p>';
}

function loadRepositories() {
    const reposList = document.getElementById('repos-list');
    if (!reposList) return;
    // Try to render cached repos immediately to avoid long waits
    sendClientLog('loadRepositories_start', { cached: !!localStorage.getItem('reposCache') });
    const cache = localStorage.getItem('reposCache');
    if (cache) {
        try {
            const cached = JSON.parse(cache);
            if (Array.isArray(cached) && cached.length > 0) {
                reposList.innerHTML = renderReposHtml(cached);
            }
        } catch (e) {
            console.warn('Invalid repos cache', e);
        }
    } else {
        reposList.innerHTML = '<div style="grid-column: 1 / -1; padding: 2rem 1rem; text-align: center; color: #64748b;">Loading repositories...</div>';
    }

    // Fetch fresh repos in background with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    fetch('/api/repos', { signal: controller.signal })
        .then(response => response.json())
        .then(data => {
            clearTimeout(timeoutId);
            const repos = data.repositories || [];
            // Update cache
            try { localStorage.setItem('reposCache', JSON.stringify(repos)); } catch (e) { /* ignore */ }
            // Render
            reposList.innerHTML = repos.length > 0 ? renderReposHtml(repos) : '<div style="grid-column: 1 / -1; padding: 2rem; text-align: center; color: #64748b;">No repositories available</div>';
            sendClientLog('loadRepositories_success', { count: repos.length });
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.warn('Repo fetch aborted (timeout)');
                sendClientLog('loadRepositories_timeout', {}, 'warning');
            } else {
                console.error('Error loading repositories:', error);
                sendClientLog('loadRepositories_error', { message: error.message || String(error) }, 'error');
            }
            // leave cached content visible
        });
}

function renderReposHtml(repos) {
    let html = '';
    repos.forEach(repo => {
        // Extract owner from repo object or construct from clone_url
        let repoOwner = repo.owner || 'unknown';
        let repoUrl = repo.clone_url || repo.html_url || `https://github.com/${repoOwner}/${repo.name}.git`;
        let repoBranch = repo.branch || repo.default_branch || 'main';
        
        // Escape quotes for JavaScript
        const escapedName = (repo.name || '').replace(/'/g, "\\'");
        const escapedOwner = (repoOwner || '').replace(/'/g, "\\'");
        const escapedUrl = (repoUrl || '').replace(/'/g, "\\'");
        const escapedBranch = (repoBranch || '').replace(/'/g, "\\'");
        
        html += `
            <div class="table-row">
                <div class="col-repo-name">${repo.name || 'N/A'}</div>
                <div class="col-repo-id">${repo.id || 'N/A'}</div>
                <div class="col-repo-branch">${repoBranch || 'N/A'}</div>
                <div class="col-repo-action">
                    <button class="scan-btn" onclick="triggerManualScan('${repo.id}', '${escapedName}', '${escapedOwner}', '${escapedUrl}', '${escapedBranch}')">Scan</button>
                </div>
            </div>
        `;
    });
    return html;
}

// Simple non-blocking toast notification helper (replaces alert)
function showToast(message, type = 'info', timeout = 6000) {
    try {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.position = 'fixed';
            container.style.right = '1rem';
            container.style.bottom = '1rem';
            container.style.zIndex = 9999;
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = 'toast-notification toast-' + type;
        toast.style.background = type === 'error' ? '#ffdddd' : (type === 'success' ? '#e6ffed' : '#ffffff');
        toast.style.color = '#0f172a';
        toast.style.border = '1px solid #cbd5e1';
        toast.style.padding = '0.6rem 0.9rem';
        toast.style.marginTop = '0.5rem';
        toast.style.borderRadius = '6px';
        toast.style.boxShadow = '0 6px 18px rgba(2,6,23,0.08)';
        toast.style.maxWidth = '28rem';
        toast.style.fontSize = '0.95rem';
        toast.textContent = message;

        container.appendChild(toast);

        setTimeout(() => {
            try { toast.remove(); } catch (e) { /* ignore */ }
        }, timeout);
    } catch (e) {
        try { console.log('Toast:', message); } catch (e2) {}
    }
}

function triggerManualScan(repoId, repoName, repoOwner, repoUrl, repoBranch) {
    if (!repoId) {
        console.error('Repository ID is required');
        return;
    }
    
    if (!repoName || !repoOwner) {
        console.error('Repository name and owner are required');
        return;
    }

    // Trigger manual scan via API
    sendClientLog('triggerManualScan_start', { repoId, repoName, repoOwner });
    fetch('/api/repos/scan', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
            repo_id: repoId,
            repo_name: repoName,
            repo_owner: repoOwner,
            repo_url: repoUrl || `https://github.com/${repoOwner}/${repoName}.git`,
            repo_branch: repoBranch || 'main'
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Scan triggered:', data);
        if (data.status === 'success') {
            sendClientLog('triggerManualScan_success', { repoId, repoName, repoOwner, repo_path: data.repo_path });
            // Show non-blocking success notification
            showToast(`✓ Scan started for ${repoOwner}/${repoName} — cloned to: ${data.repo_path}`, 'success');
        } else {
            sendClientLog('triggerManualScan_error', { repoId, message: data.message }, 'error');
            showToast(`✗ Scan failed: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error triggering scan:', error);
        sendClientLog('triggerManualScan_error', { repoId, message: error.message || String(error) }, 'error');
        showToast(`✗ Error: ${error.message || 'Failed to trigger scan'}`, 'error');
    });
}

function loadHistory() {
    const historyList = document.getElementById('history-list');
    if (!historyList || historyList.innerHTML) return; // Already loaded

    sendClientLog('loadHistory_start');

    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            let html = '';
            if (data.history && data.history.length > 0) {
                data.history.forEach(scan => {
                    const critical = scan.critical || 0;
                    const high = scan.high || 0;
                    const medium = scan.medium || 0;
                    
                    const issuesHtml = `
                        <span class="issue-count critical">${critical}</span>/
                        <span class="issue-count high">${high}</span>/
                        <span class="issue-count medium">${medium}</span>
                    `;
                    
                    html += `
                        <div class="table-row">
                            <div class="col-time">${formatDate(scan.timestamp)}</div>
                            <div class="col-repo">${scan.repository || 'N/A'}</div>
                            <div class="col-type">${scan.scan_type || 'N/A'}</div>
                            <div class="col-issues">${issuesHtml}</div>
                        </div>
                    `;
                });
            } else {
                html = '<div style="grid-column: 1 / -1; padding: 2rem; text-align: center; color: #64748b;">No scan history available</div>';
            }
            historyList.innerHTML = html;
            sendClientLog('loadHistory_success', { count: data.history ? data.history.length : 0 });
        })
        .catch(error => {
            console.error('Error loading history:', error);
            sendClientLog('loadHistory_error', { message: error.message || String(error) }, 'error');
        });
}

function loadSettings() {
    const form = document.getElementById('github-credentials-form');
    const statusDiv = document.getElementById('settings-status');
    
    if (!form) return;

    // Load current GitHub credentials
    sendClientLog('loadSettings_start');
    fetch('/api/settings/github')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const creds = data.credentials;
                document.getElementById('github_app_id').value = creds.github_app_id || '';
                document.getElementById('github_app_name').value = creds.github_app_name || '';
                // Do NOT populate the private key field for security. Show masked placeholder and keep readonly.
                const secretEl = document.getElementById('github_secret_key');
                if (secretEl) {
                    secretEl.value = '';
                    secretEl.placeholder = 'Private key is stored securely. Click "Replace Key" to provide a new one.';
                    secretEl.setAttribute('readonly', 'true');
                }
                document.getElementById('ngrok_oauth_token').value = creds.ngrok_oauth_token || '';
                sendClientLog('loadSettings_success', { github_app_id: !!creds.github_app_id });
            } else {
                sendClientLog('loadSettings_error', { message: data.message || 'unknown' }, 'error');
            }
        })
        .catch(error => { console.error('Error loading GitHub credentials:', error); sendClientLog('loadSettings_error', { message: error.message || String(error) }, 'error'); });

    // Handle Replace Key workflow
    const replaceBtn = document.getElementById('replace-key-btn');
    const cancelReplaceBtn = document.getElementById('cancel-replace-btn');
    const secretEl = document.getElementById('github_secret_key');
    if (replaceBtn && secretEl) {
        replaceBtn.addEventListener('click', function() {
            secretEl.removeAttribute('readonly');
            secretEl.value = '';
            secretEl.placeholder = 'Paste your complete GitHub RSA Private Key here (-----BEGIN RSA PRIVATE KEY----- ... )';
            replaceBtn.style.display = 'none';
            if (cancelReplaceBtn) cancelReplaceBtn.style.display = 'inline-block';
            secretEl.focus();
            sendClientLog('replace_key_clicked');
        });
    }
    if (cancelReplaceBtn && secretEl) {
        cancelReplaceBtn.addEventListener('click', function() {
            secretEl.setAttribute('readonly', 'true');
            secretEl.value = '';
            secretEl.placeholder = 'Private key is stored securely. Click "Replace Key" to provide a new one.';
            cancelReplaceBtn.style.display = 'none';
            if (replaceBtn) replaceBtn.style.display = 'inline-block';
            sendClientLog('replace_key_cancelled');
        });
    }

    // Handle form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = {
            github_app_id: document.getElementById('github_app_id').value.trim(),
            github_app_name: document.getElementById('github_app_name').value.trim(),
            // Only send the secret key if the user replaced it (non-empty)
            github_secret_key: (document.getElementById('github_secret_key').value || '').trim(),
            ngrok_oauth_token: document.getElementById('ngrok_oauth_token').value.trim()
        };

        // Validate at least one field is filled
        if (!Object.values(formData).some(v => v !== '')) {
            showSettingsStatus('Please fill in at least one field', 'error');
            return;
        }

        // Show loading status
        showSettingsStatus('Saving credentials...', 'loading');
        sendClientLog('saveSettings_start', { github_app_id: formData.github_app_id ? true : false });

        fetch('/api/settings/github', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showSettingsStatus('✓ Credentials saved successfully to .env file', 'success');
                sendClientLog('saveSettings_success', { github_app_id: !!formData.github_app_id });
                // Clear form after successful save
                setTimeout(() => {
                    form.reset();
                    statusDiv.innerHTML = '';
                }, 2000);
            } else {
                showSettingsStatus('✗ ' + (data.message || 'Failed to save credentials'), 'error');
                sendClientLog('saveSettings_error', { message: data.message || 'unknown' }, 'error');
            }
        })
        .catch(error => {
            console.error('Error saving credentials:', error);
            showSettingsStatus('✗ Error saving credentials: ' + error.message, 'error');
            sendClientLog('saveSettings_error', { message: error.message || String(error) }, 'error');
        });
    });
}

function showSettingsStatus(message, type) {
    const statusDiv = document.getElementById('settings-status');
    if (statusDiv) {
        statusDiv.innerHTML = `<div class="status-message status-${type}">${message}</div>`;
        statusDiv.style.display = 'block';
    }
}

// ============ Utility Functions ============
function updateTimestamps() {
    const now = new Date();
    const formattedTime = now.toLocaleString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    const timestampEl = document.getElementById('timestamp');
    const footerTimeEl = document.getElementById('footer-time');

    if (timestampEl) {
        timestampEl.textContent = formattedTime;
    }
    if (footerTimeEl) {
        footerTimeEl.textContent = formattedTime;
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ============ Page Visibility ============
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
        sendClientLog('page_visible');
        updateTimestamps();
    }
});

window.addEventListener('load', function() {
    instrumentFetchLogging();
    sendClientLog('page_load', { url: window.location.pathname, activeTab: localStorage.getItem('activeTab') || 'overview' });
});

window.addEventListener('beforeunload', function() {
    sendClientLog('page_beforeunload', { url: window.location.pathname });
});

// ============ Prevent Scrolling (Extra Safety) ============
document.addEventListener('wheel', function(event) {
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab && !activeTab.querySelector(':hover')) {
        // Allow scroll only on scrollable containers
    }
}, { passive: true });

// ============ Keyboard Navigation ============
document.addEventListener('keydown', function(event) {
    const tabButtons = document.querySelectorAll('.tab-button');
    const activeButton = document.querySelector('.tab-button.active');
    let currentIndex = Array.from(tabButtons).indexOf(activeButton);

    if (event.key === 'ArrowRight') {
        event.preventDefault();
        currentIndex = (currentIndex + 1) % tabButtons.length;
        tabButtons[currentIndex].click();
    } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        currentIndex = (currentIndex - 1 + tabButtons.length) % tabButtons.length;
        tabButtons[currentIndex].click();
    }
});

// ============ Initialize Security Score Animation ============
function animateSecurityScore() {
    const scoreValue = document.getElementById('score-value');
    if (!scoreValue) return;

    const finalScore = parseInt(scoreValue.textContent);
    let currentScore = 0;
    const increment = Math.ceil(finalScore / 30);

    const interval = setInterval(() => {
        currentScore += increment;
        if (currentScore >= finalScore) {
            currentScore = finalScore;
            clearInterval(interval);
        }
        scoreValue.textContent = currentScore;
    }, 30);
}

// Run animation after page loads
window.addEventListener('load', animateSecurityScore);
