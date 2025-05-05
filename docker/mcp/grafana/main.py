from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("grafana-mcp")

app = FastAPI(title="Grafana MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000")
GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "your-api-key")

# Headers for Grafana API requests
headers = {
    "Authorization": f"Bearer {GRAFANA_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAFANA_URL}/api/health",
                headers=headers,
                timeout=5.0
            )
            if response.status_code == 200:
                return {"status": "healthy"}
            else:
                raise HTTPException(status_code=503, detail="Grafana is unhealthy")
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))

@app.post("/annotations")
async def create_annotation(annotation: Dict[str, Any]):
    """Create a Grafana annotation"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GRAFANA_URL}/api/annotations",
                headers=headers,
                json={
                    "time": annotation.get("time", None),
                    "timeEnd": annotation.get("timeEnd", None),
                    "tags": annotation.get("tags", []),
                    "text": annotation.get("text", ""),
                }
            )
            return response.json()
    except Exception as e:
        logger.error(f"Failed to create annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboards")
async def list_dashboards():
    """List all dashboards"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAFANA_URL}/api/search",
                headers=headers,
                params={"type": "dash-db"}
            )
            return response.json()
    except Exception as e:
        logger.error(f"Failed to list dashboards: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/{uid}")
async def get_dashboard(uid: str):
    """Get dashboard by UID"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAFANA_URL}/api/dashboards/uid/{uid}",
                headers=headers
            )
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dashboard")
async def create_dashboard(dashboard: Dict[str, Any]):
    """Create or update dashboard"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GRAFANA_URL}/api/dashboards/db",
                headers=headers,
                json=dashboard
            )
            return response.json()
    except Exception as e:
        logger.error(f"Failed to create/update dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def list_alerts():
    """List all alerts"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAFANA_URL}/api/alerts",
                headers=headers
            )
            return response.json()
    except Exception as e:
        logger.error(f"Failed to list alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8002))
    logger.info(f"Starting Grafana MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
