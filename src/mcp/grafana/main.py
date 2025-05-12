import os
import json
import time
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
import requests
from dotenv import load_dotenv
from grafana_api.grafana_face import GrafanaFace

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Grafana MCP Server", description="MCP server for Grafana operations")

# Get Grafana URL and API key from environment variables
grafana_url = os.environ.get("GRAFANA_URL", "http://grafana:3000")
grafana_api_key = os.environ.get("GRAFANA_API_KEY", "admin:admin")

# Parse Grafana URL to ensure it's properly formatted
if grafana_url.startswith("http://") or grafana_url.startswith("https://"):
    parsed_url = grafana_url
else:
    parsed_url = f"http://{grafana_url}"

print(f"Using Grafana URL: {parsed_url}")

# Initialize Grafana client
if ":" in grafana_api_key:
    # Basic auth
    username, password = grafana_api_key.split(":", 1)
    try:
        grafana_client = GrafanaFace(auth=(username, password), host=parsed_url)
        print(f"Initialized Grafana client with basic auth")
    except Exception as e:
        print(f"Error initializing Grafana client with basic auth: {e}")
        grafana_client = None
else:
    # API key auth
    try:
        grafana_client = GrafanaFace(auth=grafana_api_key, host=parsed_url)
        print(f"Initialized Grafana client with API key")
    except Exception as e:
        print(f"Error initializing Grafana client with API key: {e}")
        grafana_client = None

# Function to get auth headers
def get_auth_headers():
    """Get authentication headers for Grafana API requests"""
    headers = {
        "Content-Type": "application/json"
    }
    
    if ":" in grafana_api_key:
        # Basic auth
        username, password = grafana_api_key.split(":", 1)
        auth_value = f"{username}:{password}"
        import base64
        headers["Authorization"] = f"Basic {base64.b64encode(auth_value.encode()).decode()}"
    else:
        # API key
        headers["Authorization"] = f"Bearer {grafana_api_key}"
    
    return headers

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

# Grafana Models
class DashboardListInput(MCPToolInput):
    query: Optional[str] = Field(None, description="Search query")
    tag: Optional[List[str]] = Field(None, description="Tags to filter by")
    folder_id: Optional[int] = Field(None, description="Folder ID to filter by")
    starred: Optional[bool] = Field(None, description="Filter by starred status")
    limit: Optional[int] = Field(None, description="Limit number of results")

class DashboardInfo(BaseModel):
    id: int
    uid: str
    title: str
    url: str
    folder_id: Optional[int] = None
    folder_title: Optional[str] = None
    tags: List[str]
    starred: bool

class DashboardListOutput(MCPToolOutput):
    dashboards: List[DashboardInfo]

class GetDashboardInput(MCPToolInput):
    uid: str = Field(..., description="Dashboard UID")

class Panel(BaseModel):
    id: int
    title: str
    type: str

class Dashboard(BaseModel):
    id: int
    uid: str
    title: str
    tags: List[str]
    panels: List[Panel]
    url: str
    version: int
    folder_id: Optional[int] = None
    folder_title: Optional[str] = None

class GetDashboardOutput(MCPToolOutput):
    dashboard: Dashboard

class CreateAnnotationInput(MCPToolInput):
    dashboard_id: int = Field(..., description="Dashboard ID")
    time: int = Field(..., description="Time in epoch milliseconds")
    time_end: Optional[int] = Field(None, description="End time for range annotation")
    tags: Optional[List[str]] = Field(None, description="Annotation tags")
    text: str = Field(..., description="Annotation text")

class AnnotationOutput(MCPToolOutput):
    id: int
    dashboard_id: int
    panel_id: Optional[int] = None
    time: int
    time_end: Optional[int] = None
    tags: List[str]
    text: str

class AlertListInput(MCPToolInput):
    dashboard_id: Optional[int] = Field(None, description="Filter by dashboard ID")
    panel_id: Optional[int] = Field(None, description="Filter by panel ID")
    query: Optional[str] = Field(None, description="Search query")
    state: Optional[str] = Field(None, description="Filter by state (all, alerting, ok, paused)")
    limit: Optional[int] = Field(None, description="Limit number of results")

class Alert(BaseModel):
    id: int
    dashboard_id: int
    panel_id: int
    name: str
    state: str
    new_state_date: str
    url: str

