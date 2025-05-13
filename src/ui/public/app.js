// Connect to Socket.IO server
const socket = io();

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const chatHeader = document.getElementById('chatHeader');
const chatToggle = document.getElementById('chatToggle');
const chatContainer = document.querySelector('.chat-container');
const chatResetPodBtn = document.getElementById('chatResetPodBtn');

// View elements
const dashboardBtn = document.getElementById('dashboardBtn');
const incidentsBtn = document.getElementById('incidentsBtn');
const simulateBtn = document.getElementById('simulateBtn');
const settingsBtn = document.getElementById('settingsBtn');
const dashboardView = document.getElementById('dashboardView');
const incidentsView = document.getElementById('incidentsView');
const simulateView = document.getElementById('simulateView');
const settingsView = document.getElementById('settingsView');

// Dashboard elements
const apiHealth = document.getElementById('apiHealth');
const agentHealth = document.getElementById('agentHealth');
const prometheusHealth = document.getElementById('prometheusHealth');
const grafanaHealth = document.getElementById('grafanaHealth');
const lastHealthCheck = document.getElementById('lastHealthCheck');
const recentIncidents = document.getElementById('recentIncidents');
const viewAllIncidentsBtn = document.getElementById('viewAllIncidentsBtn');
const restartCounts = document.getElementById('restartCounts');
const simulateCpuBtn = document.getElementById('simulateCpuBtn');
const simulateMemoryBtn = document.getElementById('simulateMemoryBtn');
const stopSimulationBtn = document.getElementById('stopSimulationBtn');

// Incidents elements
const incidentTypeFilter = document.getElementById('incidentTypeFilter');
const incidentStatusFilter = document.getElementById('incidentStatusFilter');
const refreshIncidentsBtn = document.getElementById('refreshIncidentsBtn');
const incidentsList = document.getElementById('incidentsList');

// Simulate elements
const simulateCpuBtnView = document.getElementById('simulateCpuBtnView');
const simulateMemoryBtnView = document.getElementById('simulateMemoryBtnView');
const stopSimulationBtnView = document.getElementById('stopSimulationBtnView');
const simulationStatus = document.getElementById('simulationStatus');

// Settings elements
const runIntervalInput = document.getElementById('runIntervalInput');
const maxRestartsInput = document.getElementById('maxRestartsInput');
const analysisThresholdInput = document.getElementById('analysisThresholdInput');
const cpuThresholdInput = document.getElementById('cpuThresholdInput');
const memoryThresholdInput = document.getElementById('memoryThresholdInput');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');

// Chat toggle functionality
chatHeader.addEventListener('click', () => {
    chatContainer.classList.toggle('open');
});

// Socket.IO connection status
socket.on('connect', () => {
    statusDot.classList.add('connected');
    statusText.textContent = 'Connected';
    
    // Load initial data
    loadAgentStatus();
    loadIncidents();
    loadRestartCounts();
    
    // Add welcome message
    addMessage('system', 'Welcome to the Kubernetes Monitoring Assistant! I can help you monitor your applications, simulate issues, and manage your Kubernetes cluster. Type "help" to see what I can do.');
    
    // Open chat on connect
    chatContainer.classList.add('open');
    
    // Auto-close chat after 5 seconds
    setTimeout(() => {
        chatContainer.classList.remove('open');
    }, 5000);
});

socket.on('disconnect', () => {
    statusDot.classList.remove('connected');
    statusText.textContent = 'Disconnected';
});

// Handle server status updates
socket.on('server_status', (status) => {
    // Add server status message to chat
    addMessage('system', status.content);
    
    // If it's a success message about server restart, refresh health checks
    if (status.type === 'success' && status.content.includes('restart')) {
        // Wait a moment for services to be fully up
        setTimeout(() => {
            checkServicesHealth();
            loadIncidents();
            loadRestartCounts();
        }, 1000);
    }
});

// Handle simulation status updates
socket.on('simulation_status_update', (status) => {
    // Update the simulation status in the UI
    if (status.type === 'all' && status.status === 'stopped') {
        // All simulations stopped
        simulationStatus.innerHTML = `<p>${status.message}</p>`;
    } else {
        // CPU or memory simulation status update
        simulationStatus.innerHTML = `<p>${status.type.toUpperCase()} simulation: ${status.message}</p>`;
    }
});

// Chat message handling
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

