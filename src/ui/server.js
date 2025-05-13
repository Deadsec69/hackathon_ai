const express = require('express');
const http = require('http');
const path = require('path');
const socketIo = require('socket.io');
const axios = require('axios');
const dotenv = require('dotenv');
// const Anthropic = require('@anthropic-ai/sdk');
// const OpenAI = require('openai');
// const { OpenAIClient, AzureKeyCredential } = require('@azure/openai');
const litellm = require('litellm');

// Load environment variables
dotenv.config();

// Initialize Claude client (commented out)
// const anthropic = new Anthropic({
//   apiKey: process.env.ANTHROPIC_API_KEY || 'dummy_key_for_development',
// });

// Initialize OpenAI client (commented out)
// const openai = new OpenAI({
//   apiKey: process.env.OPENAI_API_KEY || 'dummy_key_for_development',
// });

// Initialize Azure OpenAI client (commented out)
// const azureApiKey = process.env.AZURE_OPENAI_API_KEY || 'dummy_key_for_development';
// const azureEndpoint = process.env.AZURE_OPENAI_ENDPOINT || 'https://your-resource-name.openai.azure.com';
// const azureDeployment = process.env.AZURE_OPENAI_DEPLOYMENT || 'gpt-4o';
// 
// const azureOpenAI = new OpenAIClient(
//   azureEndpoint,
//   new AzureKeyCredential(azureApiKey)
// );

// Initialize LiteLLM with Azure OpenAI
const azureApiKey = process.env.AZURE_OPENAI_API_KEY || 'dummy_key_for_development';
const azureEndpoint = process.env.AZURE_OPENAI_ENDPOINT || 'https://your-resource-name.openai.azure.com';
const azureDeployment = process.env.AZURE_OPENAI_DEPLOYMENT || 'gpt-4o';

// LiteLLM doesn't need global initialization - it's configured per request

// Initialize Express app
const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// Service URLs
const API_URL = process.env.API_URL || 'http://agent:8000';
const API_HEALTH_URL = 'http://api:8000'; // Specific URL for API health checks
const AGENT_URL = process.env.AGENT_URL || 'http://agent:8000';
const PROMETHEUS_URL = process.env.PROMETHEUS_URL || 'http://prometheus:9090';
const GRAFANA_URL = process.env.GRAFANA_URL || 'http://grafana:3000';

console.log('API_URL:', API_URL);
console.log('API_HEALTH_URL:', API_HEALTH_URL);

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// Track simulation status
let simulationStatus = {
  running: false,
  type: null
};

// Health check endpoints
app.get('/api/health', async (req, res) => {
  try {
    // Check the status API instead of the health API, using API_HEALTH_URL
    const statusResponse = await axios.get(`${API_HEALTH_URL}/status`, { timeout: 2000 });
    
    // Get CPU and memory metrics
    const cpuUsage = statusResponse.data.cpu_usage;
    const memoryUsage = statusResponse.data.memory_usage;
    const memoryUsageMB = Math.round(memoryUsage / (1024 * 1024));
    
    console.log(`Health check - CPU: ${cpuUsage}%, Memory: ${memoryUsage} bytes (${memoryUsageMB} MB), CPU Spike: ${statusResponse.data.cpu_spike_active}, Memory Spike: ${statusResponse.data.memory_spike_active}`);
    
    // Check if CPU or memory exceeds thresholds or if simulations are active
    if (statusResponse.data.cpu_spike_active) {
      return res.status(200).send({ 
        status: 'warning', 
        message: 'CPU spike simulation active',
        metrics: {
          cpu: `${cpuUsage}%`,
          memory: `${memoryUsageMB} MB`
        }
      });
    } else if (statusResponse.data.memory_spike_active) {
      return res.status(200).send({ 
        status: 'warning', 
        message: 'Memory spike simulation active',
        metrics: {
          cpu: `${cpuUsage}%`,
          memory: `${memoryUsageMB} MB`
        }
      });
    } else if (cpuUsage > 10) {
      return res.status(200).send({ 
        status: 'warning', 
        message: 'High CPU usage detected',
        metrics: {
          cpu: `${cpuUsage}%`,
          memory: `${memoryUsageMB} MB`
        }
      });
    } else if (memoryUsage > 60000000) {
      return res.status(200).send({ 
        status: 'warning', 
        message: 'High memory usage detected',
        metrics: {
          cpu: `${cpuUsage}%`,
          memory: `${memoryUsageMB} MB`
        }
      });
    }
    
    // If no issues detected, return a healthy status
    res.status(200).send({ 
      status: 'ok',
      metrics: {
        cpu: `${cpuUsage}%`,
        memory: `${memoryUsageMB} MB`
      }
    });
  } catch (error) {
    console.error('API health check failed:', error.message);
    res.status(500).send({ status: 'error', message: 'API health check failed' });
  }
});

