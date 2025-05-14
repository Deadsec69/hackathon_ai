from typing import Dict, List, Any, Optional
from dataclasses import asdict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from incident_store import incident_store
from sub_agents.logger import forge_logger, herald_logger

def get_incidents(
    resolved: Optional[bool] = None,
    incident_type: Optional[str] = None,
    pod_name: Optional[str] = None,
    namespace: Optional[str] = None,
    since: Optional[int] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Forge Agent: Get incidents with optional filtering"""
    forge_logger.info(f"Forge is retrieving incidents with filters: resolved={resolved}, type={incident_type}, pod={pod_name}, namespace={namespace}, limit={limit}")
    
    incidents = incident_store.get_incidents(
        resolved=resolved,
        incident_type=incident_type,
        pod_name=pod_name,
        namespace=namespace,
        since=since,
        limit=limit
    )
    
    forge_logger.info(f"Forge found {len(incidents)} incidents matching criteria")
    herald_logger.info(f"Herald: Forge has retrieved {len(incidents)} incidents from the incident store")
    
    return [asdict(incident) for incident in incidents]

def get_restart_counts() -> Dict[str, Dict[str, int]]:
    """Forge Agent: Get all restart counts"""
    forge_logger.info("Forge is retrieving pod restart counts")
    restart_counts = incident_store.get_all_restart_counts()
    
    # Count total restarts across all pods and days
    total_restarts = sum(sum(counts.values()) for counts in restart_counts.values())
    forge_logger.info(f"Forge found restart counts for {len(restart_counts)} days, total restarts: {total_restarts}")
    herald_logger.info(f"Herald: Forge has retrieved restart counts showing {total_restarts} total pod restarts")
    
    return restart_counts
