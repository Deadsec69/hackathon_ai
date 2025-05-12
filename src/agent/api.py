import os
import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Union
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dataclasses import asdict

from agent import run_agent, get_incidents, get_restart_counts
from incident_store import incident_store, Incident

# Initialize FastAPI app
app = FastAPI(title="AI Agent API", description="API for the AI agent")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class RunAgentRequest(BaseModel):
    """Request model for running the agent"""
    force_run: Optional[bool] = Field(False, description="Force the agent to run even if it's already running")

class RunAgentResponse(BaseModel):
    """Response model for running the agent"""
    status: str
    action: Optional[str] = None
    pod_name: Optional[str] = None
    namespace: Optional[str] = None
    issue_type: Optional[str] = None
    restart_count: Optional[int] = None
    github_issue_number: Optional[int] = None
    github_issue_url: Optional[str] = None
    github_pr_number: Optional[int] = None
    github_pr_url: Optional[str] = None
    incident_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

class GetIncidentsRequest(BaseModel):
    """Request model for getting incidents"""
    resolved: Optional[bool] = None
    incident_type: Optional[str] = None
    pod_name: Optional[str] = None
    namespace: Optional[str] = None
    since: Optional[int] = None
    limit: Optional[int] = None

class IncidentResponse(BaseModel):
    """Response model for an incident"""
    id: str
    type: str
    pod_name: str
    namespace: str
    timestamp: int
    severity: str
    metrics: Dict[str, Any]
    action_taken: Optional[str] = None
    github_issue: Optional[Dict[str, Any]] = None
    github_pr: Optional[Dict[str, Any]] = None
    resolved: bool = False
    resolved_timestamp: Optional[int] = None
    notes: Optional[str] = None

class GetIncidentsResponse(BaseModel):
    """Response model for getting incidents"""
    incidents: List[IncidentResponse]
    total: int

class GetRestartCountsResponse(BaseModel):
    """Response model for getting restart counts"""
    restart_counts: Dict[str, Dict[str, int]]

class SimulateIssueRequest(BaseModel):
    """Request model for simulating an issue"""
    issue_type: str = Field(..., description="Type of issue to simulate (cpu or memory)")

class SimulateIssueResponse(BaseModel):
    """Response model for simulating an issue"""
    status: str
    message: str

# Global variables
agent_running = False
last_run_time = 0
run_interval = 60  # Run the agent every 60 seconds
auto_run_enabled = True  # Enable automatic agent runs

# Background task to run the agent
def run_agent_task():
    """Run the agent in the background"""
    global agent_running, last_run_time
    
    try:
        agent_running = True
        result = run_agent()
        last_run_time = time.time()
        return result
    except Exception as e:
        logger.error(f"Error running agent: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        agent_running = False

# Periodic agent runner
async def periodic_agent_runner():
    """Run the agent periodically"""
    global agent_running, last_run_time, auto_run_enabled
    
    while True:
        try:
            if auto_run_enabled and not agent_running and time.time() - last_run_time >= run_interval:
                print(f"Auto-running agent at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                run_agent_task()
        except Exception as e:
            print(f"Error in periodic agent runner: {str(e)}")
        
        await asyncio.sleep(10)  # Check every 10 seconds

# Routes
@app.post("/api/agent/run", response_model=RunAgentResponse)
async def api_run_agent(request: RunAgentRequest, background_tasks: BackgroundTasks):
    """Run the agent"""
    global agent_running, last_run_time
    
    # Check if the agent is already running
    if agent_running and not request.force_run:
        return RunAgentResponse(
            status="error",
            error="Agent is already running"
        )
    
    # Check if the agent was run recently
    if time.time() - last_run_time < run_interval and not request.force_run:
        return RunAgentResponse(
            status="error",
            error=f"Agent was run recently. Please wait {int(run_interval - (time.time() - last_run_time))} seconds before running again."
        )
    
    # Run the agent in the background
    background_tasks.add_task(run_agent_task)
    
    return RunAgentResponse(
        status="success",
        message="Agent is running in the background"
    )

@app.get("/api/agent/status", response_model=Dict[str, Any])
async def api_agent_status():
    """Get the agent status"""
    return {
        "running": agent_running,
        "last_run_time": last_run_time,
        "run_interval": run_interval,
        "auto_run_enabled": auto_run_enabled
    }

@app.post("/api/agent/auto-run", response_model=Dict[str, Any])
async def api_set_auto_run(enabled: bool = True):
    """Enable or disable automatic agent runs"""
    global auto_run_enabled
    
    auto_run_enabled = enabled
    
    return {
        "auto_run_enabled": auto_run_enabled
    }

@app.post("/api/incidents", response_model=GetIncidentsResponse)
async def api_get_incidents(request: GetIncidentsRequest):
    """Get incidents"""
    incidents = get_incidents(
        resolved=request.resolved,
        incident_type=request.incident_type,
        pod_name=request.pod_name,
        namespace=request.namespace,
        since=request.since,
        limit=request.limit
    )
    
    return GetIncidentsResponse(
        incidents=incidents,
        total=len(incidents)
    )

@app.get("/api/incidents/{incident_id}", response_model=IncidentResponse)
async def api_get_incident(incident_id: str):
    """Get an incident by ID"""
    incident = incident_store.get_incident(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident with ID {incident_id} not found")
    
    return asdict(incident)

@app.post("/api/incidents/{incident_id}/resolve", response_model=IncidentResponse)
async def api_resolve_incident(incident_id: str, notes: Optional[str] = None):
    """Resolve an incident"""
    incident = incident_store.resolve_incident(incident_id, notes)
    
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident with ID {incident_id} not found")
    
    return asdict(incident)

@app.get("/api/restart-counts", response_model=GetRestartCountsResponse)
async def api_get_restart_counts():
    """Get restart counts"""
    restart_counts = get_restart_counts()
    
    return GetRestartCountsResponse(
        restart_counts=restart_counts
    )

@app.post("/api/simulate/issue", response_model=SimulateIssueResponse)
async def api_simulate_issue(request: SimulateIssueRequest):
    """Simulate an issue"""
    issue_type = request.issue_type.lower()
    
    if issue_type not in ["cpu", "memory"]:
        raise HTTPException(status_code=400, detail="Issue type must be 'cpu' or 'memory'")
    
    # Make a request to the test application to simulate the issue
    import requests
    
    try:
        response = requests.post(f"http://test-app:8000/simulate/{issue_type}")
        response.raise_for_status()
        
        return SimulateIssueResponse(
            status="success",
            message=f"{issue_type.upper()} spike simulation started"
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error simulating issue: {str(e)}")

@app.post("/api/simulate/stop", response_model=SimulateIssueResponse)
async def api_stop_simulation():
    """Stop all simulations"""
    import requests
    
    try:
        response = requests.post("http://test-app:8000/simulate/stop")
        response.raise_for_status()
        
        return SimulateIssueResponse(
            status="success",
            message="All simulations stopped"
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error stopping simulations: {str(e)}")

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "AI Agent API",
        "version": "1.0.0",
        "description": "API for the AI agent"
    }

# Run the agent periodically in the background
@app.on_event("startup")
async def startup_event():
    """Run the agent on startup"""
    # Start the periodic agent runner
    asyncio.create_task(periodic_agent_runner())
    print("Started periodic agent runner")
