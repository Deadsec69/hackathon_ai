import json
from typing import Dict, List, Any, Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_client import mcp_manager
from sub_agents.logger import vision_logger, herald_logger

def create_dashboard_annotation(
    dashboard_id: int,
    text: str,
    tags: List[str],
    time: Optional[int] = None
) -> Dict[str, Any]:
    """Vision Agent: Create a dashboard annotation in Grafana"""
    vision_logger.info(f"Vision is creating dashboard annotation for dashboard {dashboard_id}")
    
    # If time is not provided, use current time in milliseconds
    if time is None:
        import time as time_module
        time = int(time_module.time() * 1000)
    
    try:
        # Create the annotation
        annotation_result = mcp_manager.use_tool("grafana", "create_annotation", {
            "dashboard_id": dashboard_id,
            "time": time,
            "text": text,
            "tags": tags
        })
        
        vision_logger.info(f"Vision created dashboard annotation: {json.dumps(annotation_result)}")
        herald_logger.info(f"Herald: Vision has updated the monitoring dashboard with annotation: {text}")
        
        return annotation_result
    except Exception as e:
        vision_logger.error(f"Vision encountered error creating dashboard annotation: {str(e)}")
        return {"error": str(e)}

def update_dashboard_panel(
    dashboard_id: int,
    panel_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Vision Agent: Update a dashboard panel in Grafana"""
    vision_logger.info(f"Vision is updating dashboard panel {panel_id} in dashboard {dashboard_id}")
    
    try:
        # Update the panel
        update_result = mcp_manager.use_tool("grafana", "update_panel", {
            "dashboard_id": dashboard_id,
            "panel_id": panel_id,
            "title": title,
            "description": description
        })
        
        vision_logger.info(f"Vision updated dashboard panel: {json.dumps(update_result)}")
        herald_logger.info(f"Herald: Vision has updated panel {panel_id} in dashboard {dashboard_id}")
        
        return update_result
    except Exception as e:
        vision_logger.error(f"Vision encountered error updating dashboard panel: {str(e)}")
        return {"error": str(e)}
