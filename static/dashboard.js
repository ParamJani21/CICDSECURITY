/* ============================================
   CICDSECURITY Dashboard JavaScript
   Performance Optimized Edition
   ============================================ */

// ============ CACHING SYSTEM ============
// Cache for API responses with TTL (Time-To-Live in milliseconds)
const CACHE_TTL = 30000; // 30 seconds
const scanFindingsCache = {};

// Debounce function for manual refresh
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

// Get cached data if fresh, otherwise return null
function getCachedFindings(scanId) {
    const cached = scanFindingsCache[scanId];
    if (!cached) return null;
    
    const now = Date.now();
    const age = now - cached.timestamp;
    
    if (age < CACHE_TTL) {
        console.log(`✓ Cache HIT for ${scanId} (${age}ms old)`);
        return cached.data;
    }
    
    console.log(`⚠ Cache STALE for ${scanId} (${age}ms old)`);
    return null;
}

// Store findings in cache
function setCachedFindings(scanId, data) {
    scanFindingsCache[scanId] = {
        data: data,
        timestamp: Date.now()
    };
    console.log(`✓ Cached findings for ${scanId}`);
}

// Persist checkbox state to localStorage
function saveCheckboxState() {
    const checkedIds = Array.from(document.querySelectorAll('.scan-checkbox:checked'))
        .map(cb => cb.getAttribute('data-scan-id'));
    localStorage.setItem('checkedScans', JSON.stringify(checkedIds));
}

// Restore checkbox state from localStorage
function restoreCheckboxState() {
    try {
        const checkedIds = JSON.parse(localStorage.getItem('checkedScans') || '[]');
        checkedIds.forEach(id => {
            const cb = document.querySelector(`.scan-checkbox[data-scan-id="${id}"]`);
            if (cb) cb.checked = true;
        });
    } catch (e) {
        console.warn('Failed to restore checkbox state:', e);
    }
}

// Track expanded scans for this session
let expandedScanIds = new Set();

// ============ Simplified Retry Logic ============
const MAX_RETRIES = 2;
const RETRY_DELAY = 1000; // 1 second

// ============ Tab Management ============
document.addEventListener('DOMContentLoaded', function() {
    sendClientLog('page_domcontentloaded', { url: window.location.pathname, activeTab: localStorage.getItem('activeTab') || 'overview' });
    initializeTabs();
    updateTimestamps();
    loadDynamicContent();
    initializeUserMenu();
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
            loadHistory();
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
                    },
                    barThickness: 35,
                    categoryPercentage: 0.7,
                    barPercentage: 0.95
                }
            });
        })
        .catch(error => {
            console.error('Error loading overview data:', error);
        });
}

// Track selected branches per repo (repoId -> branch name)
const selectedBranches = new Map();

function loadRepositories() {
    const reposList = document.getElementById('repos-list');
    if (!reposList) return;
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
            try { localStorage.setItem('reposCache', JSON.stringify(repos)); } catch (e) { /* ignore */ }
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
        });
}

