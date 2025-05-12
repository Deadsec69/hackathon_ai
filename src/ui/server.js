const express = require('express');
const http = require('http');
const path = require('path');
const socketIo = require('socket.io');
const axios = require('axios');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

// Initialize Express app
const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// API URL
const API_URL = process.env.API_URL || 'http://api:8000';

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// Serve index.html for all routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Socket.IO connection
io.on('connection', (socket) => {
  console.log('New client connected');

  // Handle chat messages
  socket.on('chat message', async (message) => {
    try {
      // Process the message
      const response = await processMessage(message);
      
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
      const response = await axios.post(`${API_URL}/api/simulate/issue`, {
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

  // Handle stop simulation
  socket.on('stop simulation', async () => {
    try {
      const response = await axios.post(`${API_URL}/api/simulate/stop`);
      
      socket.emit('simulation response', {
        type: 'success',
        content: response.data.message
      });
    } catch (error) {
      console.error('Error stopping simulation:', error);
      socket.emit('simulation response', {
        type: 'error',
        content: 'Error stopping simulation. Please try again.'
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
      
      socket.emit('incidents response', {
        type: 'success',
        incidents: response.data.incidents,
        total: response.data.total
      });
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
async function processMessage(message) {
  // Simple keyword-based processing
  const lowerMessage = message.toLowerCase();
  
  if (lowerMessage.includes('help')) {
    return {
      type: 'system',
      content: `
        Available commands:
        - "simulate cpu" - Simulate a CPU spike
        - "simulate memory" - Simulate a memory spike
        - "stop simulation" - Stop all simulations
        - "run agent" - Run the agent manually
        - "show incidents" - Show all incidents
        - "show restart counts" - Show restart counts
      `
    };
  } else if (lowerMessage.includes('simulate cpu')) {
    try {
      const response = await axios.post(`${API_URL}/api/simulate/issue`, {
        issue_type: 'cpu'
      });
      
      return {
        type: 'action',
        content: `Simulating CPU spike: ${response.data.message}`
      };
    } catch (error) {
      console.error('Error simulating CPU spike:', error);
      return {
        type: 'error',
        content: 'Error simulating CPU spike. Please try again.'
      };
    }
  } else if (lowerMessage.includes('simulate memory')) {
    try {
      const response = await axios.post(`${API_URL}/api/simulate/issue`, {
        issue_type: 'memory'
      });
      
      return {
        type: 'action',
        content: `Simulating memory spike: ${response.data.message}`
      };
    } catch (error) {
      console.error('Error simulating memory spike:', error);
      return {
        type: 'error',
        content: 'Error simulating memory spike. Please try again.'
      };
    }
  } else if (lowerMessage.includes('stop simulation')) {
    try {
      const response = await axios.post(`${API_URL}/api/simulate/stop`);
      
      return {
        type: 'action',
        content: `Stopping simulations: ${response.data.message}`
      };
    } catch (error) {
      console.error('Error stopping simulations:', error);
      return {
        type: 'error',
        content: 'Error stopping simulations. Please try again.'
      };
    }
  } else if (lowerMessage.includes('run agent')) {
    try {
      const response = await axios.post(`${API_URL}/api/agent/run`, {
        force_run: true
      });
      
      return {
        type: 'action',
        content: `Running agent: ${response.data.message}`
      };
    } catch (error) {
      console.error('Error running agent:', error);
      return {
        type: 'error',
        content: 'Error running agent. Please try again.'
      };
    }
  } else if (lowerMessage.includes('show incidents')) {
    try {
      const response = await axios.post(`${API_URL}/api/incidents`, {});
      
      if (response.data.total === 0) {
        return {
          type: 'info',
          content: 'No incidents found.'
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
        content: `Found ${response.data.total} incidents:\n\n${incidents}`
      };
    } catch (error) {
      console.error('Error getting incidents:', error);
      return {
        type: 'error',
        content: 'Error getting incidents. Please try again.'
      };
    }
  } else if (lowerMessage.includes('show restart counts')) {
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
          content: 'No restart counts found.'
        };
      }
      
      return {
        type: 'info',
        content: `Restart counts:\n\n${restartCounts}`
      };
    } catch (error) {
      console.error('Error getting restart counts:', error);
      return {
        type: 'error',
        content: 'Error getting restart counts. Please try again.'
      };
    }
  } else {
    // Use OpenAI to generate a response
    return {
      type: 'chat',
      content: `I'm an AI agent monitoring your Kubernetes cluster. I can help you with monitoring, detecting issues, and taking remedial actions. Try asking me to "simulate cpu" or "show incidents".`
    };
  }
}

// Start the server
const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
