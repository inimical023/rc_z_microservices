// Main JavaScript for RingCentral-Zoho Admin Interface

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the dashboard
    initializeDashboard();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    loadServiceStatus();
    loadExtensions();
    loadLeadOwners();
});

// Initialize dashboard with charts
function initializeDashboard() {
    // Create call stats chart
    const ctx = document.getElementById('call-stats-chart').getContext('2d');
    const callStatsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Accepted Calls', 'Missed Calls', 'Leads Created', 'Recordings Attached'],
            datasets: [{
                label: 'Last 24 Hours',
                data: [0, 0, 0, 0],
                backgroundColor: [
                    'rgba(75, 192, 192, 0.2)',
                    'rgba(255, 99, 132, 0.2)',
                    'rgba(54, 162, 235, 0.2)',
                    'rgba(255, 206, 86, 0.2)'
                ],
                borderColor: [
                    'rgba(75, 192, 192, 1)',
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Simulate some data for the chart
    setTimeout(() => {
        callStatsChart.data.datasets[0].data = [12, 8, 15, 10];
        callStatsChart.update();
    }, 1000);
    
    // Populate recent activity with dummy data
    const recentActivity = document.getElementById('recent-activity');
    recentActivity.innerHTML = `
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>${new Date().toLocaleTimeString()}</td>
                    <td>Lead Created</td>
                    <td>New lead from +1 (555) 123-4567</td>
                </tr>
                <tr>
                    <td>${new Date(Date.now() - 5 * 60000).toLocaleTimeString()}</td>
                    <td>Recording Attached</td>
                    <td>Recording attached to lead ID 12345</td>
                </tr>
                <tr>
                    <td>${new Date(Date.now() - 15 * 60000).toLocaleTimeString()}</td>
                    <td>Call Processed</td>
                    <td>Processed 5 new calls</td>
                </tr>
            </tbody>
        </table>
    `;
}

// Set up event listeners for all interactive elements
function setupEventListeners() {
    // Credentials tab
    document.getElementById('verify-rc-btn')?.addEventListener('click', verifyRingCentralCredentials);
    document.getElementById('verify-zoho-btn')?.addEventListener('click', verifyZohoCredentials);
    document.getElementById('save-credentials-btn')?.addEventListener('click', saveAllCredentials);
    
    // Extensions tab
    document.getElementById('refresh-extensions-btn')?.addEventListener('click', loadExtensions);
    document.getElementById('add-extensions-btn')?.addEventListener('click', addSelectedExtensions);
    document.getElementById('remove-extensions-btn')?.addEventListener('click', removeSelectedExtensions);
    document.getElementById('save-extensions-btn')?.addEventListener('click', saveExtensions);
    
    // Lead Owners tab
    document.getElementById('refresh-users-btn')?.addEventListener('click', loadLeadOwners);
    document.getElementById('add-owners-btn')?.addEventListener('click', addSelectedOwners);
    document.getElementById('remove-owners-btn')?.addEventListener('click', removeSelectedOwners);
    document.getElementById('save-owners-btn')?.addEventListener('click', saveLeadOwners);
    
    // Process Calls tab
    document.getElementById('process-calls-btn')?.addEventListener('click', processCalls);
    
    // Custom date range toggle
    const customRangeRadio = document.getElementById('customRange');
    if (customRangeRadio) {
        customRangeRadio.addEventListener('change', toggleCustomDateRange);
        document.querySelectorAll('input[name="dateRange"]').forEach(radio => {
            radio.addEventListener('change', toggleCustomDateRange);
        });
    }
    
    // Settings tab
    document.getElementById('save-notification-settings-btn')?.addEventListener('click', saveNotificationSettings);
    document.getElementById('save-system-settings-btn')?.addEventListener('click', saveSystemSettings);
}

// Toggle custom date range inputs
function toggleCustomDateRange() {
    const customRangeInputs = document.getElementById('customRangeInputs');
    const customRangeRadio = document.getElementById('customRange');
    
    if (customRangeRadio && customRangeInputs) {
        customRangeInputs.style.display = customRangeRadio.checked ? 'block' : 'none';
    }
}

// Load service status
async function loadServiceStatus() {
    try {
        const response = await fetch('/api/services');
        const services = await response.json();
        
        const serviceStatusDiv = document.getElementById('service-status');
        if (!serviceStatusDiv) return;
        
        let html = '<table class="table table-striped">';
        html += '<thead><tr><th>Service</th><th>Status</th><th>Uptime</th></tr></thead>';
        html += '<tbody>';
        
        for (const [name, service] of Object.entries(services)) {
            const statusClass = service.status === 'healthy' ? 'text-success' : 
                               (service.status === 'unhealthy' ? 'text-danger' : 'text-warning');
            
            const uptime = formatUptime(service.uptime);
            
            html += `<tr>
                <td>${name}</td>
                <td><span class="${statusClass}">${service.status}</span></td>
                <td>${uptime}</td>
            </tr>`;
        }
        
        html += '</tbody></table>';
        serviceStatusDiv.innerHTML = html;
    } catch (error) {
        console.error('Error loading service status:', error);
        document.getElementById('service-status').innerHTML = 
            '<div class="alert alert-danger">Error loading service status</div>';
    }
}

// Format uptime in a human-readable format
function formatUptime(seconds) {
    if (typeof seconds !== 'number') return 'Unknown';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (days > 0) {
        return `${days}d ${hours}h ${minutes}m`;
    } else if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Load extensions from Call Service
async function loadExtensions() {
    try {
        const response = await fetch('/api/extensions');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message);
        }
        
        const availableExtDiv = document.getElementById('available-extensions');
        if (!availableExtDiv) return;
        
        let html = '<div class="list-group">';
        data.extensions.forEach(ext => {
            html += `
                <label class="list-group-item">
                    <input class="form-check-input me-1" type="checkbox" value="${ext.id}">
                    ${ext.name || ext.id} (${ext.extensionNumber || 'Unknown'})
                </label>
            `;
        });
        html += '</div>';
        
        availableExtDiv.innerHTML = html;
        
        // Also update monitored extensions (in a real app, this would be a separate API call)
        const monitoredExtDiv = document.getElementById('monitored-extensions');
        if (monitoredExtDiv) {
            monitoredExtDiv.innerHTML = '<div class="alert alert-info">No extensions currently monitored</div>';
        }
    } catch (error) {
        console.error('Error loading extensions:', error);
        document.getElementById('available-extensions').innerHTML = 
            '<div class="alert alert-danger">Error loading extensions</div>';
    }
}

// Load lead owners from Lead Service
async function loadLeadOwners() {
    try {
        const response = await fetch('/api/lead-owners');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message);
        }
        
        const availableUsersDiv = document.getElementById('available-users');
        if (!availableUsersDiv) return;
        
        let html = '<div class="list-group">';
        data.owners.forEach(owner => {
            html += `
                <label class="list-group-item">
                    <input class="form-check-input me-1" type="checkbox" value="${owner.id}">
                    ${owner.name || 'Unknown'} (${owner.email || 'No email'})
                </label>
            `;
        });
        html += '</div>';
        
        availableUsersDiv.innerHTML = html;
        
        // Also update lead owners (in a real app, this would be a separate API call)
        const leadOwnersDiv = document.getElementById('lead-owners');
        if (leadOwnersDiv) {
            leadOwnersDiv.innerHTML = '<div class="alert alert-info">No lead owners currently configured</div>';
        }
    } catch (error) {
        console.error('Error loading lead owners:', error);
        document.getElementById('available-users').innerHTML = 
            '<div class="alert alert-danger">Error loading users</div>';
    }
}

