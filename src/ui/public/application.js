// Connect to Socket.IO server
const socket = io();

// DOM elements
const cpuBtn = document.getElementById('cpuBtn');
const memoryBtn = document.getElementById('memoryBtn');
const statusElement = document.getElementById('status');
const monitoringVisual = document.querySelector('.monitoring-visual');
const cpuMetricFill = document.querySelector('.cpu .metric-fill');
const memoryMetricFill = document.querySelector('.memory .metric-fill');

// Track simulation status
let simulationActive = false;
let simulationType = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check API status on load
    checkApiStatus();
    
    // Set up periodic status check
    setInterval(checkApiStatus, 5000);
});

// Socket.IO connection status
socket.on('connect', () => {
    console.log('Connected to server');
    updateStatus('Connected to monitoring server');
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    updateStatus('Disconnected from monitoring server');
});

// Handle simulation response
socket.on('simulation response', (response) => {
    console.log('Simulation response:', response);
    
    if (response.type === 'success') {
        // Update UI based on simulation type
        if (response.content.includes('CPU')) {
            simulationActive = true;
            simulationType = 'cpu';
            cpuBtn.classList.add('active');
            cpuBtn.disabled = true;
            memoryBtn.disabled = true;
            monitoringVisual.classList.add('cpu-spike');
            updateStatus('CPU spike simulation in progress. Agent is analyzing...');
            
            // Reset after animation completes
            setTimeout(() => {
                monitoringVisual.classList.remove('cpu-spike');
            }, 5000);
        } else if (response.content.includes('Memory')) {
            simulationActive = true;
            simulationType = 'memory';
            memoryBtn.classList.add('active');
            cpuBtn.disabled = true;
            memoryBtn.disabled = true;
            monitoringVisual.classList.add('memory-spike');
            updateStatus('Memory spike simulation in progress. Agent is analyzing...');
            
            // Reset after animation completes
            setTimeout(() => {
                monitoringVisual.classList.remove('memory-spike');
            }, 5000);
        } else if (response.content.includes('stopped')) {
            resetSimulationState();
            updateStatus('Simulation stopped. Resources returning to normal levels.');
        }
    } else {
        updateStatus(`Error: ${response.content}`);
    }
});

// Handle server status updates
socket.on('server_status', (status) => {
    console.log('Server status update:', status);
    updateStatus(status.content);
});

// Handle simulation status updates
socket.on('simulation_status_update', (status) => {
    console.log('Simulation status update:', status);
    
    if (status.type === 'all' && status.status === 'stopped') {
        resetSimulationState();
        updateStatus('All simulations stopped. Resources returning to normal levels.');
    } else if (status.type === 'cpu') {
        if (status.status === 'running') {
            simulationActive = true;
            simulationType = 'cpu';
            cpuBtn.classList.add('active');
            cpuBtn.disabled = true;
            memoryBtn.disabled = true;
            monitoringVisual.classList.add('cpu-spike');
            updateStatus('CPU spike detected. Agent is analyzing...');
        }
    } else if (status.type === 'memory') {
        if (status.status === 'running') {
            simulationActive = true;
            simulationType = 'memory';
            memoryBtn.classList.add('active');
            cpuBtn.disabled = true;
            memoryBtn.disabled = true;
            monitoringVisual.classList.add('memory-spike');
            updateStatus('Memory spike detected. Agent is analyzing...');
        }
    }
});

// Handle agent response
socket.on('agent response', (response) => {
    console.log('Agent response:', response);
    
    if (response.type === 'success') {
        updateStatus(`Agent action: ${response.content}`);
    } else {
        updateStatus(`Agent error: ${response.content}`);
    }
});

// Button event listeners
cpuBtn.addEventListener('click', () => {
    if (!simulationActive) {
        simulateCpuSpike();
    }
});

memoryBtn.addEventListener('click', () => {
    if (!simulationActive) {
        simulateMemorySpike();
    }
});

// Function to refresh the page after a delay
function schedulePageRefresh(seconds) {
    console.log(`Scheduling page refresh in ${seconds} seconds`);
    setTimeout(() => {
        console.log('Refreshing page...');
        window.location.reload();
    }, seconds * 1000);
}

// Simulate CPU spike
function simulateCpuSpike() {
    console.log('Simulating CPU spike');
    socket.emit('simulate issue', { issue_type: 'cpu' });
    
    // Visual feedback while waiting for server response
    cpuBtn.classList.add('active');
    updateStatus('Requesting CPU spike simulation...');
    
    // Schedule page refresh after 10 seconds
    schedulePageRefresh(10);
}

// Simulate memory spike
function simulateMemorySpike() {
    console.log('Simulating memory spike');
    socket.emit('simulate issue', { issue_type: 'memory' });
    
    // Visual feedback while waiting for server response
    memoryBtn.classList.add('active');
    updateStatus('Requesting memory spike simulation...');
    
    // Schedule page refresh after 10 seconds
    schedulePageRefresh(10);
}

// Reset simulation state
function resetSimulationState() {
    simulationActive = false;
    simulationType = null;
    cpuBtn.classList.remove('active');
    memoryBtn.classList.remove('active');
    cpuBtn.disabled = false;
    memoryBtn.disabled = false;
    monitoringVisual.classList.remove('cpu-spike', 'memory-spike');
}

// Update status message
function updateStatus(message) {
    statusElement.textContent = message;
    
    // Add animation
    statusElement.classList.add('status-update');
    setTimeout(() => {
        statusElement.classList.remove('status-update');
    }, 300);
}

// Check API status
function checkApiStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            console.log('API status:', data);
            
            // Update metric bars based on actual values
            const cpuPercentage = Math.min(data.cpu_usage, 100);
            const memoryPercentage = Math.min((data.memory_usage / 100000000) * 100, 100);
            
            // Only update if not in simulation mode
            if (!simulationActive) {
                cpuMetricFill.style.width = `${cpuPercentage}%`;
                memoryMetricFill.style.width = `${memoryPercentage}%`;
                
                // Check if there's a spike active from the API
                if (data.cpu_spike_active && simulationType !== 'cpu') {
                    simulationActive = true;
                    simulationType = 'cpu';
                    cpuBtn.classList.add('active');
                    cpuBtn.disabled = true;
                    memoryBtn.disabled = true;
                    monitoringVisual.classList.add('cpu-spike');
                    updateStatus('CPU spike detected. Agent is analyzing...');
                } else if (data.memory_spike_active && simulationType !== 'memory') {
                    simulationActive = true;
                    simulationType = 'memory';
                    memoryBtn.classList.add('active');
                    cpuBtn.disabled = true;
                    memoryBtn.disabled = true;
                    monitoringVisual.classList.add('memory-spike');
                    updateStatus('Memory spike detected. Agent is analyzing...');
                } else if (!data.cpu_spike_active && !data.memory_spike_active && simulationActive) {
                    resetSimulationState();
                    updateStatus('Resources returning to normal levels.');
                }
            }
        })
        .catch(error => {
            console.error('Error checking API status:', error);
            updateStatus('Error connecting to API');
        });
}

// Add CSS animation for status updates
const style = document.createElement('style');
style.textContent = `
    .status-update {
        animation: statusPulse 0.3s ease-in-out;
    }
    
    @keyframes statusPulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
`;
document.head.appendChild(style);
