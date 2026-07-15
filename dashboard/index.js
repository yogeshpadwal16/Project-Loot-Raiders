// Dashboard API Controller for Loot Raiders
const API_BASE = window.location.protocol === 'file:' 
    ? 'http://127.0.0.1:5555' 
    : window.location.origin;

// Detect if running statically on GitHub Pages or locally without server
const IS_STATIC_MODE = window.location.hostname.endsWith('github.io') || window.location.hostname.endsWith('githubusercontent.com');

// Helper to check if logged in as administrator
function isAuthorized() {
    if (IS_STATIC_MODE) return false;
    return localStorage.getItem('admin_token') === 'admin_session_key_vihan_143';
}

// State management
let currentSelectors = {};
let selectedPlatformKey = 'amazon_master_lightning_deals'; // default tab
let currentDeals = [];
let clicksChartInstance = null;
let lastClicksData = [];

// DOM elements
const statusBadge = document.getElementById('status-badge');
const toggleBtn = document.getElementById('toggle-btn');
const scanBtn = document.getElementById('scan-btn');
const statState = document.getElementById('stat-state');
const statScans = document.getElementById('stat-scans');
const statBroadcasted = document.getElementById('stat-broadcasted');
const statUptime = document.getElementById('stat-uptime');
const dealsContainer = document.getElementById('deals-container');
const dealsCount = document.getElementById('deals-count');
const consoleLogs = document.getElementById('console-logs');
const selectorForm = document.getElementById('selector-form');
const saveSelectorsBtn = document.getElementById('save-selectors-btn');
const tabButtons = document.querySelectorAll('.tab-btn');
const toastEl = document.getElementById('toast');

// Map visual tab platforms to selector keys
const platformKeyMap = {
    'amazon_lightning': 'amazon_master_lightning_deals',
    'amazon_search': 'amazon_sitewide_search_deals',
    'flipkart_offers': 'flipkart_sitewide_offers',
    'flipkart_clearance': 'flipkart_clearance_master_feed'
};

// ==========================================
// UTILITY FUNCTIONS
// ==========================================
function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return '00:00:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return [hrs, mins, secs].map(v => v < 10 ? '0' + v : v).join(':');
}

function showToast(message, type = 'success') {
    toastEl.className = `toast show ${type}`;
    toastEl.innerHTML = `<i class="fa-solid ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i> ${message}`;
    setTimeout(() => {
        toastEl.classList.remove('show');
    }, 4000);
}

// ==========================================
// CORE API CALLS
// ==========================================
async function fetchStatus() {
    if (IS_STATIC_MODE) {
        statusBadge.className = 'status-badge running';
        statusBadge.querySelector('.status-text').textContent = 'SERVERLESS CLOUD';
        statState.textContent = 'SERVERLESS';
        statState.style.color = 'var(--accent-green)';
        statScans.textContent = 'AUTO CRON';
        statUptime.textContent = '24/7 ONLINE';
        
        // Hide control elements and logs
        const toggleB = document.getElementById('toggle-btn');
        if (toggleB) toggleB.style.display = 'none';
        const scanB = document.getElementById('scan-btn');
        if (scanB) scanB.style.display = 'none';
        const logoutB = document.getElementById('logout-btn');
        if (logoutB) logoutB.style.display = 'none';
        const identityB = document.querySelector('.user-identity-box');
        if (identityB) identityB.style.display = 'none';
        
        const selCard = document.querySelector('.selector-card');
        if (selCard) selCard.style.display = 'none';
        const logCard = document.querySelector('.console-card');
        if (logCard) logCard.style.display = 'none';
        const clickCard = document.querySelector('.clicks-card');
        if (clickCard) clickCard.style.display = 'none';
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        if (!response.ok) throw new Error('Status sync failure');
        const data = await response.json();
        updateStatusUI(data);
    } catch (err) {
        console.error('API Error (Status):', err);
        statusBadge.className = 'status-badge';
        statusBadge.querySelector('.status-text').textContent = 'OFFLINE';
    }
}

