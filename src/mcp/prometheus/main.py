import os
import json
import time
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Prometheus MCP Server", description="MCP server for Prometheus operations")

# Get Prometheus URL from environment variable
prometheus_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")

# MCP Models
class MCPToolInput(BaseModel):
    """Base model for MCP tool inputs"""
    pass

class MCPToolOutput(BaseModel):
    """Base model for MCP tool outputs"""
    pass

class MCPResourceOutput(BaseModel):
    """Base model for MCP resource outputs"""
    pass

class MCPError(BaseModel):
    """Model for MCP errors"""
    error: str
    details: Optional[Dict[str, Any]] = None

# Prometheus Models
class QueryInput(MCPToolInput):
    query: str = Field(..., description="Prometheus PromQL query")
    time: Optional[str] = Field(None, description="Evaluation timestamp (RFC3339 or Unix timestamp)")
    timeout: Optional[str] = Field(None, description="Evaluation timeout")

class QueryRangeInput(MCPToolInput):
    query: str = Field(..., description="Prometheus PromQL query")
    start: str = Field(..., description="Start timestamp (RFC3339 or Unix timestamp)")
    end: str = Field(..., description="End timestamp (RFC3339 or Unix timestamp)")
    step: str = Field(..., description="Query resolution step width")
    timeout: Optional[str] = Field(None, description="Evaluation timeout")

class AlertsInput(MCPToolInput):
    active: Optional[bool] = Field(None, description="Filter by active alerts")
    silenced: Optional[bool] = Field(None, description="Filter by silenced alerts")
    inhibited: Optional[bool] = Field(None, description="Filter by inhibited alerts")
    unprocessed: Optional[bool] = Field(None, description="Filter by unprocessed alerts")
    filter: Optional[str] = Field(None, description="Filter alerts by label")

class TargetsInput(MCPToolInput):
    state: Optional[str] = Field(None, description="Filter by target state (active, dropped, any)")

class MetricValue(BaseModel):
    timestamp: float
    value: Union[float, str]

class MetricSeries(BaseModel):
    metric: Dict[str, str]
    values: List[MetricValue]

class QueryOutput(MCPToolOutput):
    result_type: str
    result: List[Dict[str, Any]]

class AlertOutput(BaseModel):
    labels: Dict[str, str]
    annotations: Dict[str, str]
    state: str
    active_at: str
    value: str

class AlertsOutput(MCPToolOutput):
    alerts: List[AlertOutput]

class Target(BaseModel):
    target_url: str
    labels: Dict[str, str]
    health: str
    last_scrape: str
    error: Optional[str] = None

class TargetsOutput(MCPToolOutput):
    targets: List[Target]

class MetricsListOutput(MCPToolOutput):
    metrics: List[str]