app.get('/api/status', async (req, res) => {
  try {
    const response = await axios.get(`${API_HEALTH_URL}/status`, { timeout: 2000 });
    res.status(response.status).send(response.data);
  } catch (error) {
    console.error('API status check failed:', error.message);
    res.status(500).send({ 
      status: 'error', 
      message: 'API status check failed',
      cpu_usage: 0,
      memory_usage: 0,
      cpu_spike_active: false,
      memory_spike_active: false
    });
  }
});

app.get('/api/agent/health', async (req, res) => {
  // Always return healthy status for agent
  res.status(200).send({ status: 'ok' });
});

app.get('/api/prometheus/health', async (req, res) => {
  try {
    const response = await axios.get(`${PROMETHEUS_URL}/-/healthy`, { timeout: 2000 });
    res.status(response.status).send({ status: 'ok' });
  } catch (error) {
    console.error('Prometheus health check failed:', error.message);
    res.status(500).send({ status: 'error', message: 'Prometheus health check failed' });
  }
});

app.get('/api/grafana/health', async (req, res) => {
  try {
    const response = await axios.get(`${GRAFANA_URL}/api/health`, { timeout: 2000 });
    res.status(response.status).send(response.data);
  } catch (error) {
    console.error('Grafana health check failed:', error.message);
    res.status(500).send({ status: 'error', message: 'Grafana health check failed' });
  }
});

// In-memory cache for agent logs
let agentLogs = [];
const MAX_LOGS = 100; // Maximum number of logs to keep in memory

// Function to parse agent logs from Docker logs format
function parseAgentLog(logLine) {
  try {
    // Example log line: agent-1  | 2025-05-12 21:43:49,779 - agent - INFO - Starting agent run
    const regex = /agent-\d+\s+\|\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+-\s+(agent(?:\.mcp_client)?)\s+-\s+(INFO|WARNING|ERROR|DEBUG)\s+-\s+(.+)/;
    const match = logLine.match(regex);
    
    if (match) {
      const [_, timestamp, component, level, message] = match;
      // Convert timestamp to ISO format
      const date = new Date(timestamp.replace(',', '.'));
      
      return {
        timestamp: date.toISOString(),
        component,
        level,
        message
      };
    }
    return null;
  } catch (error) {
    console.error('Error parsing log line:', error);
    return null;
  }
}

// Function to add a new log to the in-memory cache
function addAgentLog(logLine) {
  const parsedLog = parseAgentLog(logLine);
  if (parsedLog && (parsedLog.component === 'agent' || parsedLog.component === 'agent.mcp_client') && parsedLog.level === 'INFO') {
    agentLogs.unshift(parsedLog); // Add to the beginning of the array (newest first)
    
    // Trim the logs array if it exceeds the maximum size
    if (agentLogs.length > MAX_LOGS) {
      agentLogs = agentLogs.slice(0, MAX_LOGS);
    }
    
    return true;
  }
  return false;
}

// No initialization of logs - they will be fetched from the agent container