function sendMessage() {
    const message = messageInput.value.trim();
    if (message) {
        // Add user message to chat
        addMessage('user', message);
        
        // Send message to server
        socket.emit('chat message', message);
        
        // Clear input
        messageInput.value = '';
    }
}

socket.on('chat response', (response) => {
    addMessage(response.type, response.content);
});

function addMessage(type, content) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', type);
    
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// View switching
dashboardBtn.addEventListener('click', () => switchView('dashboard'));
incidentsBtn.addEventListener('click', () => switchView('incidents'));
simulateBtn.addEventListener('click', () => switchView('simulate'));
settingsBtn.addEventListener('click', () => switchView('settings'));
viewAllIncidentsBtn.addEventListener('click', () => switchView('incidents'));

function switchView(view) {
    // Hide all views
    dashboardView.classList.remove('active');
    incidentsView.classList.remove('active');
    simulateView.classList.remove('active');
    settingsView.classList.remove('active');
    
    // Remove active class from all buttons
    dashboardBtn.classList.remove('active');
    incidentsBtn.classList.remove('active');
    simulateBtn.classList.remove('active');
    settingsBtn.classList.remove('active');
    
    // Show selected view
    if (view === 'dashboard') {
        dashboardView.classList.add('active');
        dashboardBtn.classList.add('active');
        loadAgentStatus();
        loadIncidents(5);
        loadRestartCounts();
    } else if (view === 'incidents') {
        incidentsView.classList.add('active');
        incidentsBtn.classList.add('active');
        loadIncidents();
    } else if (view === 'simulate') {
        simulateView.classList.add('active');
        simulateBtn.classList.add('active');
    } else if (view === 'settings') {
        settingsView.classList.add('active');
        settingsBtn.classList.add('active');
    }
}

// Services health check
function checkServicesHealth() {
    // Check API health using status API
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            console.log('API status check response:', data);
            // API is healthy if CPU usage is below 10% and memory usage is below 50,000,000 bytes
            const isHealthy = data.cpu_usage <= 10 && data.memory_usage <= 50000000 && 
                             !data.cpu_spike_active && !data.memory_spike_active;
            updateServiceHealth(apiHealth, isHealthy);
            
            // Update simulation buttons based on API health and simulation status
            updateSimulationButtons(isHealthy, data.cpu_spike_active || data.memory_spike_active);
        })
        .catch(error => {
            console.error('API status check error:', error);
            updateServiceHealth(apiHealth, false);
            
            // Disable simulation buttons when API is unreachable
            updateSimulationButtons(false, false);
        });
    
    // Check Agent health
    fetch('/api/agent/health')
        .then(response => {
            updateServiceHealth(agentHealth, response.ok);
        })
        .catch(() => {
            updateServiceHealth(agentHealth, false);
        });
    
    // Check Prometheus health
    fetch('/api/prometheus/health')
        .then(response => {
            updateServiceHealth(prometheusHealth, response.ok);
        })
        .catch(() => {
            updateServiceHealth(prometheusHealth, false);
        });
    
    // Check Grafana health
    fetch('/api/grafana/health')
        .then(response => {
            updateServiceHealth(grafanaHealth, response.ok);
        })
        .catch(() => {
            updateServiceHealth(grafanaHealth, false);
        });
    
    // Update last check time
    lastHealthCheck.textContent = new Date().toLocaleString();
    
    // No need to schedule next check here as it's handled in loadAgentStatus
}

function updateServiceHealth(element, isHealthy) {
    const statusDot = element.querySelector('.status-dot');
    if (isHealthy) {
        statusDot.classList.add('connected');
        element.textContent = '';
        element.appendChild(statusDot);
        element.appendChild(document.createTextNode(' Healthy'));
    } else {
        statusDot.classList.remove('connected');
        element.textContent = '';
        element.appendChild(statusDot);
        element.appendChild(document.createTextNode(' Unhealthy'));
    }
}

// Agent status
function loadAgentStatus() {
    // Start health checks
    checkServicesHealth();
    
    // Start periodic data updates
    loadRecentIncidents();
    loadRestartCounts();
    loadAgentLogs();
    
    // Schedule periodic data updates with different intervals
    
    // Refresh logs more frequently (every 2 seconds)
    setInterval(() => {
        loadAgentLogs();
    }, 2000);
    
    // Refresh other data less frequently
    setInterval(() => {
        checkServicesHealth();
        loadRecentIncidents();
        loadRestartCounts();
    }, 5000);
}

