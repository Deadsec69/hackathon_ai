// Connect to Socket.IO server
const socket = io();

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');

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
const agentRunning = document.getElementById('agentRunning');
const agentLastRun = document.getElementById('agentLastRun');
const agentRunInterval = document.getElementById('agentRunInterval');
const runAgentBtn = document.getElementById('runAgentBtn');
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

// Socket.IO connection status
socket.on('connect', () => {
    statusDot.classList.add('connected');
    statusText.textContent = 'Connected';
    
    // Load initial data
    loadAgentStatus();
    loadIncidents();
    loadRestartCounts();
});

socket.on('disconnect', () => {
    statusDot.classList.remove('connected');
    statusText.textContent = 'Disconnected';
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

// Agent status
function loadAgentStatus() {
    fetch('/api/agent/status')
        .then(response => response.json())
        .then(data => {
            agentRunning.textContent = data.running ? 'Yes' : 'No';
            agentLastRun.textContent = data.last_run_time ? new Date(data.last_run_time * 1000).toLocaleString() : 'Never';
            agentRunInterval.textContent = `${data.run_interval}s`;
        })
        .catch(error => {
            console.error('Error loading agent status:', error);
        });
}

runAgentBtn.addEventListener('click', () => {
    socket.emit('run agent');
});

socket.on('agent response', (response) => {
    if (response.type === 'success') {
        addMessage('action', response.content);
        loadAgentStatus();
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

// Simulate issues
function simulateIssue(type) {
    socket.emit('simulate issue', { issue_type: type });
}

function stopSimulation() {
    socket.emit('stop simulation');
}

simulateCpuBtn.addEventListener('click', () => simulateIssue('cpu'));
simulateMemoryBtn.addEventListener('click', () => simulateIssue('memory'));
stopSimulationBtn.addEventListener('click', stopSimulation);

simulateCpuBtnView.addEventListener('click', () => simulateIssue('cpu'));
simulateMemoryBtnView.addEventListener('click', () => simulateIssue('memory'));
stopSimulationBtnView.addEventListener('click', stopSimulation);

socket.on('simulation response', (response) => {
    if (response.type === 'success') {
        simulationStatus.innerHTML = `<p>${response.content}</p>`;
        addMessage('action', response.content);
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
