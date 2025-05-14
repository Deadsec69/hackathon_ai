import os
import json
import time
import uuid
import datetime
from typing import Dict, List, Any, Optional
from dataclasses import asdict

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_client import mcp_manager
from incident_store import incident_store, Incident
from sub_agents.logger import medic_logger, forge_logger, vision_logger, herald_logger

def remediate_issue(state: Dict[str, Any]) -> Dict[str, Any]:
    """Medic Agent: Remediate the issue by restarting the pod and creating a GitHub issue"""
    if state.get("error"):
        medic_logger.warning(f"Medic is skipping remediation due to error: {state.get('error')}")
        return state
    
    medic_logger.info("Medic is starting remediation")
    
    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])
    
    if not issues:
        medic_logger.warning("Medic found no issues to remediate")
        return state
    
    # Sort issues by severity
    issues.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x["severity"], 0), reverse=True)
    
    # Get the most severe issue
    issue = issues[0]
    pod_name = issue["pod_name"]
    namespace = issue["namespace"]
    issue_type = issue["type"]
    value = issue["value"]
    threshold = issue["threshold"]
    severity = issue["severity"]
    
    medic_logger.info(f"Medic is addressing issue: {json.dumps(issue)}")
    
    try:
        # Restart the pod
        medic_logger.info(f"Medic is restarting pod {pod_name} in namespace {namespace}")
        medic_logger.info(f"MEDIC ATTEMPTING TO RESTART POD: {pod_name} in namespace {namespace} due to {issue_type} issue")
        restart_result = mcp_manager.use_tool("kubernetes", "restart_pod", {
            "namespace": namespace,
            "pod_name": pod_name
        })
        medic_logger.info(f"Medic received restart result: {json.dumps(restart_result)}")
        medic_logger.info(f"MEDIC POD RESTART COMPLETED: {pod_name} in namespace {namespace}")
        herald_logger.info(f"Herald: Medic has successfully restarted pod {pod_name} in namespace {namespace}")
        
        # Increment restart count
        medic_logger.info(f"Medic is incrementing restart count for {pod_name}")
        restart_count = incident_store.increment_restart_count(pod_name, namespace)
        medic_logger.info(f"Medic updated restart count to: {restart_count}")
        
        # Create GitHub issue
        forge_logger.info(f"Forge is creating incident ticket for {issue_type.upper()} issue in pod {pod_name}")
        issue_title = f"{issue_type.upper()} usage alert for pod {pod_name}"
        issue_body = f"""
# {issue_type.upper()} Usage Alert

## Pod Information
- **Pod Name**: {pod_name}
- **Namespace**: {namespace}
- **Severity**: {severity}

## Metrics
- **{issue_type.upper()} Usage**: {value:.2f}%
- **Threshold**: {threshold}%
- **Timestamp**: {datetime.datetime.fromtimestamp(analysis.get("timestamp", time.time())).strftime('%Y-%m-%d %H:%M:%S')}

## Action Taken
The pod has been automatically restarted to mitigate the issue.

## Restart Count
This pod has been restarted {restart_count} times today.

## Next Steps
If this issue persists, consider:
1. Investigating the application logs
2. Checking for memory leaks or inefficient code
3. Adjusting resource limits
        """
        
        forge_logger.info(f"Forge is creating GitHub issue: {issue_title}")
        github_issue = mcp_manager.use_tool("github", "create_issue", {
            "title": issue_title,
            "body": issue_body,
            "labels": [issue_type, "auto-remediated", severity]
        })
        forge_logger.info(f"Forge created GitHub issue #{github_issue.get('number')}: {github_issue.get('html_url')}")
        herald_logger.info(f"Herald: Forge has created issue #{github_issue.get('number')} for {issue_type} alert in {pod_name}")
        
        # Create incident record
        incident_id = str(uuid.uuid4())
        forge_logger.info(f"Forge is creating incident record with ID {incident_id}")
        incident = Incident(
            id=incident_id,
            type=issue_type,
            pod_name=pod_name,
            namespace=namespace,
            timestamp=int(time.time()),
            severity=severity,
            metrics={
                "value": value,
                "threshold": threshold
            },
            action_taken="restart_pod",
            github_issue=github_issue
        )
        
        incident_store.add_incident(incident)
        forge_logger.info(f"Forge created incident record {incident_id}")
        
        # Create Grafana annotation
        dashboard_id = 1  # Assuming dashboard ID 1 for the test application dashboard
        vision_logger.info(f"Vision is updating dashboard {dashboard_id} with alert for {pod_name}")
        annotation_result = mcp_manager.use_tool("grafana", "create_annotation", {
            "dashboard_id": dashboard_id,
            "time": int(time.time() * 1000),  # Convert to milliseconds
            "text": f"Pod {pod_name} restarted due to high {issue_type} usage ({value:.2f}%)",
            "tags": [issue_type, "auto-remediated", severity]
        })
        vision_logger.info(f"Vision created dashboard annotation: {json.dumps(annotation_result)}")
        herald_logger.info(f"Herald: Vision has updated the monitoring dashboard with {issue_type} alert for {pod_name}")
        
        action = {
            "type": "remediate",
            "pod_name": pod_name,
            "namespace": namespace,
            "issue_type": issue_type,
            "restart_result": restart_result,
            "restart_count": restart_count,
            "github_issue": github_issue,
            "incident_id": incident_id,
            "annotation": annotation_result
        }
        
        medic_logger.info(f"Medic completed remediation successfully")
        herald_logger.info(f"Herald: Incident {incident_id} remediated - Pod {pod_name} restarted and issue #{github_issue.get('number')} created")
        
        return {
            **state,
            "action": action
        }
    except Exception as e:
        medic_logger.error(f"Error remediating issue: {str(e)}")
        return {
            **state,
            "error": f"Error remediating issue: {str(e)}"
        }
