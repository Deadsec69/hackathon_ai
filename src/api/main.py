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

# CPU intensive task for a single thread
def cpu_intensive_task():
    while cpu_spike_active:
        # Perform CPU-intensive calculation
        [random.random() ** 2 for _ in range(10000000)]

# CPU spike simulation
def simulate_cpu_spike():
    global cpu_spike_active, cpu_threads
    cpu_spike_active = True
    CPU_SPIKE_COUNTER.inc()
    
    # Create multiple threads to maximize CPU usage
    # Use as many threads as there are CPU cores
    num_cores = multiprocessing.cpu_count()
    cpu_threads = []
    
    for _ in range(num_cores * 2):  # Use 2x the number of cores to ensure high load
        thread = threading.Thread(target=cpu_intensive_task)
        thread.daemon = True
        thread.start()
        cpu_threads.append(thread)
    
    # Run for 60 seconds
    time.sleep(60)
    
    # Stop the CPU spike
    cpu_spike_active = False
    
    # Wait for all threads to finish
    for thread in cpu_threads:
        thread.join(timeout=1)
    
    cpu_threads = []

# Memory spike simulation
def simulate_memory_spike():
    global memory_spike_active, allocated_memory
    memory_spike_active = True
    MEMORY_SPIKE_COUNTER.inc()
    
    # Simulate memory spike by allocating memory
    try:
        # Allocate ~500MB of memory
        for _ in range(50):
            allocated_memory.append(bytearray(10 * 1024 * 1024))  # 10MB chunks
            time.sleep(0.1)  # Small pause to make it gradual
    except MemoryError:
        pass
    
    # Keep the memory allocated for 60 seconds
    time.sleep(60)
    
    # Release memory
    allocated_memory = []
    memory_spike_active = False

# Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    return {"status": "ok", "message": "Test application is running"}

@app.get("/health", response_model=Dict[str, str])
async def health():
    return {"status": "ok"}

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
    
    cpu_spike_active = False
    memory_spike_active = False
    allocated_memory = []
    
    return SpikeResponse(
        status="stopped",
        message="All simulations stopped"
    )

# Middleware to measure request latency
@app.middleware("http")
async def add_metrics(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    REQUEST_LATENCY.observe(time.time() - start_time)
    return response
