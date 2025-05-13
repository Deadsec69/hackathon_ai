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
TEST_APP_URL = "http://api:8000"  # URL of the test application (using the api service)

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

class GetAppCodeInput(MCPToolInput):
    pod_name: str = Field(..., description="Name of the pod")
    namespace: str = Field(default="default", description="Kubernetes namespace")

class GetAppCodeOutput(MCPToolOutput):
    code: str

# Helper function to check if test app is available
def is_test_app_available():
    try:
        response = requests.get(f"{TEST_APP_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

# MCP Protocol Routes
import subprocess

@app.post("/mcp/tools/restart_pod", response_model=PodRestartOutput)
async def restart_pod(input_data: PodRestartInput):
    """Restart a pod by actually restarting the Docker container"""
    try:
        # Check if test app is available
        # if not is_test_app_available():
        #     return PodRestartOutput(
        #         success=False,
        #         message="Test application is not available"
        #     )
        
        print(f"[Kubernetes MCP] Restarting pod {input_data.pod_name} in namespace {input_data.namespace}")
        print(f"[Kubernetes MCP] In a real K8s environment, this would terminate and recreate the pod")
        print(f"[Kubernetes MCP] In this simulation, we'll actually restart the Docker container")
        
        # First try to stop any active simulations
        try:
            response = requests.post(f"{TEST_APP_URL}/simulate/stop", timeout=2)
            print(f"[Kubernetes MCP] Sent stop signal to simulations: {response.status_code}")
        except Exception as e:
            print(f"[Kubernetes MCP] Failed to send stop signal: {str(e)}")
        
        # Call the shutdown endpoint to force the container to exit and restart
        try:
            print(f"[Kubernetes MCP] Calling shutdown endpoint to force container restart")
            shutdown_response = requests.post(f"{TEST_APP_URL}/admin/shutdown", timeout=2)
            print(f"[Kubernetes MCP] Shutdown response: {shutdown_response.status_code}")
            
            # Wait for the container to go down and come back up
            print(f"[Kubernetes MCP] Waiting for API container to restart")
            
            # First wait for it to go down
            down = False
            for i in range(5):  # Try for 5 seconds
                try:
                    time.sleep(1)
                    health_check = requests.get(f"{TEST_APP_URL}/health", timeout=1)
                    # If we get here, it's still up
                except:
                    # If we get an exception, it's down
                    down = True
                    print(f"[Kubernetes MCP] API container is down after {i+1} seconds")
                    break
            
            if not down:
                print(f"[Kubernetes MCP] API container did not go down after 5 seconds")
            
            # Now wait for it to come back up
            max_retries = 15  # Wait up to 15 seconds for it to come back
            for i in range(max_retries):
                try:
                    time.sleep(1)
                    health_check = requests.get(f"{TEST_APP_URL}/health", timeout=1)
                    if health_check.status_code == 200:
                        print(f"[Kubernetes MCP] API container is back up after {i+1} seconds")
                        break
                except:
                    if i == max_retries - 1:
                        print(f"[Kubernetes MCP] API container did not come back up after {max_retries} seconds")
            
            return PodRestartOutput(
                success=True,
                message=f"Pod {input_data.pod_name} in namespace {input_data.namespace} restarted successfully"
            )
        except subprocess.CalledProcessError as e:
            print(f"[Kubernetes MCP] Docker restart command failed: {e.stderr}")
            return PodRestartOutput(
                success=False,
                message=f"Failed to restart pod: {e.stderr}"
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
        # if not is_test_app_available():
        #     return LogsOutput(logs="Test application is not available")
        
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

@app.post("/mcp/tools/get_app_code", response_model=GetAppCodeOutput)
async def get_app_code(input_data: GetAppCodeInput):
    """Get application code from the pod"""
    try:
        # Check if test app is available
        # if not is_test_app_available():
        #     return GetAppCodeOutput(code="Test application is not available")
        
        # In a real implementation, we would get the actual code from the pod
        # For this PoC, we'll read the main.py file from the host filesystem
        try:
            # Read the API code from the filesystem
            # This assumes the file is accessible from the container
            with open("/app/main.py", "r") as f:
                code = f.read()
            print(f"[Kubernetes MCP] Read {len(code)} bytes of application code")
            return GetAppCodeOutput(code=code)
        except Exception as e:
            print(f"[Kubernetes MCP] Error reading application code: {str(e)}")
            
            # Fallback: Return a hardcoded version of the file
            code = '''
import os
import time
import threading
import psutil
import random
import multiprocessing
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Initialize FastAPI app
app = FastAPI(title="Test Application", description="A test application that can simulate CPU and memory spikes")

# Initialize Prometheus metrics
CPU_USAGE = Gauge("app_cpu_usage_percent", "CPU usage in percent")
MEMORY_USAGE = Gauge("app_memory_usage_bytes", "Memory usage in bytes")
CPU_SPIKE_COUNTER = Counter("app_cpu_spike_total", "Total number of CPU spikes")
MEMORY_SPIKE_COUNTER = Counter("app_memory_spike_total", "Total number of memory spikes")
REQUEST_LATENCY = Histogram("app_request_latency_seconds", "Request latency in seconds")

# Start Prometheus metrics server
start_http_server(8001)

# Global variables to control spikes
cpu_spike_active = False
memory_spike_active = False
allocated_memory = []
cpu_threads = []

# Models
class SpikeResponse(BaseModel):
    status: str
    message: str

class CPUSpikeRequest(BaseModel):
    cpu_percent: Optional[int] = None

class StatusResponse(BaseModel):
    cpu_usage: float
    memory_usage: float
    cpu_spike_active: bool
    memory_spike_active: bool

# Background task to update metrics
def update_metrics():
    while True:
        # Update CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        CPU_USAGE.set(cpu_percent)
        
        # Update memory usage
        memory_info = psutil.Process(os.getpid()).memory_info()
        MEMORY_USAGE.set(memory_info.rss)
        
        time.sleep(1)

# Start metrics update thread
metrics_thread = threading.Thread(target=update_metrics, daemon=True)
metrics_thread.start()

# Generate a large graph for CPU-intensive path finding
def generate_large_graph(num_nodes=20):
    """Generate a large random graph for path finding"""
    graph = {}
    for i in range(num_nodes):
        graph[i] = {}
        # Connect to several random nodes
        for _ in range(random.randint(2, 5)):
            target = random.randint(0, num_nodes-1)
            if target != i:  # Avoid self-loops
                graph[i][target] = random.randint(1, 100)  # Random distance
    return graph

# Brute force shortest path algorithm (CPU intensive)
def brute_force_shortest_path(graph, start, end, max_depth=10):
    """
    Find the shortest path between start and end nodes using brute force.
    This is extremely CPU-intensive for large graphs.
    
    Args:
        graph: Dictionary representing the graph {node: {neighbor: distance}}
        start: Starting node
        end: Target node
        max_depth: Maximum path length to consider (to avoid infinite recursion)
    
    Returns:
        Tuple of (shortest_path, distance)
    """
    best_path = None
    best_distance = float('inf')
    
    def explore_paths(current_node, path, distance, depth):
        nonlocal best_path, best_distance
        
        # Base cases
        if current_node == end:
            if distance < best_distance:
                best_distance = distance
                best_path = path.copy()
            return
        
        if depth >= max_depth:
            return
            
        # Explore all neighbors not yet in the path
        if current_node in graph:
            for neighbor, edge_distance in graph[current_node].items():
                if neighbor not in path:  # Avoid cycles
                    path.append(neighbor)
                    explore_paths(neighbor, path, distance + edge_distance, depth + 1)
                    path.pop()  # Backtrack
    
    # Start the recursive exploration
    explore_paths(start, [start], 0, 0)
    
    return best_path, best_distance

# CPU intensive task for a single thread
def cpu_intensive_task():
    print(f"[CPU Task] Starting CPU-intensive graph algorithm task")
    iteration = 0
    while cpu_spike_active:
        iteration += 1
        # Generate a new random graph for each iteration
        graph_size = 20  # 20 nodes creates significant CPU load
        graph = generate_large_graph(graph_size)
        
        # Pick random start and end nodes
        start_node = random.randint(0, graph_size-1)
        end_node = random.randint(0, graph_size-1)
        while end_node == start_node:
            end_node = random.randint(0, graph_size-1)
        
        print(f"[CPU Task] Iteration {iteration}: Running brute force shortest path algorithm on graph with {graph_size} nodes from node {start_node} to {end_node}")
        
        # Find shortest path using brute force (CPU intensive)
        start_time = time.time()
        path, distance = brute_force_shortest_path(graph, start_node, end_node)
        elapsed = time.time() - start_time
        
        if path:
            print(f"[CPU Task] Found path with {len(path)} nodes and distance {distance} in {elapsed:.2f} seconds")
        else:
            print(f"[CPU Task] No path found after {elapsed:.2f} seconds")

# CPU spike simulation
def simulate_cpu_spike():
    global cpu_spike_active, cpu_threads
    cpu_spike_active = True
    CPU_SPIKE_COUNTER.inc()
    
    # Create multiple threads to maximize CPU usage
    # Use as many threads as there are CPU cores
    num_cores = multiprocessing.cpu_count()
    cpu_threads = []
    
    print(f"[CPU Spike] Starting CPU spike simulation with graph-based algorithm")
    print(f"[CPU Spike] Creating {num_cores * 2} threads to maximize CPU usage")
    
    for i in range(num_cores * 2):  # Use 2x the number of cores to ensure high load
        thread = threading.Thread(target=cpu_intensive_task, name=f"cpu-task-{i}")
        thread.daemon = True
        thread.start()
        cpu_threads.append(thread)
    
    print(f"[CPU Spike] All threads started, will run for 60 seconds")
    
    # Run for 60 seconds
    time.sleep(60)
    
    # Stop the CPU spike
    print(f"[CPU Spike] Stopping CPU spike simulation")
    cpu_spike_active = False
    
    # Wait for all threads to finish
    for thread in cpu_threads:
        thread.join(timeout=1)
    
    cpu_threads = []
    print(f"[CPU Spike] CPU spike simulation completed")

# Memory spike simulation
def simulate_memory_spike():
    global memory_spike_active, allocated_memory
    memory_spike_active = True
    MEMORY_SPIKE_COUNTER.inc()
    
    print(f"[Memory Spike] Starting memory spike simulation")
    
    # Simulate memory spike by allocating memory
    try:
        # Allocate ~700MB of memory
        total_allocated = 0
        for i in range(70):  # Increased from 50 to 70 chunks
            chunk_size = 10 * 1024 * 1024  # 10MB chunks
            allocated_memory.append(bytearray(chunk_size))
            total_allocated += chunk_size
            print(f"[Memory Spike] Allocated chunk {i+1}/70: {total_allocated / (1024 * 1024):.1f} MB total")
            time.sleep(0.05)  # Reduced from 0.1 to 0.05 to make it faster
    except MemoryError as e:
        print(f"[Memory Spike] Memory allocation error: {e}")
    
    print(f"[Memory Spike] Memory allocation complete, holding for 60 seconds")
    
    # Keep the memory allocated for 60 seconds
    time.sleep(60)
    
    # Release memory
    print(f"[Memory Spike] Releasing allocated memory")
    allocated_memory = []
    memory_spike_active = False
    print(f"[Memory Spike] Memory spike simulation completed")

# Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    return {"status": "ok", "message": "Test application is running"}

@app.get("/health", response_model=Dict[str, str])
async def health():
    return {"status": "ok"}

@app.post("/admin/shutdown", response_model=Dict[str, str])
async def shutdown():
    """Shutdown the application - this will cause the container to exit and Docker will restart it"""
    print(f"[System] Received shutdown request - exiting process")
    # Use a thread to exit after sending the response
    def exit_app():
        time.sleep(1)  # Wait for response to be sent
        os._exit(0)  # Force exit the process
    
    threading.Thread(target=exit_app, daemon=True).start()
    return {"status": "shutting_down", "message": "Application is shutting down"}

@app.get("/status", response_model=StatusResponse)
async def status():
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory_info = psutil.Process(os.getpid()).memory_info()
    
    return StatusResponse(
        cpu_usage=cpu_percent,
        memory_usage=memory_info.rss,
        cpu_spike_active=cpu_spike_active,
        memory_spike_active=memory_spike_active
    )

@app.post("/simulate/cpu", response_model=SpikeResponse)
async def trigger_cpu_spike(request: CPUSpikeRequest = None):
    global cpu_spike_active
    
    if cpu_spike_active:
        raise HTTPException(status_code=400, detail="CPU spike already in progress")
    
    # Start CPU spike in a separate thread
    threading.Thread(target=simulate_cpu_spike, daemon=True).start()
    
    return SpikeResponse(
        status="started",
        message="CPU spike simulation started. Will run for 60 seconds."
    )

@app.post("/simulate/memory", response_model=SpikeResponse)
async def trigger_memory_spike():
    global memory_spike_active
    
    if memory_spike_active:
        raise HTTPException(status_code=400, detail="Memory spike already in progress")
    
    # Start memory spike in a separate thread
    threading.Thread(target=simulate_memory_spike, daemon=True).start()
    
    return SpikeResponse(
        status="started",
        message="Memory spike simulation started. Will run for 60 seconds."
    )

@app.post("/simulate/stop", response_model=SpikeResponse)
async def stop_simulations():
    global cpu_spike_active, memory_spike_active, allocated_memory
    
    print(f"[System] Received stop simulation request - this simulates a pod restart")
    print(f"[System] Setting cpu_spike_active to False")
    cpu_spike_active = False
    
    print(f"[System] Setting memory_spike_active to False")
    memory_spike_active = False
    
    print(f"[System] Clearing allocated memory")
    allocated_memory = []
    
    print(f"[System] All simulations stopped - in a real K8s environment, this would be a complete pod restart")
    
    return SpikeResponse(
        status="stopped",
        message="All simulations stopped (simulating pod restart)"
    )

# Middleware to measure request latency
@app.middleware("http")
async def add_metrics(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    REQUEST_LATENCY.observe(time.time() - start_time)
    return response
'''
            return GetAppCodeOutput(code=code)
    except Exception as e:
        return GetAppCodeOutput(code=f"Error getting application code: {str(e)}")

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
            },
            {
                "name": "get_app_code",
                "description": "Get application code from a pod",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "default": "default"},
                        "pod_name": {"type": "string"}
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