async function fetchDeals() {
    try {
        const response = await fetch(IS_STATIC_MODE ? './deals_history.json' : `${API_BASE}/api/deals`);
        if (!response.ok) throw new Error('Deals sync failure');
        const data = await response.json();
        currentDeals = data;
        applyFiltersAndRender();
    } catch (err) {
        console.error('API Error (Deals):', err);
    }
}

function applyFiltersAndRender() {
    const searchVal = document.getElementById('feed-search').value.toLowerCase().trim();
    const platformFilter = document.getElementById('feed-filter-platform').value;
    const sortVal = document.getElementById('feed-sort').value;
    
    let filtered = [...currentDeals];
    
    // 1. Search filter
    if (searchVal) {
        filtered = filtered.filter(deal => 
            (deal.title || '').toLowerCase().includes(searchVal)
        );
    }
    
    // 2. Platform filter
    if (platformFilter === 'amazon') {
        filtered = filtered.filter(deal => (deal.platform || '').toLowerCase().includes('amazon'));
    } else if (platformFilter === 'flipkart') {
        filtered = filtered.filter(deal => (deal.platform || '').toLowerCase().includes('flipkart'));
    } else if (platformFilter === 'verified_low') {
        filtered = filtered.filter(deal => deal.is_verified_low);
    }
    
    // 3. Sorting
    if (sortVal === 'newest') {
        filtered.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    } else if (sortVal === 'discount') {
        filtered.sort((a, b) => (parseFloat(b.discount) || 0) - (parseFloat(a.discount) || 0));
    } else if (sortVal === 'price_asc') {
        filtered.sort((a, b) => (parseInt(a.price) || 0) - (parseInt(b.price) || 0));
    } else if (sortVal === 'price_desc') {
        filtered.sort((a, b) => (parseInt(b.price) || 0) - (parseInt(a.price) || 0));
    }
    
    updateDealsUI(filtered);
}

async function fetchLogs() {
    try {
        const response = await fetch(`${API_BASE}/api/logs`);
        if (!response.ok) throw new Error('Logs sync failure');
        const data = await response.json();
        updateLogsUI(data);
    } catch (err) {
        console.error('API Error (Logs):', err);
    }
}

async function fetchSelectors() {
    try {
        const response = await fetch(`${API_BASE}/api/selectors`);
        if (!response.ok) throw new Error('Selectors sync failure');
        currentSelectors = await response.json();
        loadPlatformSelectorsToForm(selectedPlatformKey);
    } catch (err) {
        console.error('API Error (Selectors):', err);
        showToast('Failed to load scraper selectors configuration.', 'error');
    }
}

// ==========================================
// UI RENDERERS
// ==========================================
function updateStatusUI(status) {
    statScans.textContent = status.scans_completed;
    statUptime.textContent = formatTime(status.uptime);
    
    if (status.is_running) {
        statusBadge.className = 'status-badge running';
        statusBadge.querySelector('.status-text').textContent = 'ACTIVE';
        statState.textContent = 'RUNNING';
        statState.style.color = 'var(--accent-green)';
        toggleBtn.innerHTML = '<i class="fa-solid fa-pause"></i> <span>Pause Scan</span>';
        toggleBtn.className = 'btn btn-secondary';
    } else {
        statusBadge.className = 'status-badge paused';
        statusBadge.querySelector('.status-text').textContent = 'PAUSED';
        statState.textContent = 'PAUSED';
        statState.style.color = 'var(--accent-orange)';
        toggleBtn.innerHTML = '<i class="fa-solid fa-play"></i> <span>Resume Scan</span>';
        toggleBtn.className = 'btn btn-primary';
    }
}

