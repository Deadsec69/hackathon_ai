
import json
import logging
import sys
import time

from dotenv import load_dotenv
from incident_store import incident_store, Incident
from mcp_client import mcp_manager
from langchain_anthropic import ChatAnthropic
from agent import AgentState, ANALYSIS_THRESHOLD, MAX_RESTARTS_PER_DAY
import uuid
import datetime
# import openai
# from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[
                       logging.StreamHandler(sys.stdout)
                   ])
logger = logging.getLogger("agent")

# Load environment variables
load_dotenv()
# Claude setup
llm = ChatAnthropic(model="claude-3-sonnet-20240229", temperature=0)

def decide_action(state: AgentState) -> AgentState:
    """Decide what action to take based on analysis"""
    if state.get("error"):
        logger.warning(f"Skipping action decision due to error: {state.get('error')}")
        return state

    logger.info("Deciding action based on analysis")

    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])

    logger.info(f"Issues found: {len(issues)}")

    if not issues:
        logger.info("No issues found, no action needed")
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

    logger.info(f"Most severe issue: {json.dumps(issue)}")

    # Check restart count
    restart_count = incident_store.get_restart_count(pod_name, namespace)
    logger.info(f"Current restart count for {pod_name}: {restart_count}")

    if restart_count >= ANALYSIS_THRESHOLD:
        logger.info(f"Restart count {restart_count} exceeds analysis threshold {ANALYSIS_THRESHOLD}, will analyze code")
        # Return a dictionary with a "next" key instead of a string
        return {
            **state,
            "decide": {"next": "analyze_code"}
        }
    elif restart_count < MAX_RESTARTS_PER_DAY:
        logger.info(f"Restart count {restart_count} is below max restarts {MAX_RESTARTS_PER_DAY}, will remediate")
        # Return a dictionary with a "next" key instead of a string
        return {
            **state,
            "decide": {"next": "remediate"}
        }
    else:
        # We've reached the maximum number of restarts, but not the analysis threshold
        # This is an edge case, so we'll just remediate
        logger.info(f"Restart count {restart_count} equals max restarts {MAX_RESTARTS_PER_DAY}, will remediate")
        # Return a dictionary with a "next" key instead of a string
        return {
            **state,
            "decide": {"next": "remediate"}
        }


def remediate_issue(state: AgentState) -> AgentState:
    """Remediate the issue by restarting the pod and creating a GitHub issue"""
    if state.get("error"):
        logger.warning(f"Skipping remediation due to error: {state.get('error')}")
        return state

    logger.info("Starting remediation")

    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])

    if not issues:
        logger.warning("No issues found, skipping remediation")
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

    logger.info(f"Remediating issue: {json.dumps(issue)}")

    try:
        # Restart the pod
        logger.info(f"Restarting pod {pod_name} in namespace {namespace}")
        logger.info(f"ATTEMPTING TO RESTART POD: {pod_name} in namespace {namespace} due to {issue_type} issue")
        restart_result = mcp_manager.use_tool("kubernetes", "restart_pod", {
            "namespace": namespace,
            "pod_name": pod_name
        })
        logger.info(f"Restart result: {json.dumps(restart_result)}")
        logger.info(f"POD RESTART COMPLETED: {pod_name} in namespace {namespace}, result: {json.dumps(restart_result)}")

        # Increment restart count
        logger.info(f"Incrementing restart count for {pod_name}")
        restart_count = incident_store.increment_restart_count(pod_name, namespace)
        logger.info(f"New restart count: {restart_count}")

        # Create GitHub issue
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

        logger.info(f"Creating GitHub issue: {issue_title}")
        github_issue = mcp_manager.use_tool("github", "create_issue", {
            "title": issue_title,
            "body": issue_body,
            "labels": [issue_type, "auto-remediated", severity]
        })
        logger.info(f"GitHub issue created: {json.dumps(github_issue)}")

        # Create incident record
        incident_id = str(uuid.uuid4())
        logger.info(f"Creating incident record with ID {incident_id}")
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
        logger.info(f"Incident record created")

        # Create Grafana annotation
        dashboard_id = 1  # Assuming dashboard ID 1 for the test application dashboard
        logger.info(f"Creating Grafana annotation for dashboard {dashboard_id}")
        annotation_result = mcp_manager.use_tool("grafana", "create_annotation", {
            "dashboard_id": dashboard_id,
            "time": int(time.time() * 1000),  # Convert to milliseconds
            "text": f"Pod {pod_name} restarted due to high {issue_type} usage ({value:.2f}%)",
            "tags": [issue_type, "auto-remediated", severity]
        })
        logger.info(f"Grafana annotation created: {json.dumps(annotation_result)}")

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

        logger.info(f"Remediation completed successfully")

        return {
            **state,
            "action": action
        }
    except Exception as e:
        logger.error(f"Error remediating issue: {str(e)}", exc_info=True)
        return {
            **state,
            "error": f"Error remediating issue: {str(e)}"
        }
