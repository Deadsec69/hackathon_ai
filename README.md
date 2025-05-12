# AI Agent for Kubernetes Monitoring and Self-Healing

This project demonstrates an AI agent system that monitors applications running on Kubernetes, performs health checks, and implements automated fixes.

## Architecture

The system consists of the following components:

1. **Test Application**: A simple application that can simulate CPU and memory spikes
2. **Monitoring Stack**: Prometheus and Grafana for metrics collection and visualization
3. **MCP Servers**: Model Context Protocol servers for Kubernetes, Prometheus, Grafana, and GitHub
4. **AI Agent**: LangGraph-based agent using GPT-4o for decision making
5. **Chat Interface**: Web UI for interacting with the agent and simulating issues

## Workflow

1. User simulates CPU/memory spike via chat interface
2. Spike is logged in Grafana/Prometheus
3. AI agent detects the spike
4. Agent restarts the pod (up to 10 times per day)
5. Agent creates a GitHub issue
6. After 10 restarts in a day, agent analyzes code and creates a PR with suggested fixes

## Directory Structure

```
.
├── README.md
├── docker-compose.yml
├── requirements.txt
└── src/
    ├── agent/           # AI agent implementation using LangGraph
    ├── api/             # FastAPI backend for the chat interface
    ├── kubernetes/      # Kubernetes configuration files
    ├── mcp/             # MCP server implementations/configurations
    ├── monitoring/      # Prometheus and Grafana configuration
    └── ui/              # Web UI for the chat interface
```

## Setup Instructions

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Start the local environment:
   ```
   docker-compose up -d
   ```

3. Access the chat interface:
   ```
   http://localhost:8080
   ```

## Features

- Simulate CPU and memory spikes
- View real-time metrics in Grafana
- Automatic pod restarts for issue remediation
- GitHub issue creation for incident tracking
- Intelligent PR creation for persistent issues
- Incident history and query capabilities
