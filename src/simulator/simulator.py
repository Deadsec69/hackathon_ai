from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import time
import threading
import psutil
import numpy as np
import asyncio
import httpx
from typing import Dict, Any
from prometheus_client import start_http_server, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("simulator")

app = FastAPI(title="Application Simulator")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
APP_URL = os.environ.get("APP_URL", "http://localhost:5001")

# Prometheus metrics
CPU_GAUGE = Gauge('simulator_cpu_usage', 'Simulated CPU usage')
MEMORY_GAUGE = Gauge('simulator_memory_usage', 'Simulated memory usage in MB')

# Global state
current_cpu_load = 0.0
current_memory_mb = 0.0
stop_simulation = False
simulation_thread = None

async def update_app_metrics(cpu: float = None, memory: float = None):
    """Update app metrics via admin endpoints"""
    async with httpx.AsyncClient() as client:
        try:
            if cpu is not None:
                response = await client.put(
                    f"{APP_URL}/admin/metrics/cpu",
                    json={"value": cpu},
                    timeout=5.0
                )
                if response.status_code != 200:
                    logger.error(f"Failed to update app CPU metrics: {response.text}")
                else:
                    logger.info(f"Updated app CPU metrics to {cpu}")

            if memory is not None:
                response = await client.put(
                    f"{APP_URL}/admin/metrics/memory",
                    json={"value": memory},
                    timeout=5.0
                )
                if response.status_code != 200:
                    logger.error(f"Failed to update app memory metrics: {response.text}")
                else:
                    logger.info(f"Updated app memory metrics to {memory}")

        except Exception as e:
            logger.error(f"Error updating app metrics: {str(e)}")

def simulate_cpu_load(target_load: float):
    """Simulate CPU load by performing calculations"""
    global current_cpu_load, stop_simulation
    
    while not stop_simulation:
        start_time = time.time()
        
        # Update current load and metrics
        current_cpu_load = target_load
        CPU_GAUGE.set(target_load)
        
        # Update app metrics
        asyncio.run(update_app_metrics(cpu=target_load))
        
        # Perform calculations to consume CPU
        if target_load > 0:
            end_time = start_time + 0.1  # 100ms interval
            while time.time() < end_time:
                # CPU-intensive calculation
                np.random.random((100, 100)).dot(np.random.random((100, 100)))
            
            # Sleep to achieve target load
            elapsed = time.time() - start_time
            if elapsed < 0.1:  # 100ms interval
                time.sleep(0.1 - elapsed)
        else:
            time.sleep(0.1)

def simulate_memory_usage(target_mb: float):
    """Simulate memory usage by allocating memory"""
    global current_memory_mb, stop_simulation
    
    # Convert MB to bytes
    target_bytes = target_mb * 1024 * 1024
    
    # Allocate memory in chunks
    chunk_size = 1024 * 1024  # 1MB chunks
    data = []
    
    while not stop_simulation:
        current_bytes = sum(len(chunk) for chunk in data)
        
        if current_bytes < target_bytes:
            # Allocate more memory
            chunk = bytearray(chunk_size)
            data.append(chunk)
        elif current_bytes > target_bytes:
            # Free some memory
            if data:
                data.pop()
        
        # Update current memory usage and metrics
        current_memory_mb = current_bytes / (1024 * 1024)
        MEMORY_GAUGE.set(current_memory_mb)
        
        # Update app metrics
        asyncio.run(update_app_metrics(memory=current_memory_mb))
        
        time.sleep(0.1)

@app.get("/")
async def read_root():
    """Root endpoint"""
    return {
        "status": "running",
        "cpu_load": current_cpu_load,
        "memory_mb": current_memory_mb
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.get("/simulate/cpu/{load}")
async def simulate_cpu(load: float):
    """Simulate CPU load (0.0 to 1.0)"""
    global stop_simulation, simulation_thread, current_cpu_load
    
    if load < 0 or load > 1:
        raise HTTPException(status_code=400, detail="Load must be between 0 and 1")
    
    # Stop any existing simulation
    if simulation_thread and simulation_thread.is_alive():
        stop_simulation = True
        simulation_thread.join()
    
    # Start new simulation
    stop_simulation = False
    simulation_thread = threading.Thread(target=simulate_cpu_load, args=(load,))
    simulation_thread.start()
    
    # Update app metrics immediately
    await update_app_metrics(cpu=load)
    
    return {
        "status": "started",
        "target_load": load
    }

@app.get("/simulate/memory/{mb}")
async def simulate_memory(mb: float):
    """Simulate memory usage in MB"""
    global stop_simulation, simulation_thread, current_memory_mb
    
    if mb < 0:
        raise HTTPException(status_code=400, detail="Memory must be positive")
    
    # Stop any existing simulation
    if simulation_thread and simulation_thread.is_alive():
        stop_simulation = True
        simulation_thread.join()
    
    # Start new simulation
    stop_simulation = False
    simulation_thread = threading.Thread(target=simulate_memory_usage, args=(mb,))
    simulation_thread.start()
    
    # Update app metrics immediately
    await update_app_metrics(memory=mb)
    
    return {
        "status": "started",
        "target_mb": mb
    }

@app.get("/stop")
async def stop():
    """Stop all simulations"""
    global stop_simulation, simulation_thread, current_cpu_load, current_memory_mb
    
    if simulation_thread and simulation_thread.is_alive():
        stop_simulation = True
        simulation_thread.join()
    
    current_cpu_load = 0.0
    current_memory_mb = 0.0
    
    # Update metrics
    CPU_GAUGE.set(0.0)
    MEMORY_GAUGE.set(0.0)
    
    # Update app metrics
    await update_app_metrics(cpu=0.0, memory=0.0)
    
    return {
        "status": "stopped"
    }

if __name__ == "__main__":
    import uvicorn
    
    # Start Prometheus metrics server
    metrics_port = int(os.environ.get("SIMULATOR_METRICS_PORT", 8082))
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")
    
    # Start FastAPI server
    port = int(os.environ.get("SIMULATOR_PORT", 5002))
    logger.info(f"Starting simulator on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
