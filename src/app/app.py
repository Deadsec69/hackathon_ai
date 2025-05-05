from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import time
import psutil
from typing import Dict, Any
from prometheus_client import start_http_server, Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("app")

app = FastAPI(title="Sample Application")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
CPU_GAUGE = Gauge('app_cpu_usage', 'Application CPU usage')
MEMORY_GAUGE = Gauge('app_memory_usage', 'Application memory usage in MB')
HEALTH_GAUGE = Gauge('app_health_status', 'Application health status (1=healthy, 0=unhealthy)')
REQUEST_COUNTER = Counter('app_request_count', 'Total request count')

# Application state
current_cpu_usage = 0.0
current_memory_usage = 0.0
current_health_status = 1

# Thresholds (configurable via environment variables)
CPU_THRESHOLD = float(os.environ.get("CPU_THRESHOLD", 0.8))  # 80%
MEMORY_THRESHOLD = float(os.environ.get("MEMORY_THRESHOLD", 90))  # 90MB

@app.get("/")
async def read_root():
    """Root endpoint"""
    REQUEST_COUNTER.inc()
    return {
        "status": "running",
        "cpu_usage": current_cpu_usage,
        "memory_usage": current_memory_usage,
        "health_status": current_health_status
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    REQUEST_COUNTER.inc()
    return {"status": "healthy" if current_health_status == 1 else "unhealthy"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    REQUEST_COUNTER.inc()
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.get("/metrics/json")
async def metrics_json():
    """Get metrics in JSON format"""
    REQUEST_COUNTER.inc()
    return {
        "cpu_usage": current_cpu_usage,
        "memory_usage": current_memory_usage,
        "health_status": current_health_status,
        "request_count": REQUEST_COUNTER._value.get()
    }

@app.put("/admin/metrics/cpu")
async def set_cpu_usage(value: Dict[str, float]):
    """Admin endpoint to set CPU usage"""
    global current_cpu_usage, current_health_status
    
    if "value" not in value:
        raise HTTPException(status_code=400, detail="Missing 'value' in request body")
    
    cpu_value = value["value"]
    if cpu_value < 0 or cpu_value > 1:
        raise HTTPException(status_code=400, detail="CPU value must be between 0 and 1")
    
    current_cpu_usage = cpu_value
    CPU_GAUGE.set(cpu_value)
    
    # Update health status based on thresholds
    if cpu_value > CPU_THRESHOLD:
        current_health_status = 0
        HEALTH_GAUGE.set(0)
    else:
        current_health_status = 1
        HEALTH_GAUGE.set(1)
    
    return {"status": "updated", "cpu_usage": current_cpu_usage}

@app.put("/admin/metrics/memory")
async def set_memory_usage(value: Dict[str, float]):
    """Admin endpoint to set memory usage"""
    global current_memory_usage, current_health_status
    
    if "value" not in value:
        raise HTTPException(status_code=400, detail="Missing 'value' in request body")
    
    memory_value = value["value"]
    if memory_value < 0:
        raise HTTPException(status_code=400, detail="Memory value must be positive")
    
    current_memory_usage = memory_value
    MEMORY_GAUGE.set(memory_value)
    
    # Update health status based on thresholds
    if memory_value > MEMORY_THRESHOLD:
        current_health_status = 0
        HEALTH_GAUGE.set(0)
    else:
        current_health_status = 1
        HEALTH_GAUGE.set(1)
    
    return {"status": "updated", "memory_usage": current_memory_usage}

@app.get("/simulate/high-cpu")
async def simulate_high_cpu():
    """Simulate high CPU usage"""
    global current_cpu_usage, current_health_status
    
    current_cpu_usage = 0.95  # 95% CPU usage
    CPU_GAUGE.set(current_cpu_usage)
    
    # Update health status
    current_health_status = 0
    HEALTH_GAUGE.set(0)
    
    return {"status": "simulated", "cpu_usage": current_cpu_usage}

@app.get("/simulate/high-memory")
async def simulate_high_memory():
    """Simulate high memory usage"""
    global current_memory_usage, current_health_status
    
    current_memory_usage = 95  # 95MB memory usage
    MEMORY_GAUGE.set(current_memory_usage)
    
    # Update health status
    current_health_status = 0
    HEALTH_GAUGE.set(0)
    
    return {"status": "simulated", "memory_usage": current_memory_usage}

@app.get("/simulate/reset")
async def reset_simulation():
    """Reset all simulated values"""
    global current_cpu_usage, current_memory_usage, current_health_status
    
    current_cpu_usage = 0.1  # 10% CPU usage
    current_memory_usage = 50  # 50MB memory usage
    current_health_status = 1  # healthy
    
    CPU_GAUGE.set(current_cpu_usage)
    MEMORY_GAUGE.set(current_memory_usage)
    HEALTH_GAUGE.set(current_health_status)
    
    return {
        "status": "reset",
        "cpu_usage": current_cpu_usage,
        "memory_usage": current_memory_usage,
        "health_status": current_health_status
    }

if __name__ == "__main__":
    import uvicorn
    
    # Start Prometheus metrics server
    metrics_port = int(os.environ.get("METRICS_PORT", 8081))
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")
    
    # Start FastAPI server
    port = int(os.environ.get("APP_PORT", 5001))
    logger.info(f"Starting application on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
