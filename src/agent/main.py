from fastapi import FastAPI, HTTPException
import httpx
import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("agent")

app = FastAPI(title="AI Agent")

# Environment variables
PROMETHEUS_MCP_URL = os.environ.get("PROMETHEUS_MCP_URL", "http://localhost:8001")
GRAFANA_MCP_URL = os.environ.get("GRAFANA_MCP_URL", "http://localhost:8002")
GITHUB_MCP_URL = os.environ.get("GITHUB_MCP_URL", "http://localhost:8003")
APP_URL = os.environ.get("APP_URL", "http://localhost:5001")
SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://localhost:5002")

class RestartAttempt:
    def __init__(self, timestamp: datetime, successful: bool, reason: str):
        self.timestamp = timestamp
        self.successful = successful
        self.reason = reason

# Agent state
restart_attempts = []  # List of RestartAttempt objects
MAX_FAILED_RESTARTS_PER_DAY = int(os.environ.get("MAX_RESTARTS_PER_DAY", 5))
incident_history = []
manual_intervention_requested = False

class Incident:
    def __init__(self, description: str, severity: str, actions: List[str]):
        self.timestamp = datetime.now()
        self.description = description
        self.severity = severity
        self.actions = actions

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

async def query_prometheus(query: str) -> float:
    """Query Prometheus metrics via MCP"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{PROMETHEUS_MCP_URL}/query",
                params={"query": query},
                timeout=5.0
            )
            if response.status_code != 200:
                logger.error(f"Failed to query Prometheus MCP: {response.text}")
                raise HTTPException(status_code=500, detail="Failed to query metrics")
            
            data = response.json()
            if data.get("status") == "success" and data.get("data", {}).get("result"):
                return float(data["data"]["result"][0]["value"][1])
            return 0.0
        except Exception as e:
            logger.error(f"Error querying Prometheus: {str(e)}")
            return 0.0

async def check_app_health() -> Dict[str, Any]:
    """Check application health by querying metrics"""
    try:
        # Query metrics from app directly first
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{APP_URL}/metrics/json")
            if response.status_code == 200:
                metrics = response.json()
                logger.info(f"Current metrics (from app) - CPU: {metrics['cpu_usage']:.2f}, Memory: {metrics['memory_usage']:.1f}MB, Health: {metrics['health_status']}")
                return metrics
            else:
                logger.warning("Failed to get metrics from app directly, falling back to Prometheus")
        
        # Fallback to Prometheus if direct query fails
        cpu_usage = await query_prometheus("app_cpu_usage")
        memory_usage = await query_prometheus("app_memory_usage")
        health_status = await query_prometheus("app_health_status")
        
        logger.info(f"Current metrics (from Prometheus) - CPU: {cpu_usage:.2f}, Memory: {memory_usage:.1f}MB, Health: {health_status}")
        
        return {
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "health_status": health_status
        }
    except Exception as e:
        logger.error(f"Error checking health: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking health: {str(e)}")

async def check_metrics_healthy(metrics: Dict[str, Any]) -> bool:
    """Check if metrics are within healthy ranges"""
    return (
        metrics["cpu_usage"] <= 0.8 and
        metrics["memory_usage"] <= 90 and
        metrics["health_status"] == 1
    )

async def can_restart_pod() -> bool:
    """Check if we can restart the pod based on daily limit"""
    now = datetime.now()
    failed_restarts = [
        attempt for attempt in restart_attempts
        if not attempt.successful and attempt.timestamp > now - timedelta(days=1)
    ]
    return len(failed_restarts) < MAX_FAILED_RESTARTS_PER_DAY

async def restart_pod(reason: str) -> bool:
    """Restart the application pod"""
    if not await can_restart_pod():
        logger.warning("Cannot restart pod: daily failed restart limit reached")
        return False
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Restarting pod...")
            
            # Stop any simulations first
            try:
                await client.get(f"{SIMULATOR_URL}/stop")
                logger.info("Stopped running simulations")
            except Exception as e:
                logger.warning(f"Failed to stop simulations: {str(e)}")
            
            # Reset metrics to healthy values
            await client.put(f"{APP_URL}/admin/metrics/cpu", json={"value": 0.1})
            await client.put(f"{APP_URL}/admin/metrics/memory", json={"value": 50})
            
            # Wait a moment for metrics to update
            await asyncio.sleep(2)
            
            # Check if metrics are now healthy
            metrics = await check_app_health()
            success = await check_metrics_healthy(metrics)
            
            # Record restart attempt
            global restart_attempts
            attempt = RestartAttempt(datetime.now(), success, reason)
            restart_attempts.append(attempt)
            
            # If successful, clear failed restart history
            if success:
                logger.info("Restart was successful, clearing failed restart history")
                restart_attempts = [a for a in restart_attempts if a.successful]
            
            # Create Grafana annotation
            status = "successful" if success else "unsuccessful"
            await create_grafana_annotation(f"Pod restart {status} - {reason}")
            
            # Create GitHub issue for tracking
            await create_github_issue(
                f"Pod Restart Event - {status.title()}",
                f"Pod restart was {status} after {reason}.\n\n" +
                "Details:\n" +
                f"- Timestamp: {attempt.timestamp.isoformat()}\n" +
                f"- Reason: {reason}\n" +
                f"- Success: {success}\n" +
                f"- Failed restarts today: {len([a for a in restart_attempts if not a.successful])}\n" +
                f"- Max failed restarts per day: {MAX_FAILED_RESTARTS_PER_DAY}",
                ["incident", "auto-remediation", "success" if success else "failure"]
            )
            
            logger.info(f"Pod restart completed - success: {success}")
            return success
        except Exception as e:
            logger.error(f"Error restarting pod: {str(e)}")
            # Record failed attempt
            attempt = RestartAttempt(datetime.now(), False, reason)
            restart_attempts.append(attempt)
            return False

async def create_github_issue(title: str, body: str, labels: List[str]) -> Optional[Dict[str, Any]]:
    """Create a GitHub issue"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GITHUB_MCP_URL}/issues",
                json={
                    "title": title,
                    "body": body,
                    "labels": labels
                },
                timeout=5.0
            )
            if response.status_code == 200:
                logger.info(f"Created GitHub issue: {title}")
                return response.json()
            else:
                logger.error(f"Failed to create GitHub issue: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating GitHub issue: {str(e)}")
            return None