function updateDealsUI(deals) {
    dealsCount.textContent = `${deals.length} Deals`;
    
    if (deals.length === 0) {
        dealsContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-ghost"></i>
                <p>No deals found in this session yet.</p>
            </div>`;
        statBroadcasted.textContent = '0';
        return;
    }
    
    statBroadcasted.textContent = deals.length;
    
    let html = '';
    deals.forEach(deal => {
        const platformStr = deal.platform || '';
        const isAmazon = platformStr.toLowerCase().includes('amazon');
        const badgeClass = isAmazon ? 'platform-badge amazon' : 'platform-badge flipkart';
        const badgeLabel = isAmazon ? 'AMAZON' : 'FLIPKART';
        
        // Format timestamp safely
        let dealTime = 'Unknown time';
        if (deal.timestamp) {
            try {
                dealTime = new Date(deal.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            } catch (e) {
                console.error(e);
            }
        }
        
        // Title check & truncation safely
        const titleStr = deal.title || 'Untitled Deal';
        const displayTitle = titleStr.length > 85 
            ? titleStr.substring(0, 82) + '...' 
            : titleStr;
        
        // Image check (offline-safe inline base64 fallback)
        const noImageFallback = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNTAiIGhlaWdodD0iMTUwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMmEyNzMwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmb250LXNpemU9IjE0IiBmaWxsPSIjOTU4Zjk5Ij5ObyBJbWFnZTwvdGV4dD48L3N2Zz4=";
        const displayImage = (deal.image_url && !deal.image_url.startsWith('data:')) 
            ? deal.image_url 
            : noImageFallback;
            
        // True lowest ever price verification badge
        const lowBadge = deal.is_verified_low 
            ? '<span class="all-time-low-badge"><i class="fa-solid fa-award"></i> ALL-TIME LOW</span>' 
            : '';

        // Safe price formatting
        const priceVal = deal.price ? parseInt(deal.price).toLocaleString() : '0';
        const mrpVal = deal.mrp ? parseInt(deal.mrp).toLocaleString() : '0';
        const discountVal = deal.discount ? parseFloat(deal.discount).toFixed(0) : '0';
        const dealUrl = deal.url || '#';
        const operatorName = encodeURIComponent(localStorage.getItem('operator_identity') || 'Anonymous');
        const redirectUrl = IS_STATIC_MODE 
            ? dealUrl
            : `${API_BASE}/api/redirect?id=${deal.id}&user=${operatorName}&url=${encodeURIComponent(dealUrl)}`;
        
        const clicksLabel = deal.clicks > 0 
            ? `<span class="deal-clicks" title="Total clicks from this dashboard"><i class="fa-solid fa-fire text-red"></i> ${deal.clicks} clicks</span>` 
            : '';

        html += `
            <div class="deal-item">
                <div class="deal-img-wrapper">
                    <span class="${badgeClass}">${badgeLabel}</span>
                    <img src="${displayImage}" alt="Product image" onerror="this.onerror=null; this.src='${noImageFallback}';">
                </div>
                <div class="deal-content">
                    <div class="deal-header-row">
                        <h4 class="deal-title" title="${titleStr}">${displayTitle}</h4>
                        ${lowBadge}
                    </div>
                    <div class="deal-price-block">
                        <span class="current-price">₹${priceVal}</span>
                        <span class="mrp-price">₹${mrpVal}</span>
                        <span class="discount-tag">${discountVal}% OFF</span>
                    </div>
                    <div class="deal-footer">
                        <span class="deal-time"><i class="fa-solid fa-clock"></i> Broadcasted at ${dealTime} ${clicksLabel}</span>
                        <div class="deal-actions-row" style="display: flex; gap: 8px; align-items: center;">
                            ${isAuthorized() ? `<button class="btn-delete-deal" data-id="${deal.id}" title="Remove this deal from feed"><i class="fa-solid fa-trash"></i></button>` : ''}
                            <a href="${redirectUrl}" target="_blank" class="btn-grab">GRAB DEAL <i class="fa-solid fa-up-right-from-square"></i></a>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    dealsContainer.innerHTML = html;
}

// Log streaming console
let lastLogText = '';
function updateLogsUI(logs) {
    const fullText = logs.join('');
    if (fullText === lastLogText) return; // avoid redraw if no updates
    lastLogText = fullText;
    
    let html = '';
    logs.forEach(line => {
        // Strip newline
        let cleanLine = line.replace('\n', '');
        
        // Parse time and text
        let timePart = '';
        let rest = cleanLine;
        const timeMatch = cleanLine.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})/);
        
        if (timeMatch) {
            timePart = timeMatch[1];
            rest = cleanLine.substring(timePart.length);
        }
        
        // Set styling based on log level
        let levelClass = 'log-level-info';
        if (rest.includes('[WARNING]')) {
            levelClass = 'log-level-warning';
        } else if (rest.includes('[ERROR]')) {
            levelClass = 'log-level-error';
        }
        
        html += `<div class="log-line">`;
        if (timePart) {
            html += `<span class="log-time">[${timePart.split(' ')[1]}]</span>`;
        }
        html += `<span class="${levelClass}">${rest}</span>`;
        html += `</div>`;
    });
    
    consoleLogs.innerHTML = html;
    // Auto scroll to bottom
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// ==========================================
// SELECTOR FORM MANAGEMENT
// ==========================================
function loadPlatformSelectorsToForm(platformKey) {
    const pData = currentSelectors[platformKey];
    if (!pData) return;
    
    document.getElementById('feed-url').value = pData.url || '';
    document.getElementById('card-sel').value = pData.card_selector || '';
    document.getElementById('title-sel').value = pData.title_selector || '';
    document.getElementById('link-sel').value = pData.link_selector || '';
    document.getElementById('image-sel').value = pData.image_selector || '';
}