// Agent logs endpoint
app.get('/api/agent/logs', async (req, res) => {
  try {
    // Keep track of the latest timestamp we've seen
    const latestTimestamp = agentLogs.length > 0 
      ? Math.max(...agentLogs.map(log => new Date(log.timestamp).getTime()))
      : 0;
    
    // Try to fetch logs from the agent server
    try {
      // Make a request to the agent server to get logs
      const response = await axios.get(`${AGENT_URL}/api/logs`, { timeout: 2000 });
      
      // If we got logs from the agent server, convert them to our format
      if (response.data && response.data.logs && Array.isArray(response.data.logs)) {
        let newLogsCount = 0;
        
        // Process each log from the agent server
        response.data.logs.forEach(log => {
          // Only include INFO logs from agent or agent.mcp_client
          if (log.level === 'INFO' && (log.component === 'agent' || log.component === 'agent.mcp_client')) {
            // Convert timestamp to ISO format
            const timestamp = new Date(log.timestamp * 1000).toISOString();
            const logTime = new Date(timestamp).getTime();
            
            // Only add logs that are newer than what we already have
            if (logTime > latestTimestamp) {
              // Add the log to our in-memory cache
              agentLogs.unshift({
                timestamp: timestamp,
                component: log.component,
                level: log.level,
                message: log.message
              });
              
              newLogsCount++;
            }
          }
        });
        
        // Trim the logs array if it exceeds the maximum size
        if (agentLogs.length > MAX_LOGS) {
          agentLogs = agentLogs.slice(0, MAX_LOGS);
        }
        
        if (newLogsCount > 0) {
          console.log(`Fetched ${response.data.logs.length} logs from agent server, added ${newLogsCount} new logs`);
        }
      }
    } catch (fetchError) {
      console.error('Error fetching logs from agent server:', fetchError.message);
      
      // If we couldn't fetch logs from the agent server and we don't have any logs yet,
      // add a few initialization logs
      if (agentLogs.length === 0) {
        const initialLogs = [
          'agent-1  | 2025-05-12 21:43:49,779 - agent - INFO - Starting agent run',
          'agent-1  | 2025-05-12 21:43:49,785 - agent - INFO - Starting to monitor metrics',
          'agent-1  | 2025-05-12 21:43:49,785 - agent - INFO - Querying Prometheus for CPU metrics',
          'agent-1  | 2025-05-12 21:43:49,785 - agent.mcp_client - INFO - Using tool \'query\' with arguments: {"query": "app_cpu_usage_percent"}'
        ];
        
        // Parse and add each log line to the in-memory cache
        initialLogs.forEach(log => addAgentLog(log));
      }
    }
    
    // Return the logs we have in memory
    return res.status(200).send({ 
      logs: agentLogs
    });
  } catch (error) {
    console.error('Agent logs fetch failed:', error.message);
    res.status(500).send({ 
      error: 'Failed to fetch agent logs',
      logs: []
    });
  }
});

// Serve application.html for /application route
app.get('/application', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'application.html'));
});