async def create_grafana_annotation(text: str) -> Optional[Dict[str, Any]]:
    """Create a Grafana annotation"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GRAFANA_MCP_URL}/annotations",
                json={
                    "text": text,
                    "tags": ["ai-agent"]
                },
                timeout=5.0
            )
            if response.status_code == 200:
                logger.info(f"Created Grafana annotation: {text}")
                return response.json()
            else:
                logger.error(f"Failed to create Grafana annotation: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating annotation: {str(e)}")
            return None

async def request_manual_intervention(issue_type: str, metrics: Dict[str, Any]):
    """Create GitHub issue for manual intervention"""
    global manual_intervention_requested
    
    if manual_intervention_requested:
        return
    
    manual_intervention_requested = True
    
    title = f"URGENT: Manual Intervention Required - {issue_type}"
    body = (
        f"The application is experiencing persistent issues that could not be resolved automatically.\n\n"
        f"Current Metrics:\n"
        f"- CPU Usage: {metrics['cpu_usage']*100:.1f}%\n"
        f"- Memory Usage: {metrics['memory_usage']:.1f}MB\n"
        f"- Health Status: {metrics['health_status']}\n\n"
        f"Auto-remediation attempts:\n"
        f"- Failed restarts today: {len([a for a in restart_attempts if not a.successful])}\n"
        f"- Max failed restarts per day: {MAX_FAILED_RESTARTS_PER_DAY}\n\n"
        f"Please investigate and resolve the underlying issue."
    )
    
    await create_github_issue(
        title,
        body,
        ["urgent", "needs-attention", "manual-intervention"]
    )
    
    await create_grafana_annotation(
        f"Manual intervention requested: {issue_type} - Auto-remediation limit reached"
    )

@app.on_event("startup")
async def startup_event():
    """Start monitoring on app startup"""
    asyncio.create_task(monitor_and_fix())
    logger.info("Started monitoring loop")

async def monitor_and_fix():
    """Main monitoring and remediation loop"""
    logger.info("Starting monitoring loop...")
    
    while True:
        try:
            metrics = await check_app_health()
            
            # Reset manual intervention flag if metrics are healthy
            if await check_metrics_healthy(metrics):
                global manual_intervention_requested
                manual_intervention_requested = False
            
            # Check CPU usage
            if metrics["cpu_usage"] > 0.8:  # 80% threshold
                logger.warning(f"High CPU usage detected: {metrics['cpu_usage']*100:.1f}%")
                
                if await can_restart_pod():
                    if await restart_pod(f"high CPU usage ({metrics['cpu_usage']*100:.1f}%)"):
                        incident = Incident(
                            f"High CPU usage detected: {metrics['cpu_usage']*100:.1f}%",
                            "high",
                            ["Pod restart"]
                        )
                        incident_history.append(incident)
                else:
                    # Request manual intervention
                    await request_manual_intervention("High CPU Usage", metrics)
            
            # Check memory usage
            if metrics["memory_usage"] > 90:  # 90MB threshold
                logger.warning(f"High memory usage detected: {metrics['memory_usage']:.1f}MB")
                
                if await can_restart_pod():
                    if await restart_pod(f"high memory usage ({metrics['memory_usage']:.1f}MB)"):
                        incident = Incident(
                            f"High memory usage detected: {metrics['memory_usage']:.1f}MB",
                            "high",
                            ["Pod restart"]
                        )
                        incident_history.append(incident)
                else:
                    # Request manual intervention
                    await request_manual_intervention("High Memory Usage", metrics)
            
            # Check health status
            if metrics["health_status"] == 0:
                logger.warning("Application health check failed")
                
                if await can_restart_pod():
                    if await restart_pod("failed health check"):
                        incident = Incident(
                            "Application health check failed",
                            "critical",
                            ["Pod restart"]
                        )
                        incident_history.append(incident)
                else:
                    # Request manual intervention
                    await request_manual_intervention("Health Check Failure", metrics)
        
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
        
        # Wait before next check
        await asyncio.sleep(10)  # Check every 10 seconds

@app.get("/incidents")
async def get_incidents():
    """Get incident history"""
    return [
        {
            "timestamp": incident.timestamp.isoformat(),
            "description": incident.description,
            "severity": incident.severity,
            "actions": incident.actions
        }
        for incident in incident_history
    ]

@app.get("/restarts")
async def get_restarts():
    """Get restart history"""
    failed_restarts = [a for a in restart_attempts if not a.successful]
    successful_restarts = [a for a in restart_attempts if a.successful]
    
    return {
        "total_restarts": len(restart_attempts),
        "successful_restarts": len(successful_restarts),
        "failed_restarts_today": len([
            a for a in failed_restarts 
            if a.timestamp > datetime.now() - timedelta(days=1)
        ]),
        "max_failed_restarts_per_day": MAX_FAILED_RESTARTS_PER_DAY,
        "restart_history": [
            {
                "timestamp": attempt.timestamp.isoformat(),
                "successful": attempt.successful,
                "reason": attempt.reason
            }
            for attempt in restart_attempts
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("AGENT_PORT", 5003))
    logger.info(f"Starting agent on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