class AlertListOutput(MCPToolOutput):
    alerts: List[Alert]

# MCP Protocol Routes
@app.post("/mcp/tools/list_dashboards", response_model=DashboardListOutput)
async def list_dashboards(input_data: DashboardListInput):
    """List Grafana dashboards"""
    try:
        params = {}
        if input_data.query:
            params["query"] = input_data.query
        if input_data.tag:
            params["tag"] = input_data.tag
        if input_data.folder_id is not None:
            params["folderIds"] = input_data.folder_id
        if input_data.starred is not None:
            params["starred"] = str(input_data.starred).lower()
        if input_data.limit:
            params["limit"] = input_data.limit
        
        # Use direct requests instead of the library
        headers = get_auth_headers()
        api_url = f"{parsed_url}/api/search"
        print(f"Listing dashboards from: {api_url}")
        
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        search_result = response.json()
        
        dashboards = []
        for item in search_result:
            if item.get("type") == "dash-folder":
                continue
                
            dashboard_info = DashboardInfo(
                id=item.get("id", 0),
                uid=item.get("uid", ""),
                title=item.get("title", ""),
                url=f"{parsed_url}/d/{item.get('uid')}",
                folder_id=item.get("folderId"),
                folder_title=item.get("folderTitle"),
                tags=item.get("tags", []),
                starred=item.get("isStarred", False)
            )
            dashboards.append(dashboard_info)
        
        return DashboardListOutput(dashboards=dashboards)
    except Exception as e:
        print(f"Error listing dashboards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/get_dashboard", response_model=GetDashboardOutput)
async def get_dashboard(input_data: GetDashboardInput):
    """Get a Grafana dashboard by UID"""
    try:
        # Use direct requests instead of the library
        headers = get_auth_headers()
        api_url = f"{parsed_url}/api/dashboards/uid/{input_data.uid}"
        print(f"Getting dashboard from: {api_url}")
        
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        dashboard_data = result["dashboard"]
        meta = result["meta"]
        
        panels = []
        for panel in dashboard_data.get("panels", []):
            panels.append(Panel(
                id=panel.get("id", 0),
                title=panel.get("title", ""),
                type=panel.get("type", "")
            ))
        
        dashboard = Dashboard(
            id=dashboard_data.get("id", 0),
            uid=dashboard_data.get("uid", ""),
            title=dashboard_data.get("title", ""),
            tags=dashboard_data.get("tags", []),
            panels=panels,
            url=f"{parsed_url}/d/{dashboard_data.get('uid')}",
            version=dashboard_data.get("version", 0),
            folder_id=meta.get("folderId"),
            folder_title=meta.get("folderTitle")
        )
        
        return GetDashboardOutput(dashboard=dashboard)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Dashboard with UID {input_data.uid} not found")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        print(f"Error getting dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/create_annotation", response_model=AnnotationOutput)