// Verify RingCentral credentials
async function verifyRingCentralCredentials() {
    const jwt = document.getElementById('rc-jwt').value;
    const clientId = document.getElementById('rc-client-id').value;
    const clientSecret = document.getElementById('rc-client-secret').value;
    
    if (!jwt || !clientId || !clientSecret) {
        alert('Please fill in all RingCentral credential fields');
        return;
    }
    
    // In a real app, this would make an API call to verify the credentials
    alert('RingCentral credentials verification would happen here');
}

// Verify Zoho credentials
async function verifyZohoCredentials() {
    const clientId = document.getElementById('zoho-client-id').value;
    const clientSecret = document.getElementById('zoho-client-secret').value;
    const refreshToken = document.getElementById('zoho-refresh-token').value;
    
    if (!clientId || !clientSecret || !refreshToken) {
        alert('Please fill in all Zoho credential fields');
        return;
    }
    
    // In a real app, this would make an API call to verify the credentials
    alert('Zoho credentials verification would happen here');
}

// Save all credentials
async function saveAllCredentials() {
    const rcJwt = document.getElementById('rc-jwt').value;
    const rcClientId = document.getElementById('rc-client-id').value;
    const rcClientSecret = document.getElementById('rc-client-secret').value;
    const rcAccountId = document.getElementById('rc-account-id').value || '~';
    
    const zohoClientId = document.getElementById('zoho-client-id').value;
    const zohoClientSecret = document.getElementById('zoho-client-secret').value;
    const zohoRefreshToken = document.getElementById('zoho-refresh-token').value;
    
    if (!rcJwt || !rcClientId || !rcClientSecret || !zohoClientId || !zohoClientSecret || !zohoRefreshToken) {
        alert('Please fill in all credential fields');
        return;
    }
    
    try {
        const response = await fetch('/api/credentials', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                rc_jwt: rcJwt,
                rc_client_id: rcClientId,
                rc_client_secret: rcClientSecret,
                rc_account_id: rcAccountId,
                zoho_client_id: zohoClientId,
                zoho_client_secret: zohoClientSecret,
                zoho_refresh_token: zohoRefreshToken
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Credentials saved successfully');
        } else {
            alert(`Error saving credentials: ${data.message}`);
        }
    } catch (error) {
        console.error('Error saving credentials:', error);
        alert('Error saving credentials. See console for details.');
    }
}