function updateLocalSelectorsState() {
    if (!currentSelectors[selectedPlatformKey]) {
        currentSelectors[selectedPlatformKey] = {};
    }
    
    currentSelectors[selectedPlatformKey].url = document.getElementById('feed-url').value;
    currentSelectors[selectedPlatformKey].card_selector = document.getElementById('card-sel').value;
    currentSelectors[selectedPlatformKey].title_selector = document.getElementById('title-sel').value;
    currentSelectors[selectedPlatformKey].link_selector = document.getElementById('link-sel').value;
    currentSelectors[selectedPlatformKey].image_selector = document.getElementById('image-sel').value;
}

// ==========================================
// EVENT LISTENERS
// ==========================================

// Toggle running status
toggleBtn.addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_BASE}/api/toggle`, { method: 'POST' });
        if (!response.ok) throw new Error('Toggle error');
        const data = await response.json();
        
        if (data.is_running) {
            showToast('Deals scanner is now active.');
        } else {
            showToast('Deals scanner has been paused.', 'error');
        }
        fetchStatus();
    } catch (err) {
        showToast('Connection failed. Could not communicate with server.', 'error');
    }
});

// Trigger manual scan
scanBtn.addEventListener('click', async () => {
    scanBtn.disabled = true;
    scanBtn.querySelector('i').classList.add('fa-spin');
    
    try {
        const response = await fetch(`${API_BASE}/api/scan`, { method: 'POST' });
        if (!response.ok) throw new Error('Scan command error');
        showToast('Immediate manual scan execution loop triggered.');
    } catch (err) {
        showToast('Could not trigger manual scan.', 'error');
    }
    
    setTimeout(() => {
        scanBtn.disabled = false;
        scanBtn.querySelector('i').classList.remove('fa-spin');
    }, 3000);
});

// Handle selector forms changes and tab toggles
tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        // Save current tab values first
        updateLocalSelectorsState();
        
        // Shift active state
        tabButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Update selected key and load form
        const platformCode = btn.getAttribute('data-platform');
        selectedPlatformKey = platformKeyMap[platformCode];
        loadPlatformSelectorsToForm(selectedPlatformKey);
    });
});

// Save selectors back to backend API
saveSelectorsBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!selectorForm.reportValidity()) return;
    
    // Refresh state from form values
    updateLocalSelectorsState();
    
    try {
        const response = await fetch(`${API_BASE}/api/selectors`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentSelectors)
        });
        if (!response.ok) throw new Error('Selector save failure');
        showToast('Scraper selectors matrix updated successfully!');
    } catch (err) {
        showToast('Failed to save selectors to server.', 'error');
    }
});

// ==========================================
// INITIALIZATION
// ==========================================
async function fetchClicks() {
    try {
        const response = await fetch(`${API_BASE}/api/clicks`);
        if (!response.ok) throw new Error('Clicks sync failure');
        const data = await response.json();
        updateClicksUI(data);
    } catch (err) {
        console.error('API Error (Clicks):', err);
    }
}

function updateClicksUI(clicks) {
    const totalBadge = document.getElementById('clicks-total-badge');
    const topDealEl = document.getElementById('top-clicked-deal');
    const logContainer = document.getElementById('clicks-log-container');
    
    if (!totalBadge || !topDealEl || !logContainer) return;
    
    totalBadge.textContent = `${clicks.length} Clicks`;
    
    // Save to global cache
    lastClicksData = clicks;
    
    // Render visual Chart.js chart
    renderClicksChart(clicks);
    
    if (clicks.length === 0) {
        topDealEl.textContent = 'None';
        topDealEl.title = 'None';
        logContainer.innerHTML = '<div class="log-line system-line">Waiting for link click activity...</div>';
        return;
    }
    
    // Calculate top clicked deal
    const counts = {};
    clicks.forEach(c => {
        counts[c.title] = (counts[c.title] || 0) + 1;
    });
    
    let topTitle = 'None';
    let maxCount = 0;
    for (const title in counts) {
        if (counts[title] > maxCount) {
            maxCount = counts[title];
            topTitle = title;
        }
    }
    
    topDealEl.textContent = maxCount > 0 ? `${topTitle} (${maxCount}x)` : 'None';
    topDealEl.title = topTitle;
    
    let html = '';
    clicks.forEach(c => {
        const timeStr = new Date(c.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const displayTitle = c.title.length > 30 ? c.title.substring(0, 27) + '...' : c.title;
        const userDisplay = c.user && c.user !== 'Anonymous' ? `${c.user} (${c.ip})` : c.ip;
        html += `
            <div class="click-line">
                <span class="click-time">[${timeStr}]</span> 
                <span class="click-ip">${userDisplay}</span> clicked 
                <span class="click-title" title="${c.title}">"${displayTitle}"</span>
            </div>
        `;
    });
    
    logContainer.innerHTML = html;
}

function renderClicksChart(clicks) {
    const canvas = document.getElementById('clicks-chart');
    if (!canvas) return;
    
    const counts = {};
    clicks.forEach(c => {
        const shortTitle = c.title.length > 25 ? c.title.substring(0, 22) + '...' : c.title;
        counts[shortTitle] = (counts[shortTitle] || 0) + 1;
    });
    
    const sorted = Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
        
    const labels = sorted.map(item => item[0]);
    const dataValues = sorted.map(item => item[1]);
    
    if (sorted.length === 0) {
        labels.push('No clicks yet');
        dataValues.push(0);
    }
    
    const isDarkMode = !document.body.classList.contains('light-mode');
    const textColor = isDarkMode ? '#94a3b8' : '#475569';
    const gridColor = isDarkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
    const barColor = isDarkMode ? 'rgba(255, 153, 0, 0.75)' : 'rgba(27, 100, 218, 0.75)';
    const barBorderColor = isDarkMode ? '#ff9900' : '#1b64da';
    
    if (clicksChartInstance) {
        clicksChartInstance.data.labels = labels;
        clicksChartInstance.data.datasets[0].data = dataValues;
        clicksChartInstance.data.datasets[0].backgroundColor = barColor;
        clicksChartInstance.data.datasets[0].borderColor = barBorderColor;
        clicksChartInstance.options.scales.x.ticks.color = textColor;
        clicksChartInstance.options.scales.y.ticks.color = textColor;
        clicksChartInstance.options.scales.x.grid.color = gridColor;
        clicksChartInstance.options.scales.y.grid.color = gridColor;
        clicksChartInstance.update();
    } else {
        const ctx = canvas.getContext('2d');
        clicksChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Clicks',
                    data: dataValues,
                    backgroundColor: barColor,
                    borderColor: barBorderColor,
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { color: textColor, stepSize: 1, precision: 0 },
                        grid: { color: gridColor }
                    },
                    y: {
                        ticks: { color: textColor },
                        grid: { display: false }
                    }
                }
            }
        });
    }
}

async function fetchSettings() {
    if (IS_STATIC_MODE) return;
    try {
        const response = await fetch(`${API_BASE}/api/settings`);
        const settings = await response.json();
        
        document.getElementById('set-amazon-tag').value = settings.amazon_tag || '';
        document.getElementById('set-flipkart-affid').value = settings.flipkart_affid || '';
        document.getElementById('set-telegram-token').value = settings.telegram_bot_token || '';
        document.getElementById('set-telegram-chat').value = settings.telegram_chat_id || '';
        document.getElementById('set-min-discount').value = settings.min_discount || 30;
        document.getElementById('set-discord-webhook').value = settings.discord_webhook_url || '';
        document.getElementById('set-proxies-enabled').checked = settings.proxies_enabled || false;
        
        const proxyList = settings.proxy_list || [];
        document.getElementById('set-proxy-list').value = proxyList.join('\n');
    } catch (err) {
        console.error('API Error (Settings):', err);
    }
}

async function saveSettings(e) {
    if (e) e.preventDefault();
    
    const amazon_tag = document.getElementById('set-amazon-tag').value.trim();
    const flipkart_affid = document.getElementById('set-flipkart-affid').value.trim();
    const telegram_bot_token = document.getElementById('set-telegram-token').value.trim();
    const telegram_chat_id = document.getElementById('set-telegram-chat').value.trim();
    const min_discount = parseFloat(document.getElementById('set-min-discount').value) || 30;
    const discord_webhook_url = document.getElementById('set-discord-webhook').value.trim();
    const proxies_enabled = document.getElementById('set-proxies-enabled').checked;
    
    const proxyText = document.getElementById('set-proxy-list').value;
    const proxy_list = proxyText.split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0);
        
    const settings = {
        amazon_tag,
        flipkart_affid,
        telegram_bot_token,
        telegram_chat_id,
        min_discount,
        discord_webhook_url,
        proxies_enabled,
        proxy_list
    };
    
    try {
        const response = await fetch(`${API_BASE}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (response.ok) {
            showToast('Settings saved successfully!');
            fetchSettings();
        } else {
            showToast('Failed to save settings.', 'error');
        }
    } catch (err) {
        console.error('Save Settings Error:', err);
        showToast('Connection error. Could not save settings.', 'error');
    }
}