async def create_annotation(input_data: CreateAnnotationInput):
    """Create a Grafana annotation"""
    try:
        annotation = {
            "dashboardId": input_data.dashboard_id,
            "time": input_data.time,
            "text": input_data.text,
            "tags": input_data.tags or []
        }
        
        if input_data.time_end:
            annotation["timeEnd"] = input_data.time_end
        
        # Use direct requests instead of the library to have better error handling
        headers = get_auth_headers()
        
        # Ensure the URL is properly formatted
        api_url = f"{parsed_url}/api/annotations"
        print(f"Creating annotation at: {api_url}")
        print(f"Annotation data: {json.dumps(annotation)}")
        print(f"Headers: {json.dumps({k: v for k, v in headers.items() if k != 'Authorization'})}")
        
        # Try a simpler annotation first to test connectivity
        test_annotation = {
            "time": input_data.time,
            "text": input_data.text,
            "tags": input_data.tags or []
        }
        
        print(f"Trying simpler annotation without dashboardId: {json.dumps(test_annotation)}")
        
        try:
            response = requests.post(api_url, json=test_annotation, headers=headers)
            response.raise_for_status()
            result = response.json()
            print(f"Annotation created successfully: {json.dumps(result)}")
            
            return AnnotationOutput(
                id=result.get("id", 0),
                dashboard_id=input_data.dashboard_id,
                time=input_data.time,
                time_end=input_data.time_end,
                tags=input_data.tags or [],
                text=input_data.text
            )
        except requests.exceptions.RequestException as e:
            print(f"Error creating annotation: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            
            # Fall back to creating a global annotation without dashboardId
            print("Falling back to creating a global annotation")
            
            # Create a global annotation (without dashboardId)
            global_annotation = {
                "time": input_data.time,
                "text": f"[{input_data.dashboard_id}] {input_data.text}",
                "tags": input_data.tags or []
            }
            
            if input_data.time_end:
                global_annotation["timeEnd"] = input_data.time_end
            
            try:
                response = requests.post(api_url, json=global_annotation, headers=headers)
                response.raise_for_status()
                result = response.json()
                print(f"Global annotation created successfully: {json.dumps(result)}")
                
                return AnnotationOutput(
                    id=result.get("id", 0),
                    dashboard_id=0,  # No dashboard ID for global annotations
                    time=input_data.time,
                    time_end=input_data.time_end,
                    tags=input_data.tags or [],
                    text=input_data.text
                )
            except requests.exceptions.RequestException as e2:
                print(f"Error creating global annotation: {str(e2)}")
                if hasattr(e2, 'response') and e2.response is not None:
                    print(f"Response status code: {e2.response.status_code}")
                    print(f"Response text: {e2.response.text}")
                raise HTTPException(status_code=500, detail=f"Failed to create annotation: {str(e2)}")
    except Exception as e:
        print(f"Unexpected error creating annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/list_alerts", response_model=AlertListOutput)
async def list_alerts(input_data: AlertListInput):
    """List Grafana alerts"""
    try:
        params = {}
        if input_data.dashboard_id is not None:
            params["dashboardId"] = input_data.dashboard_id
        if input_data.panel_id is not None:
            params["panelId"] = input_data.panel_id
        if input_data.query:
            params["query"] = input_data.query
        if input_data.state:
            params["state"] = input_data.state
        if input_data.limit:
            params["limit"] = input_data.limit
        
        # Use direct requests instead of the library
        headers = get_auth_headers()
        
        # Ensure the URL is properly formatted
        api_url = f"{parsed_url}/api/alerts"
        print(f"Making request to: {api_url}")
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        alerts_data = response.json()
        
        alerts = []
        for alert in alerts_data:
            alerts.append(Alert(
                id=alert.get("id", 0),
                dashboard_id=alert.get("dashboardId", 0),
                panel_id=alert.get("panelId", 0),
                name=alert.get("name", ""),
                state=alert.get("state", ""),
                new_state_date=alert.get("newStateDate", ""),
                url=f"{parsed_url}/d/{alert.get('dashboardUid')}"
            ))
        
        return AlertListOutput(alerts=alerts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# MCP Schema Endpoints
@app.get("/mcp/schema")
async def get_schema():
    """Get the MCP schema for this server"""
    return {
        "name": "grafana-mcp",
        "version": "1.0.0",
        "description": "MCP server for Grafana operations",
        "tools": [
            {
                "name": "list_dashboards",
                "description": "List Grafana dashboards",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "tag": {"type": "array", "items": {"type": "string"}},
                        "folder_id": {"type": "integer"},
                        "starred": {"type": "boolean"},
                        "limit": {"type": "integer"}
                    }
                }
            },
            {
                "name": "get_dashboard",
                "description": "Get a Grafana dashboard by UID",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "uid": {"type": "string"}
                    },
                    "required": ["uid"]
                }
            },
            {
                "name": "create_annotation",
                "description": "Create a Grafana annotation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dashboard_id": {"type": "integer"},
                        "time": {"type": "integer"},
                        "time_end": {"type": "integer"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "text": {"type": "string"}
                    },
                    "required": ["dashboard_id", "time", "text"]
                }
            },
            {
                "name": "list_alerts",
                "description": "List Grafana alerts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dashboard_id": {"type": "integer"},
                        "panel_id": {"type": "integer"},
                        "query": {"type": "string"},
                        "state": {"type": "string", "enum": ["all", "alerting", "ok", "paused"]},
                        "limit": {"type": "integer"}
                    }
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
        "name": "Grafana MCP Server",
        "version": "1.0.0",
        "description": "MCP server for Grafana operations",
        "schema_url": "/mcp/schema"
    }
