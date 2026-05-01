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
    sendClientLog('loadDynamicContent_complete');
}

function loadTabContent(tabName) {
    sendClientLog('loadTabContent', { tabName });
    switch(tabName) {
        case 'repos':
            break;
        case 'history':
            loadHistory(); // Always reload to show latest scans
            break;
        case 'settings':
            loadSettings();
            break;
        default:
            break;
    }
}

function updateScanStatus() {
    fetch('/api/overview')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('scan-status-container');
            if (!container) return;
            
            const activeScans = data.active_scans_list || [];
            
            if (activeScans.length > 0) {
                const names = activeScans.map(s => s.owner ? `${s.owner}/${s.repo_name}` : s.repo_name).join(', ');
                container.innerHTML = `<span style="color: #22c55e;">● Scanning: ${names}</span>`;
            } else {
                container.innerHTML = `<span style="color: #64748b;">✓ Ready to scan</span>`;
            }
        })
        .catch(() => {});
}

// Update scan status every 3 seconds
setInterval(updateScanStatus, 3000);
updateScanStatus();

function renderScansChart() {
    const ctx = document.getElementById('scansChart');
    if (!ctx) return;

    fetch('/api/overview')
        .then(response => response.json())
        .then(data => {
            const scans = data.recent_scans || [];
            if (scans.length === 0) {
                ctx.parentElement.innerHTML = '<div style="color: #64748b; text-align: center; padding: 2rem; display: flex; flex-direction: column; justify-content: center; height: 200px;"><p>📊 No scans found yet</p><p style="font-size: 0.85rem; margin-top: 0.5rem;">Run a scan to see results</p></div>';
                return;
            }

            const labels = scans.map(s => {
                const repo = s.repository || 'Unknown';
                return repo.length > 15 ? repo.substring(0, 12) + '...' : repo;
            }).reverse();

            const criticalData = scans.map(s => s.severity.CRITICAL || 0).reverse();
            const highData = scans.map(s => s.severity.HIGH || 0).reverse();
            const mediumData = scans.map(s => s.severity.MEDIUM || 0).reverse();
            const lowData = scans.map(s => s.severity.LOW || 0).reverse();

            if (window.scansChartInstance) {
                window.scansChartInstance.destroy();
            }

            window.scansChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Critical',
                            data: criticalData,
                            backgroundColor: '#dc2626',
                            borderRadius: 4
                        },
                        {
                            label: 'High',
                            data: highData,
                            backgroundColor: '#ea580c',
                            borderRadius: 4
                        },
                        {
                            label: 'Medium',
                            data: mediumData,
                            backgroundColor: '#ca8a04',
                            borderRadius: 4
                        },
                        {
                            label: 'Low',
                            data: lowData,
                            backgroundColor: '#16a34a',
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                color: '#94a3b8',
                                font: { size: 11 }
                            }
                        },
                        title: {
                            display: true,
                            text: 'Recent Scan Results (Last 10)',
                            color: '#f1f5f9',
                            font: { size: 14 }
                        }
                    },
                    scales: {
                        x: {
                            stacked: true,
                            ticks: { color: '#94a3b8', font: { size: 10 } },
                            grid: { color: '#334155' }
                        },
                        y: {
                            stacked: true,
                            ticks: { color: '#94a3b8', font: { size: 10 } },
                            grid: { color: '#334155' },
                            beginAtZero: true
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error loading overview data:', error);
        });
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
            showToast(`✓ Scan started for ${repoOwner}/${repoName}`, 'success');
            updateScanStatus();
            // Refresh history immediately after scan triggers
            loadHistory();
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
    if (!historyList) return;

    sendClientLog('loadHistory_start');
    
    // Reset delete button on refresh (checkboxes will be cleared)
    syncDeleteButtonState();

    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            let html = '';
            if (data.history && data.history.length > 0) {
                data.history.forEach(scan => {
                    const severity = scan.severity || {};
                    const category = scan.category || {};
                    const multiSource = scan.multi_source || 0;
                    
                    const critical = severity.CRITICAL || 0;
                    const high = severity.HIGH || 0;
                    const medium = severity.MEDIUM || 0;
                    const low = severity.LOW || 0;
                    const total = scan.total_findings || 0;
                    
                    html += `
                        <div class="history-item" data-scan-id="${scan.scan_id}">
                            <div class="history-row" onclick="toggleScanDetails('${scan.scan_id}')">
                                <div class="col-checkbox">
                                    <input type="checkbox" class="scan-checkbox" data-scan-id="${scan.scan_id}" onclick="event.stopPropagation(); updateDeleteButton()">
                                </div>
                                <div class="col-time">${formatDate(scan.timestamp)}</div>
                                <div class="col-repo">${scan.repository || 'Unknown'}</div>
                                <div class="col-total">${total}</div>
                                <div class="col-severity">
                                    <span class="severity-badge critical">${critical}</span>
                                    <span class="severity-badge high">${high}</span>
                                    <span class="severity-badge medium">${medium}</span>
                                    <span class="severity-badge low">${low}</span>
                                </div>
                                <div class="col-multi">${multiSource > 0 ? multiSource : '-'}</div>
                                <div class="col-action">
                                    <button class="view-detail-btn" onclick="event.stopPropagation(); toggleScanDetails('${scan.scan_id}')" title="View Details">▶</button>
                                </div>
                            </div>
                            <div class="scan-details" id="details-${scan.scan_id}" style="display: none;">
                                <div class="details-content">
                                    <div class="details-header">
                                        <h4>Scan: ${scan.scan_id}</h4>
                                        <span class="repo-name">${scan.repository || 'Unknown'}</span>
                                    </div>
                                    <div class="details-grid">
                                        <div class="detail-card">
                                            <h5>Severity</h5>
                                            <div class="detail-stat"><span class="stat-label">CRITICAL:</span><span class="stat-value critical">${critical}</span></div>
                                            <div class="detail-stat"><span class="stat-label">HIGH:</span><span class="stat-value high">${high}</span></div>
                                            <div class="detail-stat"><span class="stat-label">MEDIUM:</span><span class="stat-value medium">${medium}</span></div>
                                            <div class="detail-stat"><span class="stat-label">LOW:</span><span class="stat-value low">${low}</span></div>
                                        </div>
                                        <div class="detail-card">
                                            <h5>Category</h5>
                                            <div class="detail-stat"><span class="stat-label">Secrets:</span><span class="stat-value">${category.secrets || 0}</span></div>
                                            <div class="detail-stat"><span class="stat-label">Code:</span><span class="stat-value">${category.code || 0}</span></div>
                                        </div>
                                        <div class="detail-card">
                                            <h5>Multi-Source</h5>
                                            <div class="detail-stat highlight"><span class="stat-value">${multiSource}</span></div>
                                        </div>
                                    </div>
                                    <div class="details-files">
                                        <div class="file-badges">
                                            <span class="file-badge">merged.json</span>
                                            <span class="file-badge">opengrep.json</span>
                                            <span class="file-badge">truffle.json</span>
                                            <span class="file-badge">trivy.json</span>
                                        </div>
                                    </div>
                                    <div class="findings-list" id="findings-${scan.scan_id}">
                                        <h5>All Findings from merged.json (${total})</h5>
                                        <div class="findings-loading">Loading findings...</div>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                    
                    // Load findings via API
                    setTimeout(() => loadScanFindings(scan.scan_id), 100);
                });
            } else {
                html = '<div style="grid-column: 1 / -1; padding: 2rem; text-align: center; color: #64748b;">No scans found. Trigger a scan to see results here.</div>';
            }
            historyList.innerHTML = html;
            
            // Restore expanded state
            expandedScanIds.forEach(scanId => {
                const details = document.getElementById('details-' + scanId);
                const btn = document.querySelector(`[data-scan-id="${scanId}"] .view-detail-btn`);
                if (details) {
                    details.style.display = 'block';
                    if (btn) btn.innerHTML = '▼';
                } else {
                    expandedScanIds.delete(scanId);
                }
            });
            
            // Update stats
            document.getElementById('total-scans').textContent = data.stats.total_scans || 0;
            document.getElementById('total-findings').textContent = data.stats.total_findings || 0;
            document.getElementById('critical-issues').textContent = data.stats.critical_issues || 0;
            
            sendClientLog('loadHistory_success', { count: data.history ? data.history.length : 0 });
        })
        .catch(error => {
            console.error('Error loading history:', error);
            sendClientLog('loadHistory_error', { message: error.message || String(error) }, 'error');
        });
}

function loadScanFindings(scanId) {
    const container = document.getElementById('findings-' + scanId);
    if (!container) return;
    
    fetch('/api/history/' + scanId)
        .then(response => response.json())
        .then(data => {
            // Handle both response formats
            let findings = [];
            if (data.files && data.files.merged && data.files.merged.findings) {
                findings = data.files.merged.findings;
            } else if (data.findings) {
                findings = data.findings;
            }
            
            if (!findings || findings.length === 0) {
                container.innerHTML = '<h5>All Findings from merged.json</h5><p style="color:#94a3b8;font-style:italic;">No findings found</p>';
                return;
            }
            
            let findingsHtml = '<h5>All Findings from merged.json (' + findings.length + ')</h5>';
            
            findings.forEach((f, idx) => {
                const severityClass = (f.severity || '').toLowerCase();
                const sources = (f.sources || []).join(', ');
                const cwe = (f.cwe || []).join(', ');
                
                findingsHtml += `
                    <div class="finding-item">
                        <div class="finding-header">
                            <span class="finding-file">${f.file}:${f.line}</span>
                            <span class="finding-type">${f.type || 'unknown'}</span>
                            <span class="severity-badge ${severityClass}">${f.severity || 'INFO'}</span>
                        </div>
                        <div class="finding-title">${f.title || 'Untitled'}</div>
                        ${f.message ? `<div class="finding-message">${f.message.substring(0, 200)}</div>` : ''}
                        ${cwe ? `<div class="finding-cwe">CWE: ${cwe}</div>` : ''}
                        <div class="source-badges">
                            ${(f.sources || []).map(s => `<span class="source-badge">${s}</span>`).join('')}
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = findingsHtml;
        })
        .catch(err => {
            console.error('Error loading findings:', err);
            container.innerHTML = '<p style="color:#94a3b8;">Error loading findings</p>';
        });
}