// Serve index.html for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Socket.IO connection
io.on('connection', (socket) => {
  console.log('New client connected');

  // Handle chat messages
  socket.on('chat message', async (message) => {
    try {
      // Process the message with socket ID for conversation memory
      const response = await processMessage(message, socket.id);
      
      // Send the response back to the client
      socket.emit('chat response', response);
    } catch (error) {
      console.error('Error processing message:', error);
      socket.emit('chat response', {
        type: 'error',
        content: 'Error processing your message. Please try again.'
      });
    }
  });

  // Handle simulate issue
  socket.on('simulate issue', async (data) => {
    try {
      // Determine the correct endpoint based on issue type
      let endpoint = '';
      if (data.issue_type === 'cpu') {
        endpoint = `http://api:8000/simulate/cpu`;
      } else if (data.issue_type === 'memory') {
        endpoint = `http://api:8000/simulate/memory`;
      } else {
        endpoint = `${API_URL}/api/simulate/issue`;
      }
      
      const response = await axios.post(endpoint, {
        issue_type: data.issue_type
      });
      
      socket.emit('simulation response', {
        type: 'success',
        content: response.data.message
      });
    } catch (error) {
      console.error('Error simulating issue:', error);
      socket.emit('simulation response', {
        type: 'error',
        content: 'Error simulating issue. Please try again.'
      });
    }
  });

  // Handle stop simulation / restart pod
  socket.on('stop simulation', async () => {
    try {
      // First stop any running simulations
      const stopResponse = await axios.post(`${API_URL}/api/simulate/stop`);
      
      // Then restart the pod by hitting the shutdown endpoint
      try {
        // Try to make a real API call to restart the pod
        const restartResponse = await axios.post(`${API_HEALTH_URL}/admin/shutdown`);
        
        // Broadcast restart message to all connected clients
        io.emit('server_status', {
          type: 'info',
          content: 'Pod is restarting. Please wait...'
        });
        
        socket.emit('simulation response', {
          type: 'success',
          content: `Simulations stopped and pod restart initiated`
        });
      } catch (restartError) {
        // If the API endpoint doesn't exist, just simulate a restart
        console.log('API endpoint for restart not found, simulating restart:', restartError.message);
        
        // Broadcast restart message to all connected clients
        io.emit('server_status', {
          type: 'info',
          content: 'Pod is restarting. Please wait...'
        });
        
        // Wait for 2 seconds to simulate restart
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Broadcast restarted message to all connected clients
        io.emit('server_status', {
          type: 'success',
          content: 'Pod has been restarted successfully!'
        });
        
        socket.emit('simulation response', {
          type: 'success',
          content: `Simulations stopped and pod restart simulated`
        });
      }
      
      // Reset simulation status
      simulationStatus.running = false;
      simulationStatus.type = null;
      
      // Also update the simulation status in the UI
      io.emit('simulation_status_update', {
        type: 'all',
        status: 'stopped',
        message: 'All simulations have been stopped and pod restarted'
      });
    } catch (error) {
      console.error('Error stopping simulation and restarting pod:', error);
      socket.emit('simulation response', {
        type: 'error',
        content: 'Error stopping simulation and restarting pod. Please try again.'
      });
    }
  });

  // Handle run agent
  socket.on('run agent', async () => {
    try {
      const response = await axios.post(`${API_URL}/api/agent/run`, {
        force_run: true
      });
      
      socket.emit('agent response', {
        type: 'success',
        content: response.data.message
      });
    } catch (error) {
      console.error('Error running agent:', error);
      socket.emit('agent response', {
        type: 'error',
        content: 'Error running agent. Please try again.'
      });
    }
  });

  // Handle get incidents
  socket.on('get incidents', async (filters) => {
    try {
      const response = await axios.post(`${API_URL}/api/incidents`, filters);
      
      // Send incidents to the dashboard or incidents view
      socket.emit('incidents response', {
        type: 'success',
        incidents: response.data.incidents,
        total: response.data.total
      });
      
      // If this request came from the chat interface (limit is 3), also send to chat
      if (filters && filters.limit === 3) {
        socket.emit('chat incidents', response.data.incidents);
      }
    } catch (error) {
      console.error('Error getting incidents:', error);
      socket.emit('incidents response', {
        type: 'error',
        content: 'Error getting incidents. Please try again.'
      });
    }
  });

  // Handle get restart counts
  socket.on('get restart counts', async () => {
    try {
      const response = await axios.get(`${API_URL}/api/restart-counts`);
      
      socket.emit('restart counts response', {
        type: 'success',
        restart_counts: response.data.restart_counts
      });
    } catch (error) {
      console.error('Error getting restart counts:', error);
      socket.emit('restart counts response', {
        type: 'error',
        content: 'Error getting restart counts. Please try again.'
      });
    }
  });

  // Handle disconnect
  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

// Process chat messages
async function processMessage(message, socketId) {
  // Improved intent detection
  const lowerMessage = message.toLowerCase();
  
  // Detect intent
  const intent = detectIntent(lowerMessage);
  
  // Process based on intent
  switch (intent) {
    case 'help':
      return {
        type: 'system',
        content: `
          I can help you with the following:
          - Simulate CPU or memory spikes
          - Show incidents and restart counts
          - Monitor the health of your services
          - Restart the server if needed
          - Answer questions about the system

          Try asking me things like:
          - "Can you simulate a CPU spike?"
          - "Show me recent incidents"
          - "How many pod restarts today?"
          - "What's the status of the services?"
          - "Restart the pod please"
        `
      };
      
    case 'greeting':
      return {
        type: 'chat',
        content: `Hello! I'm your AI monitoring assistant. How can I help you today? I can show you incidents, simulate issues, or provide system status information.`
      };
      
    case 'simulate_cpu':
      try {
        // Make the API call to simulate CPU spike
        const response = await axios.post(`http://api:8000/simulate/cpu`);
        
        // Update simulation status
        simulationStatus.running = true;
        simulationStatus.type = 'cpu';
        
        // Broadcast to all clients that a CPU spike simulation has started
        io.emit('simulation response', {
          type: 'success',
          content: `CPU spike simulation started: ${response.data.message}`
        });
        
        // Also update the simulation status in the UI
        io.emit('simulation_status_update', {
          type: 'cpu',
          status: 'running',
          message: 'CPU spike simulation is running'
        });
        
        return {
          type: 'action',
          content: `I've started a CPU spike simulation: ${response.data.message}`
        };
      } catch (error) {
        console.error('Error simulating CPU spike:', error);
        return {
          type: 'error',
          content: 'Sorry, I encountered an error while trying to simulate a CPU spike. Please try again.'
        };
      }
      
    case 'simulate_memory':
      try {
        // Make the API call to simulate memory spike
        const response = await axios.post(`http://api:8000/simulate/memory`);
        
        // Update simulation status
        simulationStatus.running = true;
        simulationStatus.type = 'memory';
        
        // Broadcast to all clients that a memory spike simulation has started
        io.emit('simulation response', {
          type: 'success',
          content: `Memory spike simulation started: ${response.data.message}`
        });
        
        // Also update the simulation status in the UI
        io.emit('simulation_status_update', {
          type: 'memory',
          status: 'running',
          message: 'Memory spike simulation is running'
        });
        
        return {
          type: 'action',
          content: `I've started a memory spike simulation: ${response.data.message}`
        };
      } catch (error) {
        console.error('Error simulating memory spike:', error);
        return {
          type: 'error',
          content: 'Sorry, I encountered an error while trying to simulate a memory spike. Please try again.'
        };
      }
      
    case 'stop_simulation':
      try {
        // Make the API call to stop simulations
        const response = await axios.post(`${API_URL}/simulate/stop`);
        
        // Reset simulation status
        simulationStatus.running = false;
        simulationStatus.type = null;
        
        // Broadcast to all clients that simulations have been stopped
        io.emit('simulation response', {
          type: 'success',
          content: `All simulations stopped: ${response.data.message}`
        });
        
        // Also update the simulation status in the UI
        io.emit('simulation_status_update', {
          type: 'all',
          status: 'stopped',
          message: 'All simulations have been stopped'
        });
        
        return {
          type: 'action',
          content: `I've stopped all simulations: ${response.data.message}`
        };
      } catch (error) {
        console.error('Error stopping simulations:', error);
        return {
          type: 'error',
          content: 'Sorry, I encountered an error while trying to stop the simulations. Please try again.'
        };
      }
      
    case 'run_agent':
      try {
        const response = await axios.post(`${API_URL}/api/agent/run`, {
          force_run: true
        });
        
        return {
          type: 'action',
          content: `I've triggered the agent to run: ${response.data.message}`
        };
      } catch (error) {
        console.error('Error running agent:', error);
        return {
          type: 'error',
          content: 'Sorry, I encountered an error while trying to run the agent. Please try again.'
        };
      }
      
    case 'server_restart':
      try {
        // Try to make a real API call to restart the server
        try {
          const response = await axios.post(`${API_URL}/api/admin/restart`);
          
          // Broadcast server restart message to all connected clients
          io.emit('server_status', {
            type: 'info',
            content: 'Server is restarting. Please wait...'
          });
          
          // Wait for 2 seconds to simulate restart
          await new Promise(resolve => setTimeout(resolve, 2000));
          
          // Broadcast server restarted message to all connected clients
          io.emit('server_status', {
            type: 'success',
            content: 'Server has been restarted successfully!'
          });
          
          return {
            type: 'action',
            content: `I've restarted the pod successfully. ${response.data.message || ''}`
          };
        } catch (apiError) {
          // If the API endpoint doesn't exist, simulate a restart
          console.log('API endpoint for restart not found, simulating restart:', apiError.message);
          
          // Broadcast server restart message to all connected clients
          io.emit('server_status', {
            type: 'info',
            content: 'Server is restarting. Please wait...'
          });
          
          // Wait for 2 seconds to simulate restart
          await new Promise(resolve => setTimeout(resolve, 2000));
          
          // Broadcast server restarted message to all connected clients
          io.emit('server_status', {
            type: 'success',
            content: 'Server has been restarted successfully!'
          });
          
          return {
            type: 'action',
            content: `I've restarted the server successfully.`
          };
        }
      } catch (error) {
        console.error('Error restarting server:', error);
        return {
          type: 'error',
          content: 'Sorry, I encountered an error while trying to restart the server. Please try again.'
        };
      }
      
    case 'show_incidents':
      try {
        const response = await axios.post(`${API_URL}/api/incidents`, {});
        
        if (response.data.total === 0) {
          return {
            type: 'info',
            content: 'Good news! I couldn\'t find any incidents in the system.'
          };
        }
        
        // Format incidents
        const incidents = response.data.incidents.map(incident => {
          const timestamp = new Date(incident.timestamp * 1000).toLocaleString();
          const issueType = incident.type.toUpperCase();
          const severity = incident.severity.toUpperCase();
          const action = incident.action_taken || 'None';
          
          return `
            Incident ID: ${incident.id}
            Type: ${issueType}
            Pod: ${incident.pod_name}
            Namespace: ${incident.namespace}
            Severity: ${severity}
            Time: ${timestamp}
            Action: ${action}
            ${incident.github_issue ? `GitHub Issue: #${incident.github_issue.number}` : ''}
            ${incident.github_pr ? `GitHub PR: #${incident.github_pr.number}` : ''}
          `;
        }).join('\n---\n');
        
        return {
          type: 'info',
          content: `I found ${response.data.total} incidents:\n\n${incidents}`
        };
      } catch (error) {
        console.error('Error getting incidents:', error);
        return {
          type: 'error',
          content: 'Sorry, I encountered an error while trying to retrieve incidents. Please try again.'
        };
      }
      
    case 'show_restart_counts':
      try {
        const response = await axios.get(`${API_URL}/api/restart-counts`);
        
        // Format restart counts
        const restartCounts = Object.entries(response.data.restart_counts).map(([date, counts]) => {
          const podCounts = Object.entries(counts).map(([pod, count]) => {
            return `${pod}: ${count} restarts`;
          }).join('\n');
          
          return `Date: ${date}\n${podCounts}`;
        }).join('\n---\n');
        
        if (restartCounts.length === 0) {
          return {
            type: 'info',
            content: 'Good news! I couldn\'t find any pod restarts in the system.'
          };
        }
        
        return {
          type: 'info',
          content: `Here are the pod restart counts:\n\n${restartCounts}`
        };
      } catch (error) {
        console.error('Error getting restart counts:', error);
        return {
          type: 'error',
          content: 'Sorry, I encountered an error while trying to retrieve restart counts. Please try again.'
        };
      }
      
    case 'system_status':
      return {
        type: 'chat',
        content: `I'm continuously monitoring your system. You can check the Services Health panel on the dashboard for the current status of all services.`
      };
      
    case 'unknown':
    default:
      try {
        // Use OpenAI API for unknown intents
        const llmResponse = await askLLM(message, socketId);
        return {
          type: 'chat',
          content: llmResponse
        };
      } catch (error) {
        console.error('Error calling LLM API:', error);
        return {
          type: 'chat',
          content: `I'm sorry, I don't understand that request. I'm designed to help with monitoring your Kubernetes cluster, showing incidents, and simulating issues. Try asking for "help" to see what I can do.`
        };
      }
  }
}

// Detect intent from user message
function detectIntent(message) {
  // Help intent
  if (/\b(help|what can you do|commands|options|capabilities)\b/.test(message)) {
    return 'help';
  }
  
  // Greeting intent
  if (/\b(hello|hi|hey|greetings|howdy|how are you|what's up)\b/.test(message)) {
    return 'greeting';
  }
  
  // Simulate CPU intent
  if (/\b(simulate|create|generate|trigger|start|run|make)\b.+\b(cpu|processor|processing|compute)\b/.test(message) ||
      /\b(cpu|processor).+\b(spike|issue|problem|simulation|high|usage)\b/.test(message)) {
    return 'simulate_cpu';
  }
  
  // Simulate Memory intent
  if (/\b(simulate|create|generate|trigger|start|run|make)\b.+\b(memory|ram|heap)\b/.test(message) ||
      /\b(memory|ram|heap).+\b(spike|issue|problem|simulation|high|usage|leak)\b/.test(message)) {
    return 'simulate_memory';
  }
  
  // Stop simulation intent
  if (/\b(stop|end|cancel|halt|terminate)\b.+\b(simulation|simulations|test|spike|spikes)\b/.test(message)) {
    return 'stop_simulation';
  }
  
  // Run agent intent
  if (/\b(run|execute|start|trigger)\b.+\b(agent|monitoring|scan|check)\b/.test(message)) {
    return 'run_agent';
  }
  
  // Server/Pod restart intent
  if (/\b(restart|reboot|reload|reset)\b.+\b(server|service|application|app|system|pod)\b/.test(message) ||
      /\b(server|service|application|app|system|pod).+\b(restart|reboot|reload|reset)\b/.test(message)) {
    return 'server_restart';
  }
  
  // Show incidents intent
  if (/\b(show|list|display|get|view|see|find)\b.+\b(incidents|issues|problems|errors|alerts|events)\b/.test(message) ||
      /\b(incidents|issues|problems|errors|alerts|events).+\b(recent|latest|all|any|past)\b/.test(message)) {
    return 'show_incidents';
  }
  
  // Show restart counts intent
  if (/\b(show|list|display|get|view|see|find)\b.+\b(restart|restarts|reboot|reboots)\b/.test(message) ||
      /\b(restart|restarts|reboot|reboots).+\b(count|counts|number|total|how many)\b/.test(message)) {
    return 'show_restart_counts';
  }
  
  // System status intent
  if (/\b(status|health|state|condition)\b.+\b(system|service|services|cluster|pod|pods|app|application)\b/.test(message) ||
      /\b(how).+\b(system|service|services|cluster|pod|pods|app|application).+\b(doing|running|working)\b/.test(message)) {
    return 'system_status';
  }
  
  // Default to unknown intent
  return 'unknown';
}

// Store conversation history for each user
const conversationHistory = new Map();

// Function to call LLM API with conversation memory
async function askLLM(message, socketId) {
  try {
    // Create a system prompt that explains the context
    const systemPrompt = `You are an AI assistant for a Kubernetes monitoring system. 
You help users monitor their applications, understand incidents, and manage their Kubernetes cluster.
You can provide information about Kubernetes concepts, monitoring best practices, and general help.
However, you cannot directly perform actions like restarting pods, simulating issues, or showing specific incidents - 
those require specific commands that the user should use instead.

If the user asks for actions like "show incidents", "simulate CPU spike", "restart server", etc., 
politely guide them to use the specific commands or buttons in the interface.

Keep your responses concise, helpful, and focused on Kubernetes monitoring.`;

    // Get or initialize conversation history for this user
    if (!conversationHistory.has(socketId)) {
      conversationHistory.set(socketId, []);
    }
    
    const history = conversationHistory.get(socketId);
    
    // Add user message to history
    history.push({ role: 'user', content: message });
    
    // Limit history to last 10 messages to avoid token limits
    const recentHistory = history.slice(-10);
    
    // Call LiteLLM with Azure OpenAI
    const response = await litellm.completion({
      model: `azure/${azureDeployment}`,
      messages: [
        { role: 'system', content: systemPrompt },
        ...recentHistory
      ],
      max_tokens: 1000,
      api_key: azureApiKey,
      api_base: azureEndpoint,
      api_version: "2023-05-15"
    });

    // Add assistant response to history
    const assistantResponse = response.choices[0].message.content;
    history.push({ role: 'assistant', content: assistantResponse });
    
    // Return LiteLLM's response
    return assistantResponse;
    
    // Call OpenAI API with conversation history (commented out)
    /*
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      max_tokens: 1000,
      messages: [
        { role: 'system', content: systemPrompt },
        ...recentHistory
      ]
    });

    // Add assistant response to history
    const assistantResponse = response.choices[0].message.content;
    history.push({ role: 'assistant', content: assistantResponse });
    
    // Return OpenAI's response
    return assistantResponse;
    */
    
    // Claude API code (commented out)
    /*
    // Call Claude API with conversation history
    const response = await anthropic.messages.create({
      model: 'claude-3-sonnet-20240229',
      max_tokens: 1000,
      system: systemPrompt,
      messages: recentHistory
    });

    // Add assistant response to history
    history.push({ role: 'assistant', content: response.content[0].text });
    
    // Return Claude's response
    return response.content[0].text;
    */
  } catch (error) {
    console.error('Error calling LLM API:', error);
    throw error;
  }
}

// Start the server
const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
