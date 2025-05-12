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
    # Check if any simulation is active
    if cpu_spike_active:
        return {"status": "degraded", "message": "High CPU load detected"}
    elif memory_spike_active:
        return {"status": "degraded", "message": "High memory usage detected"}
    else:
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
    
    # Set the flag before starting the thread
    cpu_spike_active = True
    
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
    
    # Set the flag before starting the thread
    memory_spike_active = True
    
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