// Add selected extensions to monitored list
function addSelectedExtensions() {
    alert('This would add the selected extensions to the monitored list');
}

// Remove selected extensions from monitored list
function removeSelectedExtensions() {
    alert('This would remove the selected extensions from the monitored list');
}

// Save extensions configuration
async function saveExtensions() {
    alert('This would save the extensions configuration');
}

// Add selected users to lead owners list
function addSelectedOwners() {
    alert('This would add the selected users to the lead owners list');
}

// Remove selected owners from lead owners list
function removeSelectedOwners() {
    alert('This would remove the selected owners from the lead owners list');
}

// Save lead owners configuration
async function saveLeadOwners() {
    alert('This would save the lead owners configuration');
}

// Process calls based on form settings
async function processCalls() {
    const dateRangeValue = document.querySelector('input[name="dateRange"]:checked').value;
    let hoursBack = null;
    let startDate = null;
    let endDate = null;
    
    if (dateRangeValue === 'custom') {
        startDate = document.getElementById('startDate').value;
        endDate = document.getElementById('endDate').value;
        
        if (!startDate || !endDate) {
            alert('Please select both start and end dates');
            return;
        }
    } else {
        hoursBack = parseInt(dateRangeValue);
    }
    
    const acceptedCalls = document.getElementById('acceptedCalls').checked;
    const missedCalls = document.getElementById('missedCalls').checked;
    
    if (!acceptedCalls && !missedCalls) {
        alert('Please select at least one call type');
        return;
    }
    
    // Update processing status
    const processingStatus = document.getElementById('processing-status');
    processingStatus.innerHTML = '<div class="alert alert-info">Processing calls...</div>';
    
    // In a real app, this would make API calls to process the calls
    setTimeout(() => {
        processingStatus.innerHTML = '<div class="alert alert-success">Call processing completed successfully</div>';
    }, 2000);
}

// Save notification settings
async function saveNotificationSettings() {
    const enableNotifications = document.getElementById('enableNotifications').checked;
    const notificationEmails = document.getElementById('notificationEmails').value;
    
    alert(`This would save notification settings: Enabled=${enableNotifications}, Emails=${notificationEmails}`);
}

// Save system settings
async function saveSystemSettings() {
    const logLevel = document.getElementById('logLevel').value;
    const debugMode = document.getElementById('debugMode').checked;
    
    alert(`This would save system settings: LogLevel=${logLevel}, DebugMode=${debugMode}`);
}