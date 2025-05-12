import os
import json
import time
import requests
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# Initialize FastAPI app
app = FastAPI(title="Kubernetes MCP Server", description="MCP server for Kubernetes operations")

# Configuration
TEST_APP_URL = "http://test-app:8000"  # URL of the test application

# MCP Models
class MCPToolInput(BaseModel):
    """Base model for MCP tool inputs"""
    pass

class MCPToolOutput(BaseModel):
    """Base model for MCP tool outputs"""
    pass

class PodRestartInput(MCPToolInput):
    namespace: str = Field(default="default", description="Kubernetes namespace")
    pod_name: str = Field(..., description="Name of the pod to restart")

class PodRestartOutput(MCPToolOutput):
    success: bool
    message: str

class PodListInput(MCPToolInput):
    namespace: str = Field(default="default", description="Kubernetes namespace")
    label_selector: Optional[str] = Field(None, description="Label selector for filtering pods")

class PodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    ip: Optional[str] = None
    node: Optional[str] = None
    start_time: Optional[str] = None
    containers: List[str]

class PodListOutput(MCPToolOutput):
    pods: List[PodInfo]

class NodeListInput(MCPToolInput):
    label_selector: Optional[str] = Field(None, description="Label selector for filtering nodes")

class NodeInfo(BaseModel):
    name: str
    status: str
    roles: List[str]
    cpu_capacity: str
    memory_capacity: str
    pods: int

class NodeListOutput(MCPToolOutput):
    nodes: List[NodeInfo]

class LogsInput(MCPToolInput):
    namespace: str = Field(default="default", description="Kubernetes namespace")
    pod_name: str = Field(..., description="Name of the pod")
    container: Optional[str] = Field(None, description="Container name (if pod has multiple containers)")
    tail_lines: Optional[int] = Field(100, description="Number of lines to return from the end of the logs")

class LogsOutput(MCPToolOutput):
    logs: str