function init() {
    fetchStatus();
    fetchDeals();
    
    if (IS_STATIC_MODE) {
        // Statically poll deals file every minute
        setInterval(fetchDeals, 60000);
        return;
    }
    
    fetchLogs();
    fetchSelectors();
    fetchClicks();
    
    // Set periodic polling
    setInterval(fetchStatus, 3000);
    setInterval(fetchDeals, 5000);
    setInterval(fetchLogs, 3000);
    setInterval(fetchClicks, 4000);

    // Event delegation for delete buttons
    if (dealsContainer) {
        dealsContainer.addEventListener('click', async (e) => {
            const deleteBtn = e.target.closest('.btn-delete-deal');
            if (!deleteBtn) return;
            
            const dealId = deleteBtn.getAttribute('data-id');
            if (!dealId) return;
            
            if (confirm('Are you sure you want to remove this deal from the feed?')) {
                try {
                    const response = await fetch(`${API_BASE}/api/deals/delete`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id: dealId })
                    });
                    if (response.ok) {
                        showToast('Deal removed from matrix.');
                        fetchDeals();
                    } else {
                        showToast('Failed to delete deal.', 'error');
                    }
                } catch (err) {
                    showToast('Connection error. Could not delete deal.', 'error');
                }
            }
        });
    }
    
    // Fetch and bind settings
    fetchSettings();
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', saveSettings);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Detect local file protocol to trigger browser security warning
    if (window.location.protocol === 'file:') {
        const warningBanner = document.getElementById('file-protocol-warning');
        if (warningBanner) {
            warningBanner.style.display = 'flex';
        }
    }

    // Auth helper
    function isAuthorized() {
        return localStorage.getItem('admin_token') === 'admin_session_key_vihan_143';
    }

    function checkAuthentication() {
        if (IS_STATIC_MODE) return true; // Bypass authentication in static cloud mode
        const overlay = document.getElementById('login-overlay');
        if (!overlay) return true;
        if (!isAuthorized()) {
            overlay.style.display = 'flex';
            return false;
        } else {
            overlay.style.display = 'none';
            return true;
        }
    }

    // Operator Identity Caching & Display
    function updateOperatorDisplay() {
        const userDisplayName = document.getElementById('user-display-name');
        if (userDisplayName) {
            if (isAuthorized()) {
                userDisplayName.textContent = localStorage.getItem('operator_identity') || 'Yogesh Padwal';
            } else {
                userDisplayName.textContent = 'Anonymous';
            }
        }
    }
    updateOperatorDisplay();

    // Check authentication
    if (!checkAuthentication()) {
        const loginForm = document.getElementById('login-form');
        const loginError = document.getElementById('login-error');
        
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value.trim();
            const password = document.getElementById('login-password').value.trim();
            
            try {
                const response = await fetch(`${API_BASE}/api/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem('admin_token', data.token);
                    localStorage.setItem('operator_identity', data.name);
                    
                    updateOperatorDisplay();
                    
                    document.getElementById('login-overlay').style.display = 'none';
                    init();
                    showToast(`Welcome back, ${data.name}!`);
                } else {
                    loginError.style.display = 'flex';
                }
            } catch (err) {
                console.error(err);
                loginError.textContent = 'Server connection failed.';
                loginError.style.display = 'flex';
            }
        });
    } else {
        init();
    }

    // Logout logic
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('admin_token');
            localStorage.removeItem('operator_identity');
            window.location.reload();
        });
    }
    
    // Theme Toggle logic
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const themeIcon = themeToggleBtn.querySelector('i');

    // Check saved theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        themeIcon.className = 'fa-solid fa-sun';
    } else {
        document.body.classList.remove('light-mode');
        themeIcon.className = 'fa-solid fa-moon';
    }

    themeToggleBtn.addEventListener('click', () => {
        document.body.classList.toggle('light-mode');
        const isLight = document.body.classList.contains('light-mode');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        themeIcon.className = isLight ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
        showToast(`${isLight ? 'Light' : 'Dark'} mode activated.`);
        if (lastClicksData && lastClicksData.length > 0) {
            renderClicksChart(lastClicksData);
        }
    });

    // Feed controls live listeners
    document.getElementById('feed-search').addEventListener('input', applyFiltersAndRender);
    document.getElementById('feed-filter-platform').addEventListener('change', applyFiltersAndRender);
    document.getElementById('feed-sort').addEventListener('change', applyFiltersAndRender);
});