// Load agent logs
function loadAgentLogs() {
    fetch('/api/agent/logs')
        .then(response => response.json())
        .then(data => {
            displayAgentLogs(data.logs);
        })
        .catch(error => {
            console.error('Error loading agent logs:', error);
            document.getElementById('agentLogs').innerHTML = '<p>Error loading agent logs</p>';
        });
}

// Keep track of the logs we've already displayed
let displayedLogIds = new Set();

function displayAgentLogs(logs) {
    const agentLogsElement = document.getElementById('agentLogs');
    
    if (!logs || logs.length === 0) {
        agentLogsElement.innerHTML = '<p>No logs available</p>';
        displayedLogIds.clear();
        return;
    }
    
    // Sort logs by timestamp (newest first)
    logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    // If this is the first time displaying logs, clear the container
    if (displayedLogIds.size === 0) {
        agentLogsElement.innerHTML = '';
    }
    
    // Check for new logs and add them to the display
    let newLogsAdded = false;
    
    logs.forEach(log => {
        // Create a unique ID for this log based on timestamp and message
        const logId = `${log.timestamp}-${log.message}`;
        
        // Only add logs we haven't displayed yet
        if (!displayedLogIds.has(logId)) {
            displayedLogIds.add(logId);
            newLogsAdded = true;
            
            const timestamp = new Date(log.timestamp).toLocaleString();
            const levelClass = log.level.toLowerCase();
            const component = log.component || 'agent';
            const message = log.message || '';
            
            // Determine if this log should have a special theme
            let specialClass = '';
            if (message.includes('Remed') || message.includes('remed')) {
                specialClass = 'remediation';
            } else if (message.includes('Agent run completed')) {
                specialClass = 'completion';
            }
            
            // Create the log entry element
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${levelClass} ${specialClass}`;
            logEntry.innerHTML = `
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-component">${component}</span>
                <span class="log-level">${log.level}</span>
                <span class="log-message">${message}</span>
            `;
            
            // Add the new log entry at the top of the list
            if (agentLogsElement.firstChild) {
                agentLogsElement.insertBefore(logEntry, agentLogsElement.firstChild);
            } else {
                agentLogsElement.appendChild(logEntry);
            }
        }
    });
    
    // If we have too many displayed logs, remove the oldest ones
    const maxDisplayedLogs = 50;
    if (displayedLogIds.size > maxDisplayedLogs) {
        // Get all log entries
        const logEntries = agentLogsElement.querySelectorAll('.log-entry');
        
        // Remove the oldest log entries
        for (let i = maxDisplayedLogs; i < logEntries.length; i++) {
            agentLogsElement.removeChild(logEntries[i]);
        }
        
        // Update the set of displayed log IDs
        displayedLogIds = new Set(Array.from(displayedLogIds).slice(0, maxDisplayedLogs));
    }
}

// Load recent incidents
function loadRecentIncidents() {
    // Get the 5 most recent incidents
    socket.emit('get incidents', { limit: 5 });
}

socket.on('agent response', (response) => {
    if (response.type === 'success') {
        addMessage('action', response.content);
    } else {
        addMessage('error', response.content);
    }
});

// Incidents
function loadIncidents(limit = null) {
    const filters = {
        incident_type: incidentTypeFilter.value || null,
        resolved: incidentStatusFilter.value ? incidentStatusFilter.value === 'true' : null,
        limit: limit
    };
    
    socket.emit('get incidents', filters);
}

socket.on('incidents response', (response) => {
    if (response.type === 'success') {
        displayIncidents(response.incidents, response.total);
    } else {
        if (incidentsView.classList.contains('active')) {
            incidentsList.innerHTML = `<p class="error">${response.content}</p>`;
        }
        recentIncidents.innerHTML = '<p>Error loading incidents</p>';
    }
});

function displayIncidents(incidents, total) {
    // Display in incidents view
    if (incidentsView.classList.contains('active')) {
        if (incidents.length === 0) {
            incidentsList.innerHTML = '<p>No incidents found</p>';
            return;
        }
        
        incidentsList.innerHTML = '';
        incidents.forEach(incident => {
            const incidentItem = document.createElement('div');
            incidentItem.classList.add('incident-item');
            
            const timestamp = new Date(incident.timestamp * 1000).toLocaleString();
            const issueType = incident.type.toUpperCase();
            
            incidentItem.innerHTML = `
                <div class="incident-header">
                    <div class="incident-title">${issueType} Issue in ${incident.pod_name}</div>
                    <div class="incident-time">${timestamp}</div>
                </div>
                <div class="incident-details">
                    <div class="incident-detail">
                        <span class="incident-label">Pod</span>
                        <span class="incident-value">${incident.pod_name}</span>
                    </div>
                    <div class="incident-detail">
                        <span class="incident-label">Namespace</span>
                        <span class="incident-value">${incident.namespace}</span>
                    </div>
                    <div class="incident-detail">
                        <span class="incident-label">Severity</span>
                        <span class="incident-value"><span class="severity ${incident.severity}">${incident.severity}</span></span>
                    </div>
                    <div class="incident-detail">
                        <span class="incident-label">Status</span>
                        <span class="incident-value">${incident.resolved ? 'Resolved' : 'Active'}</span>
                    </div>
                </div>
                <div class="incident-actions">
                    ${incident.github_issue ? `<a href="${incident.github_issue.html_url}" target="_blank" class="action-button">View Issue</a>` : ''}
                    ${incident.github_pr ? `<a href="${incident.github_pr.html_url}" target="_blank" class="action-button">View PR</a>` : ''}
                    ${!incident.resolved ? `<button class="action-button resolve-incident" data-id="${incident.id}">Resolve</button>` : ''}
                </div>
            `;
            
            incidentsList.appendChild(incidentItem);
        });
        
        // Add event listeners to resolve buttons
        document.querySelectorAll('.resolve-incident').forEach(button => {
            button.addEventListener('click', (e) => {
                const incidentId = e.target.dataset.id;
                resolveIncident(incidentId);
            });
        });
    }
    
    // Display in dashboard
    if (dashboardView.classList.contains('active')) {
        if (incidents.length === 0) {
            recentIncidents.innerHTML = '<p>No incidents found</p>';
            return;
        }
        
        recentIncidents.innerHTML = '';
        incidents.slice(0, 5).forEach(incident => {
            const incidentItem = document.createElement('div');
            incidentItem.classList.add('incident-item');
            
            const timestamp = new Date(incident.timestamp * 1000).toLocaleString();
            const issueType = incident.type.toUpperCase();
            
            incidentItem.innerHTML = `
                <div class="incident-header">
                    <div class="incident-title">${issueType} Issue in ${incident.pod_name}</div>
                    <div class="incident-time">${timestamp}</div>
                </div>
                <div class="incident-details">
                    <div class="incident-detail">
                        <span class="incident-label">Severity</span>
                        <span class="incident-value"><span class="severity ${incident.severity}">${incident.severity}</span></span>
                    </div>
                    <div class="incident-detail">
                        <span class="incident-label">Status</span>
                        <span class="incident-value">${incident.resolved ? 'Resolved' : 'Active'}</span>
                    </div>
                </div>
            `;
            
            recentIncidents.appendChild(incidentItem);
        });
    }
}

function resolveIncident(incidentId) {
    fetch(`/api/incidents/${incidentId}/resolve`, {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            loadIncidents();
            addMessage('action', `Incident ${incidentId} resolved`);
        })
        .catch(error => {
            console.error('Error resolving incident:', error);
            addMessage('error', `Error resolving incident: ${error.message}`);
        });
}

incidentTypeFilter.addEventListener('change', () => loadIncidents());
incidentStatusFilter.addEventListener('change', () => loadIncidents());
refreshIncidentsBtn.addEventListener('click', () => loadIncidents());

// Restart counts
function loadRestartCounts() {
    socket.emit('get restart counts');
}

socket.on('restart counts response', (response) => {
    if (response.type === 'success') {
        displayRestartCounts(response.restart_counts);
    } else {
        restartCounts.innerHTML = '<p>Error loading restart counts</p>';
    }
});

function displayRestartCounts(counts) {
    if (Object.keys(counts).length === 0) {
        restartCounts.innerHTML = '<p>No restart counts found</p>';
        return;
    }
    
    restartCounts.innerHTML = '';
    
    // Get today's date
    const today = new Date().toISOString().split('T')[0];
    
    // Sort dates in descending order
    const sortedDates = Object.keys(counts).sort().reverse();
    
    sortedDates.forEach(date => {
        const dateItem = document.createElement('div');
        dateItem.classList.add('restart-date');
        
        const isToday = date === today;
        
        dateItem.innerHTML = `
            <div class="restart-date-header">
                <strong>${isToday ? 'Today' : date}</strong>
            </div>
        `;
        
        const podsList = document.createElement('ul');
        podsList.classList.add('restart-pods');
        
        Object.entries(counts[date]).forEach(([pod, count]) => {
            const podItem = document.createElement('li');
            podItem.textContent = `${pod}: ${count} restarts`;
            podsList.appendChild(podItem);
        });
        
        dateItem.appendChild(podsList);
        restartCounts.appendChild(dateItem);
    });
}

// Update simulation buttons based on API health and simulation status
function updateSimulationButtons(isApiHealthy, isSimulationRunning) {
    // Disable CPU and Memory simulation buttons when API is unhealthy or a simulation is running
    if (simulateCpuBtn) simulateCpuBtn.disabled = !isApiHealthy || isSimulationRunning;
    if (simulateMemoryBtn) simulateMemoryBtn.disabled = !isApiHealthy || isSimulationRunning;
    if (simulateCpuBtnView) simulateCpuBtnView.disabled = !isApiHealthy || isSimulationRunning;
    if (simulateMemoryBtnView) simulateMemoryBtnView.disabled = !isApiHealthy || isSimulationRunning;
    
    // Always enable Restart Pod buttons
    if (stopSimulationBtnView) stopSimulationBtnView.disabled = false;
    
    console.log(`Simulation buttons updated: API Healthy=${isApiHealthy}, Simulation Running=${isSimulationRunning}`);
}

// Simulate issues
function simulateIssue(type) {
    socket.emit('simulate issue', { issue_type: type });
}

function stopSimulation() {
    socket.emit('stop simulation');
}

// Add event listeners to simulation buttons if they exist
if (simulateCpuBtn) simulateCpuBtn.addEventListener('click', () => simulateIssue('cpu'));
if (simulateMemoryBtn) simulateMemoryBtn.addEventListener('click', () => simulateIssue('memory'));

if (simulateCpuBtnView) simulateCpuBtnView.addEventListener('click', () => simulateIssue('cpu'));
if (simulateMemoryBtnView) simulateMemoryBtnView.addEventListener('click', () => simulateIssue('memory'));
if (stopSimulationBtnView) stopSimulationBtnView.addEventListener('click', stopSimulation);

// Chat Reset Pod button
chatResetPodBtn.addEventListener('click', () => {
    stopSimulation();
    // Open chat if it's closed
    chatContainer.classList.add('open');
    // Add message to chat
    addMessage('system', 'Restarting pod...');
});

socket.on('simulation response', (response) => {
    if (response.type === 'success') {
        simulationStatus.innerHTML = `<p>${response.content}</p>`;
        addMessage('action', response.content);
        
        // Check if this is a start or stop simulation response
        const isStarting = response.content.includes('started');
        const isStopping = response.content.includes('stopped');
        
        // Update button states based on simulation status
        if (isStarting || isStopping) {
            // Fetch the latest status to update button states
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    const isSimulationRunning = data.cpu_spike_active || data.memory_spike_active;
                    const isApiHealthy = data.cpu_usage <= 10 && data.memory_usage <= 50000000 && 
                                        !data.cpu_spike_active && !data.memory_spike_active;
                    updateSimulationButtons(isApiHealthy, isSimulationRunning);
                })
                .catch(error => {
                    console.error('Error updating button states:', error);
                });
        }
    } else {
        simulationStatus.innerHTML = `<p class="error">${response.content}</p>`;
        addMessage('error', response.content);
    }
});

// Settings
saveSettingsBtn.addEventListener('click', () => {
    const settings = {
        run_interval: parseInt(runIntervalInput.value),
        max_restarts: parseInt(maxRestartsInput.value),
        analysis_threshold: parseInt(analysisThresholdInput.value),
        cpu_threshold: parseInt(cpuThresholdInput.value),
        memory_threshold: parseInt(memoryThresholdInput.value)
    };
    
    // In a real implementation, we would save these settings to the server
    // For this PoC, we'll just show a message
    addMessage('action', 'Settings saved (not actually implemented in this PoC)');
});

// Initial view
switchView('dashboard');
