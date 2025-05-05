from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("prometheus-mcp")

app = FastAPI(title="Prometheus MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{PROMETHEUS_URL}/-/healthy")
            if response.status_code == 200:
                return {"status": "healthy"}
            else:
                raise HTTPException(status_code=503, detail="Prometheus is unhealthy")
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))

@app.post("/query")
async def query(query: Dict[str, Any]):
    """Query Prometheus"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROMETHEUS_URL}/api/v1/query",
                json=query
            )
            return response.json()
    except Exception as e:
        logger.error(f"Query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query_range")
async def query_range(query: Dict[str, Any]):
    """Query Prometheus with time range"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                json=query
            )
            return response.json()
    except Exception as e:
        logger.error(f"Range query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    logger.info(f"Starting Prometheus MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