let expandedScanIds = new Set();

function toggleScanDetails(scanId) {
    const details = document.getElementById('details-' + scanId);
    const btn = document.querySelector(`[data-scan-id="${scanId}"] .view-detail-btn`);
    
    if (expandedScanIds.has(scanId)) {
        expandedScanIds.delete(scanId);
        details.style.display = 'none';
        if (btn) btn.innerHTML = '▶';
    } else {
        expandedScanIds.add(scanId);
        details.style.display = 'block';
        if (btn) btn.innerHTML = '▼';
    }
}

// Auto-refresh history every 5 seconds when tab is active (but skip if details are expanded)
setInterval(() => {
    const historyTab = document.getElementById('history-tab');
    if (historyTab && historyTab.classList.contains('active')) {
        if (expandedScanIds.size === 0) {
            // Save checked state before refresh
            const checkedIds = Array.from(document.querySelectorAll('.scan-checkbox:checked'))
                .map(cb => cb.getAttribute('data-scan-id'));
            
            // Call loadHistory and restore after it completes
            loadHistoryWithRestore(checkedIds);
        }
    }
}, 5000);

function loadHistoryWithRestore(checkedIds) {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;

    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            let html = '';
            if (data.history && data.history.length > 0) {
                data.history.forEach(scan => {
                    const severity = scan.severity || {};
                    const category = scan.category || {};
                    const multiSource = scan.multi_source || 0;
                    
                    const critical = severity.CRITICAL || 0;
                    const high = severity.HIGH || 0;
                    const medium = severity.MEDIUM || 0;
                    const low = severity.LOW || 0;
                    const total = scan.total_findings || 0;
                    
                    html += `
                        <div class="history-item" data-scan-id="${scan.scan_id}">
                            <div class="history-row" onclick="toggleScanDetails('${scan.scan_id}')">
                                <div class="col-checkbox">
                                    <input type="checkbox" class="scan-checkbox" data-scan-id="${scan.scan_id}" onclick="event.stopPropagation(); updateDeleteButton()">
                                </div>
                                <div class="col-time">${formatDate(scan.timestamp)}</div>
                                <div class="col-repo">${scan.repository || 'Unknown'}</div>
                                <div class="col-total">${total}</div>
                                <div class="col-severity">
                                    <span class="severity-badge critical">${critical}</span>
                                    <span class="severity-badge high">${high}</span>
                                    <span class="severity-badge medium">${medium}</span>
                                    <span class="severity-badge low">${low}</span>
                                </div>
                                <div class="col-multi">${multiSource > 0 ? multiSource : '-'}</div>
                                <div class="col-action">
                                    <button class="view-detail-btn" onclick="event.stopPropagation(); toggleScanDetails('${scan.scan_id}')" title="View Details">▶</button>
                                </div>
                            </div>
                            <div class="scan-details" id="details-${scan.scan_id}" style="display: none;">
                                <div class="details-content">
                                    <div class="details-header">
                                        <h4>Scan: ${scan.scan_id}</h4>
                                        <span class="repo-name">${scan.repository || 'Unknown'}</span>
                                    </div>
                                    <div class="details-grid">
                                        <div class="detail-card">
                                            <h5>Severity</h5>
                                            <div class="detail-stat"><span class="stat-label">CRITICAL:</span><span class="stat-value critical">${critical}</span></div>
                                            <div class="detail-stat"><span class="stat-label">HIGH:</span><span class="stat-value high">${high}</span></div>
                                            <div class="detail-stat"><span class="stat-label">MEDIUM:</span><span class="stat-value medium">${medium}</span></div>
                                            <div class="detail-stat"><span class="stat-label">LOW:</span><span class="stat-value low">${low}</span></div>
                                        </div>
                                        <div class="detail-card">
                                            <h5>Category</h5>
                                            <div class="detail-stat"><span class="stat-label">Secrets:</span><span class="stat-value">${category.secrets || 0}</span></div>
                                            <div class="detail-stat"><span class="stat-label">Code:</span><span class="stat-value">${category.code || 0}</span></div>
                                        </div>
                                        <div class="detail-card">
                                            <h5>Multi-Source</h5>
                                            <div class="detail-stat highlight"><span class="stat-value">${multiSource}</span></div>
                                        </div>
                                    </div>
                                    <div class="details-files">
                                        <div class="file-badges">
                                            <span class="file-badge">merged.json</span>
                                            <span class="file-badge">opengrep.json</span>
                                            <span class="file-badge">truffle.json</span>
                                            <span class="file-badge">trivy.json</span>
                                        </div>
                                    </div>
                                    <div class="findings-list" id="findings-${scan.scan_id}">
                                        <h5>All Findings from merged.json (${total})</h5>
                                        <div class="findings-loading">Loading findings...</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });
            } else {
                html = '<p style="color: #64748b; text-align: center; padding: 2rem;">No scan history yet. Start scanning repositories to see results here.</p>';
            }
            
            historyList.innerHTML = html;
            
            // Restore checked state AFTER HTML is inserted
            if (checkedIds && checkedIds.length > 0) {
                checkedIds.forEach(id => {
                    const cb = document.querySelector(`.scan-checkbox[data-scan-id="${id}"]`);
                    if (cb) cb.checked = true;
                });
                syncDeleteButtonState();
            }
            
            // Update total scans count
            const totalScansEl = document.getElementById('total-scans');
            if (totalScansEl && data.stats) {
                totalScansEl.textContent = data.stats.total_scans || 0;
            }
        })
        .catch(error => {
            console.error('Error loading history:', error);
            historyList.innerHTML = '<p style="color: #64748b; text-align: center; padding: 2rem;">Error loading history</p>';
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

    if (timestampEl) {
        timestampEl.textContent = formattedTime;
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

// ============ Bulk Delete Functions ============
function syncDeleteButtonState() {
    const checkboxes = document.querySelectorAll('.scan-checkbox:checked');
    const deleteBtn = document.getElementById('delete-scans-btn');
    const selectedCount = document.getElementById('selected-count');
    
    if (deleteBtn && selectedCount) {
        const count = checkboxes.length;
        selectedCount.textContent = count;
        deleteBtn.style.display = count > 0 ? 'inline-block' : 'none';
    }
}

function updateDeleteButton() {
    syncDeleteButtonState();
}

function exportReport() {
    sendClientLog('export_report_start', {});
    
    window.location.href = '/api/export-report';
}

function deleteSelectedScans() {
    const checkboxes = document.querySelectorAll('.scan-checkbox:checked');
    const scanIds = Array.from(checkboxes).map(cb => cb.getAttribute('data-scan-id'));
    
    if (scanIds.length === 0) {
        return;
    }
    
    if (!confirm(`Are you sure you want to delete ${scanIds.length} scan(s)? This will remove all data from logs.`)) {
        return;
    }
    
    sendClientLog('delete_scans_start', { count: scanIds.length, scanIds: scanIds });
    
    fetch('/api/history/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_ids: scanIds })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            sendClientLog('delete_scans_success', { count: scanIds.length });
            // Refresh history
            loadHistory();
            // Reset delete button
            const deleteBtn = document.getElementById('delete-scans-btn');
            if (deleteBtn) deleteBtn.style.display = 'none';
        } else {
            sendClientLog('delete_scans_error', { message: data.message || 'Unknown error' }, 'error');
            alert('Failed to delete scans: ' + (data.message || 'Unknown error'));
        }
    })
    .catch(error => {
        sendClientLog('delete_scans_error', { message: error.message || String(error) }, 'error');
        console.error('Error deleting scans:', error);
        alert('Error deleting scans: ' + error.message);
    });
}
