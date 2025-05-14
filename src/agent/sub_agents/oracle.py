from typing import Dict, List, Any, Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from incident_store import incident_store
from sub_agents.logger import oracle_logger, herald_logger

def decide_action(state: Dict[str, Any]) -> Dict[str, Any]:
    """Oracle Agent: Decide what action to take based on analysis"""
    if state.get("error"):
        oracle_logger.warning(f"Oracle is skipping action decision due to error: {state.get('error')}")
        return state
    
    oracle_logger.info("Oracle is deciding action based on analysis")
    
    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])
    
    # Get thresholds from environment or use defaults
    MAX_RESTARTS_PER_DAY = 10
    ANALYSIS_THRESHOLD = 4
    
    oracle_logger.info(f"Oracle evaluating {len(issues)} issues")
    
    if not issues:
        oracle_logger.info("Oracle determines no issues found, no action needed")
        # Return a dictionary with a "next" key instead of a string
        return {
            **state,
            "decide": {"next": "no_action"}
        }
    
    # Sort issues by severity
    issues.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x["severity"], 0), reverse=True)
    
    # Get the most severe issue
    issue = issues[0]
    pod_name = issue["pod_name"]
    namespace = issue["namespace"]
    
    oracle_logger.info(f"Oracle identified most severe issue: {issue}")
    
    # Check restart count
    restart_count = incident_store.get_restart_count(pod_name, namespace)
    oracle_logger.info(f"Oracle checking restart history for {pod_name}: {restart_count} restarts today")
    
    if restart_count >= ANALYSIS_THRESHOLD:
        oracle_logger.info(f"Oracle determines restart count {restart_count} exceeds analysis threshold {ANALYSIS_THRESHOLD}, directing Smith to analyze code")
        herald_logger.info(f"Herald: Oracle has determined code analysis is needed due to persistent issues with {pod_name}")
        # Return a dictionary with a "next" key instead of a string
        return {
            **state,
            "decide": {"next": "analyze_code"}
        }
    elif restart_count < MAX_RESTARTS_PER_DAY:
        oracle_logger.info(f"Oracle determines restart count {restart_count} is below max restarts {MAX_RESTARTS_PER_DAY}, directing Medic to remediate")
        herald_logger.info(f"Herald: Oracle has determined pod restart is needed for {pod_name}")
        # Return a dictionary with a "next" key instead of a string
        return {
            **state,
            "decide": {"next": "remediate"}
        }
    else:
        # We've reached the maximum number of restarts, but not the analysis threshold
        # This is an edge case, so we'll just remediate
        oracle_logger.info(f"Oracle determines restart count {restart_count} equals max restarts {MAX_RESTARTS_PER_DAY}, directing Medic to remediate")
        herald_logger.info(f"Herald: Oracle has determined final pod restart is needed for {pod_name} before escalation")
        # Return a dictionary with a "next" key instead of a string
        return {
            **state,
            "decide": {"next": "remediate"}
        }

def route_decide(state):
    """Oracle Agent: Route based on the decision"""
    # Get the decision from the state
    decision = state.get("decide", {}).get("next", "no_action")
    oracle_logger.info(f"Oracle routing workflow to: {decision}")
    
    if decision == "remediate":
        return "remediate"
    elif decision == "analyze_code":
        return "analyze_code"
    else:
        return "format_response"