# Helper function to check if test app is available
def is_test_app_available():
    try:
        response = requests.get(f"{TEST_APP_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

# MCP Protocol Routes
@app.post("/mcp/tools/restart_pod", response_model=PodRestartOutput)
async def restart_pod(input_data: PodRestartInput):
    """Restart a pod by stopping any active simulations"""
    try:
        # Check if test app is available
        if not is_test_app_available():
            return PodRestartOutput(
                success=False,
                message="Test application is not available"
            )
        
        # Stop any active simulations
        response = requests.post(f"{TEST_APP_URL}/simulate/stop")
        if response.status_code == 200:
            return PodRestartOutput(
                success=True,
                message=f"Pod {input_data.pod_name} in namespace {input_data.namespace} restarted successfully"
            )
        else:
            return PodRestartOutput(
                success=False,
                message=f"Failed to restart pod: {response.text}"
            )
    except Exception as e:
        return PodRestartOutput(
            success=False,
            message=f"Failed to restart pod: {str(e)}"
        )

@app.post("/mcp/tools/list_pods", response_model=PodListOutput)
async def list_pods(input_data: PodListInput):
    """List pods based on test application status"""
    try:
        # Check if test app is available
        if not is_test_app_available():
            return PodListOutput(pods=[])
        
        # Get status from test app
        response = requests.get(f"{TEST_APP_URL}/status")
        if response.status_code != 200:
            return PodListOutput(pods=[])
        
        status = response.json()
        
        # Create pod info based on status
        pod_info = PodInfo(
            name="app-backend-5d8d9b7f9c-abcd1",
            namespace="default",
            status="Running",
            ip="10.244.0.5",
            node="kind-control-plane",
            start_time="2023-05-12T00:00:00Z",
            containers=["app-backend"]
        )
        
        return PodListOutput(pods=[pod_info])
    except Exception as e:
        print(f"Error listing pods: {str(e)}")
        return PodListOutput(pods=[])

@app.post("/mcp/tools/list_nodes", response_model=NodeListOutput)
async def list_nodes(input_data: NodeListInput):
    """List nodes in the cluster"""
    try:
        # Check if test app is available
        if not is_test_app_available():
            return NodeListOutput(nodes=[])
        
        # Create node info
        node_info = NodeInfo(
            name="kind-control-plane",
            status="Ready",
            roles=["control-plane"],
            cpu_capacity="4",
            memory_capacity="8Gi",
            pods=1
        )
        
        return NodeListOutput(nodes=[node_info])
    except Exception as e:
        print(f"Error listing nodes: {str(e)}")
        return NodeListOutput(nodes=[])

@app.post("/mcp/tools/get_logs", response_model=LogsOutput)
async def get_logs(input_data: LogsInput):
    """Get logs from the test application"""
    try:
        # Check if test app is available
        if not is_test_app_available():
            return LogsOutput(logs="Test application is not available")
        
        # Get status from test app
        response = requests.get(f"{TEST_APP_URL}/status")
        if response.status_code != 200:
            return LogsOutput(logs="Failed to get status from test application")
        
        status = response.json()
        
        # Generate logs based on status
        logs = f"Application logs for {input_data.pod_name}:\n"
        
        if status.get("cpu_spike_active"):
            logs += """
2023-05-12T12:00:01Z INFO  [app-backend] Starting application
2023-05-12T12:00:02Z INFO  [app-backend] Connected to database
2023-05-12T12:00:03Z INFO  [app-backend] Listening on port 8000
2023-05-12T12:01:01Z WARN  [app-backend] High CPU usage detected: 85%
2023-05-12T12:01:05Z ERROR [app-backend] CPU throttling detected
2023-05-12T12:01:10Z ERROR [app-backend] Request processing slowed down
2023-05-12T12:01:15Z ERROR [app-backend] Infinite loop detected in /api/process endpoint
2023-05-12T12:01:20Z ERROR [app-backend] Memory allocation failed
2023-05-12T12:01:25Z WARN  [app-backend] High CPU usage: 92%
2023-05-12T12:01:30Z ERROR [app-backend] Thread pool exhausted
"""
        elif status.get("memory_spike_active"):
            logs += """
2023-05-12T12:00:01Z INFO  [app-backend] Starting application
2023-05-12T12:00:02Z INFO  [app-backend] Connected to database
2023-05-12T12:00:03Z INFO  [app-backend] Listening on port 8000
2023-05-12T12:01:01Z WARN  [app-backend] High memory usage detected: 75%
2023-05-12T12:01:05Z ERROR [app-backend] Memory allocation failed
2023-05-12T12:01:10Z ERROR [app-backend] Garbage collection triggered
2023-05-12T12:01:15Z ERROR [app-backend] Out of memory error in /api/data endpoint
2023-05-12T12:01:20Z ERROR [app-backend] Memory leak detected
2023-05-12T12:01:25Z WARN  [app-backend] High memory usage: 88%
2023-05-12T12:01:30Z ERROR [app-backend] Application slowdown due to memory pressure
"""
        else:
            logs += """
2023-05-12T12:00:01Z INFO  [app-backend] Starting application
2023-05-12T12:00:02Z INFO  [app-backend] Connected to database
2023-05-12T12:00:03Z INFO  [app-backend] Listening on port 8000
2023-05-12T12:01:01Z INFO  [app-backend] Processing request /api/data
2023-05-12T12:01:02Z INFO  [app-backend] Request completed in 120ms
2023-05-12T12:01:05Z INFO  [app-backend] Processing request /api/users
2023-05-12T12:01:06Z INFO  [app-backend] Request completed in 85ms
"""
        
        return LogsOutput(logs=logs)
    except Exception as e:
        return LogsOutput(logs=f"Error getting logs: {str(e)}")

# MCP Schema Endpoints
@app.get("/mcp/schema")
async def get_schema():
    """Get the MCP schema for this server"""
    return {
        "name": "kubernetes-mcp",
        "version": "1.0.0",
        "description": "MCP server for Kubernetes operations",
        "tools": [
            {
                "name": "restart_pod",
                "description": "Restart a pod by deleting it (Kubernetes will recreate it)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "default": "default"},
                        "pod_name": {"type": "string"}
                    },
                    "required": ["pod_name"]
                }
            },
            {
                "name": "list_pods",
                "description": "List pods in a namespace",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "default": "default"},
                        "label_selector": {"type": "string"}
                    }
                }
            },
            {
                "name": "list_nodes",
                "description": "List nodes in the cluster",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "label_selector": {"type": "string"}
                    }
                }
            },
            {
                "name": "get_logs",
                "description": "Get logs from a pod",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "default": "default"},
                        "pod_name": {"type": "string"},
                        "container": {"type": "string"},
                        "tail_lines": {"type": "integer", "default": 100}
                    },
                    "required": ["pod_name"]
                }
            }
        ],
        "resources": []
    }

# Health check endpoint
@app.get("/health")
async def health():
    status = "ok" if is_test_app_available() else "degraded"
    return {"status": status}

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Kubernetes MCP Server",
        "version": "1.0.0",
        "description": "MCP server for Kubernetes operations",
        "schema_url": "/mcp/schema",
        "health_url": "/health",
        "test_app_available": is_test_app_available()
    }