# Helper functions
def make_prometheus_request(endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make a request to the Prometheus API"""
    url = f"{prometheus_url}/api/v1/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Prometheus: {str(e)}")

# MCP Protocol Routes
@app.post("/mcp/tools/query", response_model=QueryOutput)
async def query(input_data: QueryInput):
    """Execute an instant query against Prometheus"""
    params = {"query": input_data.query}
    if input_data.time:
        params["time"] = input_data.time
    if input_data.timeout:
        params["timeout"] = input_data.timeout
    
    try:
        response = make_prometheus_request("query", params)
        if response["status"] != "success":
            raise HTTPException(status_code=400, detail=response.get("error", "Unknown error"))
        
        return QueryOutput(
            result_type=response["data"]["resultType"],
            result=response["data"]["result"]
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/query_range", response_model=QueryOutput)
async def query_range(input_data: QueryRangeInput):
    """Execute a range query against Prometheus"""
    params = {
        "query": input_data.query,
        "start": input_data.start,
        "end": input_data.end,
        "step": input_data.step
    }
    if input_data.timeout:
        params["timeout"] = input_data.timeout
    
    try:
        response = make_prometheus_request("query_range", params)
        if response["status"] != "success":
            raise HTTPException(status_code=400, detail=response.get("error", "Unknown error"))
        
        return QueryOutput(
            result_type=response["data"]["resultType"],
            result=response["data"]["result"]
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/alerts", response_model=AlertsOutput)
async def alerts(input_data: AlertsInput):
    """Get alerts from Prometheus"""
    params = {}
    if input_data.active is not None:
        params["active"] = str(input_data.active).lower()
    if input_data.silenced is not None:
        params["silenced"] = str(input_data.silenced).lower()
    if input_data.inhibited is not None:
        params["inhibited"] = str(input_data.inhibited).lower()
    if input_data.unprocessed is not None:
        params["unprocessed"] = str(input_data.unprocessed).lower()
    if input_data.filter:
        params["filter"] = input_data.filter
    
    try:
        response = make_prometheus_request("alerts", params)
        if response["status"] != "success":
            raise HTTPException(status_code=400, detail=response.get("error", "Unknown error"))
        
        alerts_list = []
        for alert in response["data"]["alerts"]:
            alerts_list.append(AlertOutput(
                labels=alert["labels"],
                annotations=alert["annotations"],
                state=alert["state"],
                active_at=alert["activeAt"],
                value=str(alert.get("value", ""))
            ))
        
        return AlertsOutput(alerts=alerts_list)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/targets", response_model=TargetsOutput)
async def targets(input_data: TargetsInput):
    """Get targets from Prometheus"""
    params = {}
    if input_data.state:
        params["state"] = input_data.state
    
    try:
        response = make_prometheus_request("targets", params)
        if response["status"] != "success":
            raise HTTPException(status_code=400, detail=response.get("error", "Unknown error"))
        
        targets_list = []
        for target in response["data"]["activeTargets"]:
            targets_list.append(Target(
                target_url=target["scrapeUrl"],
                labels=target["labels"],
                health=target["health"],
                last_scrape=target["lastScrape"],
                error=target.get("lastError", "")
            ))
        
        return TargetsOutput(targets=targets_list)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/metrics", response_model=MetricsListOutput)
async def metrics():
    """Get list of metrics from Prometheus"""
    try:
        response = make_prometheus_request("label/__name__/values")
        if response["status"] != "success":
            raise HTTPException(status_code=400, detail=response.get("error", "Unknown error"))
        
        return MetricsListOutput(metrics=response["data"])
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

# MCP Schema Endpoints
@app.get("/mcp/schema")
async def get_schema():
    """Get the MCP schema for this server"""
    return {
        "name": "prometheus-mcp",
        "version": "1.0.0",
        "description": "MCP server for Prometheus operations",
        "tools": [
            {
                "name": "query",
                "description": "Execute an instant query against Prometheus",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "time": {"type": "string"},
                        "timeout": {"type": "string"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "query_range",
                "description": "Execute a range query against Prometheus",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "start": {"type": "string"},
                        "end": {"type": "string"},
                        "step": {"type": "string"},
                        "timeout": {"type": "string"}
                    },
                    "required": ["query", "start", "end", "step"]
                }
            },
            {
                "name": "alerts",
                "description": "Get alerts from Prometheus",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "active": {"type": "boolean"},
                        "silenced": {"type": "boolean"},
                        "inhibited": {"type": "boolean"},
                        "unprocessed": {"type": "boolean"},
                        "filter": {"type": "string"}
                    }
                }
            },
            {
                "name": "targets",
                "description": "Get targets from Prometheus",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string", "enum": ["active", "dropped", "any"]}
                    }
                }
            },
            {
                "name": "metrics",
                "description": "Get list of metrics from Prometheus",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ],
        "resources": []
    }

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Prometheus MCP Server",
        "version": "1.0.0",
        "description": "MCP server for Prometheus operations",
        "schema_url": "/mcp/schema"
    }