function renderReposHtml(repos) {
    let html = '';
    repos.forEach(repo => {
        let repoOwner = repo.owner || 'unknown';
        let repoUrl = repo.clone_url || repo.html_url || `https://github.com/${repoOwner}/${repo.name}.git`;
        let repoBranch = repo.branch || repo.default_branch || 'main';
        
        if (!selectedBranches.has(repo.id)) {
            selectedBranches.set(repo.id, repoBranch);
        }
        
        const escapedName = (repo.name || '').replace(/'/g, "\\'");
        const escapedOwner = (repoOwner || '').replace(/'/g, "\\'");
        const escapedUrl = (repoUrl || '').replace(/'/g, "\\'");
        
        html += `
            <div class="table-row">
                <div class="col-repo-name">${repo.name || 'N/A'}</div>
                <div class="col-repo-id">${repo.id || 'N/A'}</div>
                <div class="col-repo-branch">
                    <select id="branch-select-${repo.id}" class="branch-select" onchange="onBranchChange(${repo.id}, this.value)">
                        <option value="${repoBranch}">${repoBranch}</option>
                        <option value="loading" disabled>Loading branches...</option>
                    </select>
                </div>
                <div class="col-repo-action">
                    <button class="scan-btn" onclick="triggerManualScan('${repo.id}', '${escapedName}', '${escapedOwner}', '${escapedUrl}')">Scan</button>
                </div>
            </div>
        `;
    });
    
    setTimeout(() => {
        repos.forEach(repo => {
            fetchAndPopulateBranches(repo);
        });
    }, 100);
    
    return html;
}

function fetchAndPopulateBranches(repo) {
    const selectElement = document.getElementById(`branch-select-${repo.id}`);
    if (!selectElement) return;
    
    const owner = repo.owner || 'unknown';
    const repoName = repo.name || '';
    
    fetch(`/api/branches/${owner}/${repoName}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.branches && data.branches.length > 0) {
                const currentValue = selectElement.value;
                selectElement.innerHTML = '';
                
                data.branches.forEach(branch => {
                    const option = document.createElement('option');
                    option.value = branch;
                    option.textContent = branch;
                    option.selected = (branch === currentValue);
                    selectElement.appendChild(option);
                });
                
                if (!selectedBranches.has(repo.id)) {
                    selectedBranches.set(repo.id, data.branches[0]);
                }
            } else {
                console.warn(`Could not fetch branches for ${owner}/${repoName}`);
            }
        })
        .catch(error => {
            console.error(`Error fetching branches for ${owner}/${repoName}:`, error);
        });
}

function onBranchChange(repoId, selectedBranch) {
    selectedBranches.set(repoId, selectedBranch);
    console.log(`Branch selected for repo ${repoId}: ${selectedBranch}`);
}

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

// ============ Scan Modal Functions ============
let pendingScanRepos = [];
let isScanAllMode = false;

function openScanModal(repos, isAll = false) {
    pendingScanRepos = repos;
    isScanAllMode = isAll;
    const modal = document.getElementById('scan-options-modal');
    if (modal) {
        modal.classList.add('show');
    }
}

function closeScanModal() {
    const modal = document.getElementById('scan-options-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

function getSelectedScanTypes() {
    const scanTypes = [];
    if (document.getElementById('scan-sats')?.checked) scanTypes.push('sats');
    if (document.getElementById('scan-sbom')?.checked) scanTypes.push('sbom');
    if (document.getElementById('scan-secret')?.checked) scanTypes.push('secret');
    return scanTypes;
}

function confirmScan() {
    const scanTypes = getSelectedScanTypes();
    
    if (scanTypes.length === 0) {
        showToast('Please select at least one scan type', 'error');
        return;
    }
    
    closeScanModal();
    
    if (isScanAllMode) {
        startScanAllRepos(scanTypes);
    } else if (pendingScanRepos.length > 0) {
        startSingleRepoScan(pendingScanRepos[0], scanTypes);
    }
    
    pendingScanRepos = [];
    isScanAllMode = false;
}

function startSingleRepoScan(repo, scanTypes) {
    sendClientLog('triggerManualScan_start', { repoId: repo.id, repoName: repo.name, scanTypes });
    
    fetch('/api/repos/scan', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
            repo_id: repo.id,
            repo_name: repo.name,
            repo_owner: repo.owner,
            repo_url: repo.url || `https://github.com/${repo.owner}/${repo.name}.git`,
            repo_branch: repo.branch || 'main',
            scan_types: scanTypes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            sendClientLog('triggerManualScan_success', { repoId: repo.id, repoName: repo.name, repo_path: data.repo_path });
            showToast(`✓ Scan completed for ${repo.owner}/${repo.name}`, 'success');
            updateScanStatus();
            loadHistory();
        } else {
            sendClientLog('triggerManualScan_error', { repoId: repo.id, message: data.message }, 'error');
            showToast(`✗ Scan failed: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error triggering scan:', error);
        sendClientLog('triggerManualScan_error', { repoId: repo.id, message: error.message || String(error) }, 'error');
        showToast(`✗ Error: ${error.message || 'Failed to trigger scan'}`, 'error');
    });
}

function startScanAllRepos(scanTypes) {
    showToast(`Starting scan for all repositories... (${scanTypes.join(', ')})`, 'info');
    
    fetch('/api/repos')
        .then(response => response.json())
        .then(data => {
            const repos = data.repositories || [];
            
            const reposWithBranches = repos.map(repo => ({
                repo_id: repo.id,
                repo_name: repo.name,
                repo_owner: repo.owner,
                repo_url: repo.clone_url || repo.html_url || `https://github.com/${repo.owner}/${repo.name}.git`,
                repo_branch: selectedBranches.get(repo.id) || repo.branch || 'main'
            }));
            
            fetch('/api/repos/scan-all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    scan_types: scanTypes,
                    repos: reposWithBranches
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showToast(`✓ Started scanning ${data.total_repos} repositories`, 'success');
                    loadHistory();
                    updateScanStatus();
                } else {
                    showToast(`✗ Error: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                console.error('Error scanning all repos:', error);
                showToast(`✗ Error: ${error.message}`, 'error');
            });
        })
        .catch(error => {
            console.error('Error fetching repos:', error);
            showToast(`✗ Error fetching repositories: ${error.message}`, 'error');
        });
}

function scanAllRepos() {
    openScanModal([], true);
}

function triggerManualScan(repoId, repoName, repoOwner, repoUrl) {
    const selectedBranch = selectedBranches.get(parseInt(repoId)) || 'main';
    
    const repo = {
        id: repoId,
        name: repoName,
        owner: repoOwner,
        url: repoUrl,
        branch: selectedBranch
    };
    openScanModal([repo], false);
}

// ============ OPTIMIZED HISTORY LOADING - LAZY LOAD FINDINGS ============
function loadHistory() {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;

    sendClientLog('loadHistory_start');
    
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
                    const branch = scan.branch || 'unknown';
                    
                    const critical = severity.CRITICAL || 0;
                    const high = severity.HIGH || 0;
                    const medium = severity.MEDIUM || 0;
                    const low = severity.LOW || 0;
                    const total = scan.total_findings || 0;
                    
                    html += `
                        <div class="history-item" data-scan-id="${scan.scan_id}">
                            <div class="history-row" onclick="toggleScanDetails('${scan.scan_id}')">
                                <div class="col-checkbox">
                                    <input type="checkbox" class="scan-checkbox" data-scan-id="${scan.scan_id}" onclick="event.stopPropagation(); updateDeleteButton(); saveCheckboxState()">
                                </div>
                                <div class="col-time">${formatDate(scan.timestamp)}</div>
                                <div class="col-repo">${scan.repository || 'Unknown'}</div>
                                <div class="col-branch">${branch}</div>
                                <div class="col-total">${total}</div>
                                <div class="col-severity">
                                    <span class="severity-badge critical">${critical}</span>
                                    <span class="severity-badge high">${high}</span>
                                    <span class="severity-badge medium">${medium}</span>
                                    <span class="severity-badge low">${low}</span>
                                </div>
                                 <div class="col-multi">${multiSource > 0 ? multiSource : '-'}</div>
                             </div>
                            <div class="scan-details" id="details-${scan.scan_id}" style="display: none;">
                                <div class="details-content">
                                    <div class="details-header">
                                        <h4>Scan: ${scan.scan_id}</h4>
                                        <span class="repo-name">${scan.repository || 'Unknown'}</span>
                                        <span class="scan-branch" style="margin-left: 1rem;">Branch: <strong>${branch}</strong></span>
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
                                        <div class="findings-loading" style="display: none;">Loading findings...</div>
                                    </div>
                                 </div>
                              </div>
                          </div>`;
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
            
            // Restore checkbox state from localStorage
            restoreCheckboxState();
            
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

// ============ LAZY LOAD FINDINGS - CALLED WHEN USER EXPANDS ============
function loadScanFindings(scanId) {
    const container = document.getElementById('findings-' + scanId);
    if (!container) {
        console.error('❌ Container NOT found for:', 'findings-' + scanId);
        return;
    }
    
    console.log('✓ Loading findings for:', scanId);
    
    // Check cache first
    const cachedData = getCachedFindings(scanId);
    if (cachedData) {
        console.log(`✓ Using cached findings for ${scanId}`);
        renderFindings(scanId, cachedData, container);
        // Fetch fresh data in background
        fetchAndCacheFindings(scanId, container, true);
        return;
    }
    
    // Show loading message
    const loadingDiv = container.querySelector('.findings-loading');
    if (loadingDiv) {
        loadingDiv.style.display = 'block';
    }
    
    fetchAndCacheFindings(scanId, container, false);
}

// Fetch findings with simplified retry logic
function fetchAndCacheFindings(scanId, container, isBackground = false) {
    let attempts = 0;
    
    function retry() {
        attempts++;
        
        fetch('/api/history/' + scanId)
            .then(response => {
                console.log(`⬇️  API Response for ${scanId}: Status ${response.status}`);
                
                if (response.status === 202) {
                    console.log(`⏳ Scan ${scanId} still processing. Scheduling retry...`);
                    if (attempts < MAX_RETRIES) {
                        setTimeout(retry, RETRY_DELAY);
                    } else {
                        if (!isBackground) {
                            container.innerHTML = '<p style="color:#f87171;"><strong>Still loading findings...</strong> Results may still be being processed. Please try again in a few moments.</p>';
                        }
                    }
                    return null;
                }
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                console.log(`✓ Got response for ${scanId}`);
                return response.json();
            })
            .then(data => {
                if (data === null) return;
                
                console.log(`📦 Processing data for ${scanId}:`, Object.keys(data));
                
                // Cache the data
                setCachedFindings(scanId, data);
                
                // Render findings
                renderFindings(scanId, data, container);
            })
            .catch(err => {
                console.error(`❌ Error loading findings for ${scanId}:`, err.message);
                
                if (attempts < MAX_RETRIES) {
                    console.log(`  → Retry attempt ${attempts}/${MAX_RETRIES}...`);
                    setTimeout(retry, RETRY_DELAY);
                } else {
                    if (!isBackground) {
                        container.innerHTML = `<p style="color:#f87171;"><strong>Failed to load findings</strong><br><code style="font-size:12px;">${err.message}</code></p>`;
                    }
                }
            });
    }
    
    retry();
}

// Render findings to container
function renderFindings(scanId, data, container) {
    let findings = [];
    
    if (data.files && data.files.merged) {
        const merged = data.files.merged;
        if (Array.isArray(merged.findings)) {
            findings = merged.findings;
        } else if (merged.findings && typeof merged.findings === 'object') {
            findings = Object.values(merged.findings);
        }
    } else if (data.findings) {
        findings = Array.isArray(data.findings) ? data.findings : Object.values(data.findings);
    }
    
    if (!Array.isArray(findings)) {
        findings = [];
    }
    
    if (!findings || findings.length === 0) {
        console.log(`  📭 No findings (empty)`);
        container.innerHTML = '<h5>All Findings from merged.json</h5><p style="color:#94a3b8;font-style:italic;">No findings found</p>';
        return;
    }
    
    console.log(`  ✅ Rendering ${findings.length} findings`);
    let findingsHtml = '<h5>All Findings from merged.json (' + findings.length + ')</h5>';
    
    findings.forEach((f, idx) => {
        const severityClass = (f.severity || '').toLowerCase();
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
    console.log(`✅ DOM updated successfully for ${scanId}`);
}

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
        
        // Lazy load findings when user expands
        const findingsContainer = document.getElementById('findings-' + scanId);
        // Check if findings have actually been loaded (has finding-item divs, not just header)
        const hasLoadedFindings = findingsContainer && findingsContainer.querySelector('.finding-item');
        if (findingsContainer && !hasLoadedFindings) {
            loadScanFindings(scanId);
        }
    }
}

// ============ DEBOUNCED MANUAL REFRESH ============
const debouncedRefreshHistory = debounce(() => {
    console.log('🔄 Manual refresh triggered (debounced)');
    loadHistory();
}, 2000);

function manualRefreshHistory() {
    sendClientLog('manual_refresh_history');
    debouncedRefreshHistory();
}

function loadSettings() {
    const form = document.getElementById('github-credentials-form');
    const statusDiv = document.getElementById('settings-status');
    
    if (!form) return;

    sendClientLog('loadSettings_start');
    fetch('/api/settings/github')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const creds = data.credentials;
                document.getElementById('github_app_id').value = creds.github_app_id || '';
                document.getElementById('github_app_name').value = creds.github_app_name || '';
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
        .catch(error => { 
            console.error('Error loading GitHub credentials:', error); 
            sendClientLog('loadSettings_error', { message: error.message || String(error) }, 'error'); 
        });

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

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = {
            github_app_id: document.getElementById('github_app_id').value.trim(),
            github_app_name: document.getElementById('github_app_name').value.trim(),
            github_secret_key: (document.getElementById('github_secret_key').value || '').trim(),
            ngrok_oauth_token: document.getElementById('ngrok_oauth_token').value.trim()
        };

        if (!Object.values(formData).some(v => v !== '')) {
            showSettingsStatus('Please fill in at least one field', 'error');
            return;
        }

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

window.addEventListener('load', animateSecurityScore);

// ============ Bulk Delete Functions ============
function syncDeleteButtonState() {
    const checkboxes = document.querySelectorAll('.scan-checkbox');
    const deleteBtn = document.getElementById('delete-scans-btn');
    const selectedCount = document.getElementById('selected-count');
    const selectAllCheckbox = document.getElementById('select-all-scans');
    
    const checkedCheckboxes = document.querySelectorAll('.scan-checkbox:checked');
    const checkedCount = checkedCheckboxes.length;
    const totalCount = checkboxes.length;
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = checkedCount > 0 && checkedCount === totalCount;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < totalCount;
    }
    
    if (deleteBtn && selectedCount) {
        selectedCount.textContent = checkedCount;
        deleteBtn.style.display = checkedCount > 0 ? 'inline-block' : 'none';
    }
}

function updateDeleteButton() {
    syncDeleteButtonState();
}

function toggleSelectAllScans() {
    const selectAllCheckbox = document.getElementById('select-all-scans');
    const checkboxes = document.querySelectorAll('.scan-checkbox');
    
    checkboxes.forEach(cb => {
        cb.checked = selectAllCheckbox.checked;
    });
    
    syncDeleteButtonState();
    saveCheckboxState();
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
            loadHistory();
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

// ============ User Menu Functions ============

function initializeUserMenu() {
    fetch('/api/auth/status')
        .then(response => response.json())
        .then(data => {
            if (data.username) {
                const usernameEl = document.getElementById('current-username');
                if (usernameEl) {
                    usernameEl.textContent = data.username;
                }
            }
        })
        .catch(error => {
            console.log('Could not fetch user info (may not be logged in)');
        });
    
    const userMenuToggle = document.getElementById('user-menu-toggle');
    const userDropdown = document.getElementById('user-dropdown');
    
    if (userMenuToggle && userDropdown) {
        userMenuToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            userDropdown.classList.toggle('active');
            userMenuToggle.classList.toggle('active');
        });
        
        document.addEventListener('click', () => {
            userDropdown.classList.remove('active');
            userMenuToggle.classList.remove('active');
        });
        
        userDropdown.addEventListener('click', (e) => {
            if (e.target.closest('a, button')) {
                userDropdown.classList.remove('active');
                userMenuToggle.classList.remove('active');
            }
        });
    }
}

function logout() {
    sendClientLog('logout_start', {});
    
    fetch('/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (response.ok) {
            sendClientLog('logout_success', {});
            window.location.href = '/auth/login';
        } else {
            sendClientLog('logout_error', { status: response.status }, 'error');
            alert('Logout failed. Please try again.');
        }
    })
    .catch(error => {
        sendClientLog('logout_error', { message: error.message }, 'error');
        console.error('Logout error:', error);
        alert('Logout error: ' + error.message);
    });
}

// ============ FINDINGS FILTER FUNCTIONS ============

function applyFilters() {
    const severityFilters = Array.from(document.querySelectorAll('.severity-filter:checked')).map(cb => cb.value);
    const toolFilters = Array.from(document.querySelectorAll('.tool-filter:checked')).map(cb => cb.value);
    const categoryFilters = Array.from(document.querySelectorAll('.category-filter:checked')).map(cb => cb.value);
    const searchQuery = document.getElementById('findingsSearch')?.value || '';
    
    const params = new URLSearchParams();
    if (severityFilters.length) params.set('severity', severityFilters.join(','));
    if (toolFilters.length) params.set('tool', toolFilters.join(','));
    if (categoryFilters.length) params.set('category', categoryFilters.join(','));
    if (searchQuery) params.set('search', searchQuery);
    
    const historyList = document.getElementById('history-list');
    if (historyList) historyList.innerHTML = '<div style="padding: 2rem; text-align: center; color: #64748b;">Filtering...</div>';
    
    // If no filters, just reload all history
    if (!severityFilters.length && !toolFilters.length && !categoryFilters.length && !searchQuery) {
        loadHistory();
        return;
    }
    
    fetch('/api/history/filter?' + params.toString())
        .then(response => response.json())
        .then(data => {
            if (data.history && data.history.length > 0) {
                renderFilteredHistory(data.history);
            } else {
                historyList.innerHTML = '<div style="padding: 2rem; text-align: center; color: #64748b;">No findings match your filters</div>';
            }
        })
        .catch(error => {
            console.error('Filter error:', error);
            loadHistory();
        });
}

function clearFilters() {
    document.querySelectorAll('.severity-filter, .tool-filter, .category-filter').forEach(cb => cb.checked = false);
    if (document.getElementById('findingsSearch')) {
        document.getElementById('findingsSearch').value = '';
    }
    loadHistory();
}

function renderFilteredHistory(filteredHistory) {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;
    
    if (!filteredHistory || filteredHistory.length === 0) {
        historyList.innerHTML = '<div class="empty-state">No findings match your filters</div>';
        return;
    }
    
    // Save current checkbox state
    const checkedIds = Array.from(document.querySelectorAll('.scan-checkbox:checked')).map(cb => cb.getAttribute('data-scan-id'));
    
    let html = '';
    filteredHistory.forEach(scan => {
        html += renderHistoryItem(scan);
    });
    historyList.innerHTML = html;
    
    // Restore checkbox state
    checkedIds.forEach(id => {
        const cb = document.querySelector(`.scan-checkbox[data-scan-id="${id}"]`);
        if (cb) cb.checked = true;
    });
    updateDeleteButton();
}

function renderHistoryItem(scan) {
    // Get severity counts from findings
    const findings = scan.findings || [];
    const severity = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    const sources = new Set();
    let multiSource = 0;
    
    findings.forEach(f => {
        const sev = f.severity || 'LOW';
        if (severity[sev] !== undefined) severity[sev]++;
        (f.sources || []).forEach(s => sources.add(s));
    });
    
    const total = findings.length;
    const branch = scan.repo_branch || 'main';
    const critical = severity.CRITICAL;
    const high = severity.HIGH;
    const medium = severity.MEDIUM;
    const low = severity.LOW;
    
    let html = '';
    html += `
            <div class="history-row" onclick="toggleScanDetails('${scan.scan_id}')">
                <div class="col-checkbox">
                    <input type="checkbox" class="scan-checkbox" data-scan-id="${scan.scan_id}" onclick="event.stopPropagation(); updateDeleteButton(); saveCheckboxState()">
                </div>
                <div class="col-time">${formatDate(scan.timestamp)}</div>
                <div class="col-repo">${scan.repository || 'Unknown'}</div>
                <div class="col-branch">${branch}</div>
                <div class="col-total">${total}</div>
                <div class="col-severity">
                    <span class="severity-badge critical">${critical}</span>
                    <span class="severity-badge high">${high}</span>
                    <span class="severity-badge medium">${medium}</span>
                    <span class="severity-badge low">${low}</span>
                </div>
                <div class="col-multi">${multiSource > 0 ? multiSource : '-'}</div>
            </div>
            <div class="scan-details" id="details-${scan.scan_id}" style="display: none;">
                <div class="details-content">
                    <div class="details-header">
                        <h4>Scan: ${scan.scan_id}</h4>
                        <span class="repo-name">${scan.repository || 'Unknown'}</span>
                        <span class="scan-branch" style="margin-left: 1rem;">Branch: <strong>${branch}</strong></span>
                    </div>
                    <div class="findings-list" id="findings-${scan.scan_id}">
                        <h5>All Findings from merged.json (${total})</h5>
                        <div class="findings-loading" style="display: none;">Loading findings...</div>
                    </div>
                </div>
            </div>
        </div>
    `;
    return html;
}

// ============ USER MANAGEMENT FUNCTIONS ============

function loadUsers() {
    fetch('/api/users', { credentials: 'include' })
    .then(response => {
        if (response.status === 403) {
            alert('Access denied. Admin only.');
            return;
        }
        return response.json();
    })
    .then(data => {
        if (data && data.users) {
            displayUsers(data.users);
        }
    })
    .catch(error => {
        console.error('Error loading users:', error);
    });
}

function displayUsers(users) {
    const tbody = document.getElementById('users-list');
    if (!tbody) return;
    
    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 20px; color: #64748b;">No users found</td></tr>';
        return;
    }
    
    tbody.innerHTML = users.map(user => `
        <tr>
            <td>${user.username}</td>
            <td>${user.email || '-'}</td>
            <td>${user.full_name || '-'}</td>
            <td>${user.department || '-'}</td>
            <td><span class="user-role-badge ${user.role}">${user.role}</span></td>
            <td><span class="user-status-badge ${user.is_active ? 'active' : 'disabled'}">${user.is_active ? 'Active' : 'Disabled'}</span></td>
            <td>${user.created_at ? user.created_at.split('T')[0] : '-'}</td>
            <td>${user.last_login ? user.last_login.split('T')[0] : 'Never'}</td>
            <td class="user-actions">
                <button class="edit-btn" onclick="editUser(${user.id})">Edit</button>
                <button class="disable-btn" onclick="deleteUser(${user.id})">${user.is_active ? 'Disable' : 'Enable'}</button>
            </td>
        </tr>
    `).join('');
}

function showCreateUserModal() {
    document.getElementById('user-modal-title').textContent = 'Create User';
    document.getElementById('user-id').value = '';
    document.getElementById('user-form').reset();
    document.getElementById('password-group').style.display = 'block';
    document.getElementById('is-active-group').style.display = 'none';
    document.getElementById('user-modal').style.display = 'block';
}

function closeUserModal() {
    document.getElementById('user-modal').style.display = 'none';
}

function editUser(userId) {
    fetch('/api/users', { credentials: 'include' })
    .then(response => response.json())
    .then(data => {
        const user = data.users.find(u => u.id === userId);
        if (!user) {
            alert('User not found');
            return;
        }
        
        document.getElementById('user-modal-title').textContent = 'Edit User';
        document.getElementById('user-id').value = user.id;
        document.getElementById('user-username').value = user.username;
        document.getElementById('user-email').value = user.email || '';
        document.getElementById('user-fullname').value = user.full_name || '';
        document.getElementById('user-department').value = user.department || '';
        document.getElementById('user-role').value = user.role;
        document.getElementById('user-is-active').checked = user.is_active;
        
        document.getElementById('password-group').style.display = 'none';
        document.getElementById('is-active-group').style.display = 'block';
        document.getElementById('user-modal').style.display = 'block';
    });
}

function deleteUser(userId) {
    if (!confirm('Are you sure you want to disable this user?')) return;
    
    fetch('/api/users/' + userId, {
        method: 'DELETE',
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message || data.status);
        loadUsers();
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to disable user');
    });
}

document.getElementById('user-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const userId = document.getElementById('user-id').value;
    const isEdit = !!userId;
    
    const userData = {
        username: document.getElementById('user-username').value,
        email: document.getElementById('user-email').value,
        full_name: document.getElementById('user-fullname').value,
        department: document.getElementById('user-department').value,
        role: document.getElementById('user-role').value
    };
    
    if (!isEdit) {
        userData.password = document.getElementById('user-password').value;
    } else {
        userData.is_active = document.getElementById('user-is-active').checked;
    }
    
    const url = isEdit ? '/api/users/' + userId : '/api/users';
    const method = isEdit ? 'PUT' : 'POST';
    
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(userData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(data.message);
            closeUserModal();
            loadUsers();
        } else {
            alert(data.message || 'Error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to save user');
    });
});

// Load users when users tab is shown
document.querySelector('[data-tab="users"]').addEventListener('click', function() {
    loadUsers();
});

// ============ FILTER PANEL TOGGLE ============
function toggleFilterPanel() {
    const panel = document.getElementById('filter-panel');
    panel.classList.toggle('active');
}

// ============ EXPORT REPORT MODAL ============
function exportReport() {
    document.getElementById('export-modal').classList.add('active');
}
function closeExportModal() {
    document.getElementById('export-modal').classList.remove('active');
}
function confirmExport() {
    const params = new URLSearchParams();
    
    // Date filter (000 to 111 - bit 0)
    const dateFrom = document.getElementById('export-date-from').value;
    const dateTo = document.getElementById('export-date-to').value;
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    
    // Severity filter (bit 1)
    const severity = [];
    if (document.getElementById('export-critical').checked) severity.push('CRITICAL');
    if (document.getElementById('export-high').checked) severity.push('HIGH');
    if (document.getElementById('export-medium').checked) severity.push('MEDIUM');
    if (document.getElementById('export-low').checked) severity.push('LOW');
    if (severity.length) params.set('severity', severity.join(','));
    
    // Tool filter (bit 2)
    const tool = [];
    if (document.getElementById('export-opengrep').checked) tool.push('opengrep');
    if (document.getElementById('export-truffle').checked) tool.push('truffle');
    if (document.getElementById('export-trivy').checked) tool.push('trivy');
    if (tool.length) params.set('tool', tool.join(','));
    
    closeExportModal();
    window.location.href = '/api/export-report' + (params.toString() ? '?' + params.toString() : '');
}
