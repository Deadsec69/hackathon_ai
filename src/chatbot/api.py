from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("chatbot")

app = FastAPI(title="AI Agent Chatbot Interface")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:5003")
PROMETHEUS_MCP_URL = os.environ.get("PROMETHEUS_MCP_URL", "http://localhost:8001")
GRAFANA_MCP_URL = os.environ.get("GRAFANA_MCP_URL", "http://localhost:8002")
GITHUB_MCP_URL = os.environ.get("GITHUB_MCP_URL", "http://localhost:8003")
APP_URL = os.environ.get("APP_URL", "http://localhost:5001")
SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://localhost:5002")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

class ChatRequest(BaseModel):
    message: str = Field(..., description="The chat message from the user")

class ChatResponse(BaseModel):
    response: str
    actions: Optional[List[Dict[str, Any]]] = None

async def check_health(url: str, timeout: float = 2.0) -> bool:
    """Check if a service is healthy"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/health", timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "healthy"
            return False
    except Exception as e:
        logger.error(f"Error checking health at {url}: {str(e)}")
        return False

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_interface(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/metrics")
async def get_metrics():
    """Get metrics from the application"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{APP_URL}/metrics/json")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch metrics")
    except Exception as e:
        logger.error(f"Error fetching metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/incidents")
async def get_incidents():
    """Forward incidents request to agent"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AGENT_URL}/incidents")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch incidents")
    except Exception as e:
        logger.error(f"Error fetching incidents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/restarts")
async def get_restarts():
    """Forward restarts request to agent"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AGENT_URL}/restarts")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch restarts")
    except Exception as e:
        logger.error(f"Error fetching restarts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get status of all components"""
    status = {}
    
    # Check app
    status["app"] = "healthy" if await check_health(APP_URL) else "unhealthy"
    
    # Check simulator
    status["simulator"] = "healthy" if await check_health(SIMULATOR_URL) else "unhealthy"
    
    # Check agent
    status["agent"] = "healthy" if await check_health(AGENT_URL) else "unhealthy"
    
    # Check MCP servers
    status["prometheus_mcp"] = "healthy" if await check_health(PROMETHEUS_MCP_URL) else "unhealthy"
    status["grafana_mcp"] = "healthy" if await check_health(GRAFANA_MCP_URL) else "unhealthy"
    status["github_mcp"] = "healthy" if await check_health(GITHUB_MCP_URL) else "unhealthy"
    
    return status

@app.get("/simulate/cpu/{load}")
async def simulate_cpu(load: float):
    """Simulate CPU load"""
    try:
        async with httpx.AsyncClient() as client:
            # Forward to simulator
            response = await client.get(f"{SIMULATOR_URL}/simulate/cpu/{load}")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
    except Exception as e:
        logger.error(f"Error simulating CPU load: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/simulate/memory/{mb}")
async def simulate_memory(mb: float):
    """Simulate memory usage"""
    try:
        async with httpx.AsyncClient() as client:
            # Forward to simulator
            response = await client.get(f"{SIMULATOR_URL}/simulate/memory/{mb}")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
    except Exception as e:
        logger.error(f"Error simulating memory usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/simulate_health_issue")
async def simulate_health_issue():
    """Simulate health issue"""
    try:
        async with httpx.AsyncClient() as client:
            # Set CPU to high value to trigger health issue
            response = await client.get(f"{SIMULATOR_URL}/simulate/cpu/0.9")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return {"status": "success", "message": "Health issue simulated"}
    except Exception as e:
        logger.error(f"Error simulating health issue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fix_issues")
async def fix_issues():
    """Fix all issues"""
    try:
        async with httpx.AsyncClient() as client:
            # Stop simulations
            response = await client.get(f"{SIMULATOR_URL}/stop")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return {"status": "success", "message": "All issues fixed"}
    except Exception as e:
        logger.error(f"Error fixing issues: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message and return a response"""
    if not OPENAI_API_KEY:
        return ChatResponse(
            response="OpenAI API key not configured. Using rule-based responses.",
            actions=[]
        )
    
    # In a real implementation, this would call the OpenAI API
    # For this PoC, we'll use rule-based responses
    message = request.message.lower()
    
    if "status" in message or "health" in message:
        status = await get_status()
        unhealthy_services = [svc for svc, state in status.items() if state == "unhealthy"]
        
        if unhealthy_services:
            return ChatResponse(
                response=f"The following services are unhealthy: {', '.join(unhealthy_services)}",
                actions=[{"name": "View Status", "endpoint": "/status"}]
            )
        else:
            return ChatResponse(
                response="All services are healthy and operating normally.",
                actions=[{"name": "View Status", "endpoint": "/status"}]
            )
    
    elif "cpu" in message:
        metrics = await get_metrics()
        cpu_usage = metrics["cpu_usage"] * 100
        return ChatResponse(
            response=f"Current CPU usage is {cpu_usage:.1f}%",
            actions=[
                {"name": "View Metrics", "endpoint": "/metrics"},
                {"name": "Simulate CPU Load", "endpoint": "/simulate/cpu/0.8"}
            ]
        )
    
    elif "memory" in message:
        metrics = await get_metrics()
        memory_usage = metrics["memory_usage"]
        return ChatResponse(
            response=f"Current memory usage is {memory_usage:.1f}MB",
            actions=[
                {"name": "View Metrics", "endpoint": "/metrics"},
                {"name": "Simulate Memory Load", "endpoint": "/simulate/memory/100"}
            ]
        )
    
    elif "fix" in message or "resolve" in message:
        await fix_issues()
        return ChatResponse(
            response="I've attempted to fix all issues. The application should now be healthy.",
            actions=[{"name": "Check Status", "endpoint": "/status"}]
        )
    
    else:
        return ChatResponse(
            response="I can help you monitor the application. You can ask about the system status, CPU/memory usage, or request to fix issues.",
            actions=[
                {"name": "Check Status", "endpoint": "/status"},
                {"name": "View Metrics", "endpoint": "/metrics"}
            ]
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("CHATBOT_PORT", 8000))
    logger.info(f"Starting chatbot on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
