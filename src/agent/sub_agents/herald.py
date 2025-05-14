import json
from typing import Dict, List, Any, Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sub_agents.logger import herald_logger

def format_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """Herald Agent: Format the response for the API"""
    herald_logger.info("Herald is formatting final response")
    
    if state.get("error"):
        herald_logger.warning(f"Herald is formatting error response: {state.get('error')}")
        response = {
            "status": "error",
            "error": state["error"]
        }
    else:
        action = state.get("action", {})
        action_type = action.get("type")
        
        if action_type == "remediate":
            herald_logger.info("Herald is formatting remediate response")
            response = {
                "status": "success",
                "action": "remediate",
                "pod_name": action.get("pod_name"),
                "namespace": action.get("namespace"),
                "issue_type": action.get("issue_type"),
                "restart_count": action.get("restart_count"),
                "github_issue_number": action.get("github_issue", {}).get("number"),
                "github_issue_url": action.get("github_issue", {}).get("html_url"),
                "incident_id": action.get("incident_id")
            }
        elif action_type == "analyze_code":
            herald_logger.info("Herald is formatting analyze_code response")
            response = {
                "status": "success",
                "action": "analyze_code",
                "pod_name": action.get("pod_name"),
                "namespace": action.get("namespace"),
                "issue_type": action.get("issue_type"),
                "github_issue_number": action.get("github_issue", {}).get("number"),
                "github_issue_url": action.get("github_issue", {}).get("html_url"),
                "github_pr_number": action.get("github_pr", {}).get("number"),
                "github_pr_url": action.get("github_pr", {}).get("html_url"),
                "incident_id": action.get("incident_id")
            }
        else:
            herald_logger.info("Herald is formatting no_action response")
            response = {
                "status": "success",
                "action": "no_action",
                "message": "No issues detected"
            }
    
    herald_logger.info(f"Herald completed final response: {json.dumps(response)}")
    
    return {
        **state,
        "response": response
    }
