import os
import json
import time
import uuid
import datetime
import logging
import sys
from typing import Dict, List, Any, Optional, Union, TypedDict, Annotated, Literal
from dataclasses import asdict
from dotenv import load_dotenv
# import openai
import anthropic
from langchain_anthropic import ChatAnthropic
# from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

from mcp_client import mcp_manager
from incident_store import incident_store, Incident

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[
                       logging.StreamHandler(sys.stdout)
                   ])
logger = logging.getLogger("agent")

# Load environment variables
load_dotenv()

# Initialize Anthropic client
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")

# Initialize OpenAI client (commented out)
# openai_api_key = os.environ.get("OPENAI_API_KEY")
# if not openai_api_key:
#     raise ValueError("OPENAI_API_KEY environment variable not set")

# Constants
MAX_RESTARTS_PER_DAY = int(os.environ.get("MAX_RESTARTS_PER_DAY", "10"))
ANALYSIS_THRESHOLD = int(os.environ.get("ANALYSIS_THRESHOLD", "4"))
# ANALYSIS_THRESHOLD = 1
CPU_THRESHOLD = 10  # CPU usage percentage threshold (lowered to 10% for testing)
MEMORY_THRESHOLD = 600000000  # Memory threshold in bytes (500 MB)

# State definition
class AgentState(TypedDict):
    """State for the agent workflow"""
    input: Dict[str, Any]
    metrics: Dict[str, Any]
    analysis: Dict[str, Any]
    action: Dict[str, Any]
    response: Dict[str, Any]
    error: Optional[str]

# LLM setup
# OpenAI setup (commented out)
# llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Claude setup
llm = ChatAnthropic(model="claude-3-sonnet-20240229", temperature=0)

# Node functions
def monitor_metrics(state: AgentState) -> AgentState:
    """Monitor metrics from Prometheus"""
    try:
        logger.info("Starting to monitor metrics")
        
        # Query Prometheus for CPU metrics
        logger.info("Querying Prometheus for CPU metrics")
        cpu_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_cpu_usage_percent"
        })
        logger.info(f"CPU metrics result: {json.dumps(cpu_result)}")
        
        # Query Prometheus for memory metrics
        logger.info("Querying Prometheus for memory metrics")
        memory_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_memory_usage_bytes"
        })
        logger.info(f"Memory metrics result: {json.dumps(memory_result)}")
        
        # Query Prometheus for CPU spike counter
        logger.info("Querying Prometheus for CPU spike counter")
        cpu_spike_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_cpu_spike_total"
        })
        logger.info(f"CPU spike counter result: {json.dumps(cpu_spike_result)}")
        
        # Query Prometheus for memory spike counter
        logger.info("Querying Prometheus for memory spike counter")
        memory_spike_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_memory_spike_total"
        })
        logger.info(f"Memory spike counter result: {json.dumps(memory_spike_result)}")
        
        # Get Kubernetes pods
        logger.info("Getting Kubernetes pods")
        pods_result = mcp_manager.use_tool("kubernetes", "list_pods", {
            "namespace": "default"
        })
        logger.info(f"Pods result: {json.dumps(pods_result)}")
        
        # Process metrics
        metrics = {
            "cpu": process_metric_result(cpu_result),
            "memory": process_metric_result(memory_result),
            "cpu_spike": process_metric_result(cpu_spike_result),
            "memory_spike": process_metric_result(memory_spike_result),
            "pods": pods_result.get("pods", []),
            "timestamp": int(time.time())
        }
        
        logger.info(f"Processed metrics: {json.dumps(metrics)}")
        
        return {
            **state,
            "metrics": metrics,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error monitoring metrics: {str(e)}", exc_info=True)
        return {
            **state,
            "error": f"Error monitoring metrics: {str(e)}"
        }

def process_metric_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process metric result from Prometheus"""
    processed = []
    
    if "result" in result:
        for item in result["result"]:
            metric = item.get("metric", {})
            value = item.get("value", [0, "0"])
            
            if len(value) >= 2:
                timestamp, value_str = value
                try:
                    value_float = float(value_str)
                except ValueError:
                    value_float = 0
                
                processed.append({
                    "metric": metric,
                    "value": value_float,
                    "timestamp": timestamp
                })
    
    return processed

def analyze_metrics(state: AgentState) -> AgentState:
    """Analyze metrics to detect issues"""
    if state.get("error"):
        logger.warning(f"Skipping metrics analysis due to error: {state.get('error')}")
        return state
    
    logger.info("Starting metrics analysis")
    
    metrics = state.get("metrics", {})
    cpu_metrics = metrics.get("cpu", [])
    memory_metrics = metrics.get("memory", [])
    pods = metrics.get("pods", [])
    
    logger.info(f"CPU metrics: {json.dumps(cpu_metrics)}")
    logger.info(f"Memory metrics: {json.dumps(memory_metrics)}")
    logger.info(f"Pods: {json.dumps(pods)}")
    
    issues = []
    
    # Check CPU usage
    for cpu_metric in cpu_metrics:
        logger.info(f"Checking CPU metric: {json.dumps(cpu_metric)}")
        if cpu_metric["value"] > CPU_THRESHOLD:
            logger.info(f"CPU usage {cpu_metric['value']} exceeds threshold {CPU_THRESHOLD}")
            pod_name = cpu_metric["metric"].get("instance", "unknown")
            namespace = "default"
            
            # Find the pod in the list
            for pod in pods:
                if pod["name"] in pod_name:
                    pod_name = pod["name"]
                    namespace = pod["namespace"]
                    break
            
            logger.info(f"Found pod {pod_name} in namespace {namespace}")
            
            issues.append({
                "type": "cpu",
                "pod_name": pod_name,
                "namespace": namespace,
                "value": cpu_metric["value"],
                "threshold": CPU_THRESHOLD,
                "severity": calculate_severity(cpu_metric["value"], CPU_THRESHOLD)
            })
    
    # Check memory usage
    for memory_metric in memory_metrics:
        # Get memory value in bytes
        memory_value = memory_metric["value"]
        
        # Calculate percentage for logging (assuming 1GB = 100%)
        memory_percent = memory_value / (1024 * 1024 * 1024) * 100
        
        logger.info(f"Checking memory metric: {json.dumps(memory_metric)}, value: {memory_value} bytes ({memory_percent:.2f}%)")
        
        if memory_value > MEMORY_THRESHOLD:
            logger.info(f"Memory usage {memory_value} bytes exceeds threshold {MEMORY_THRESHOLD} bytes")
            pod_name = memory_metric["metric"].get("instance", "unknown")
            namespace = "default"
            
            # Find the pod in the list
            for pod in pods:
                if pod["name"] in pod_name:
                    pod_name = pod["name"]
                    namespace = pod["namespace"]
                    break
            
            logger.info(f"Found pod {pod_name} in namespace {namespace}")
            
            issues.append({
                "type": "memory",
                "pod_name": pod_name,
                "namespace": namespace,
                "value": memory_value,
                "threshold": MEMORY_THRESHOLD,
                "severity": calculate_severity(memory_value, MEMORY_THRESHOLD)
            })
    
    analysis = {
        "issues": issues,
        "timestamp": int(time.time())
    }
    
    logger.info(f"Analysis result: {json.dumps(analysis)}")
    
    return {
        **state,
        "analysis": analysis
    }

def calculate_severity(value: float, threshold: float) -> str:
    """Calculate severity based on value and threshold"""
    if value > threshold * 1.5:
        return "high"
    elif value > threshold * 1.2:
        return "medium"
    else:
        return "low"

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

def analyze_code(state: AgentState) -> AgentState:
    """Analyze code and logs to find the root cause and create a PR"""
    if state.get("error"):
        logger.warning(f"Skipping code analysis due to error: {state.get('error')}")
        return state
    
    logger.info("Starting code analysis")
    
    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])
    
    if not issues:
        logger.warning("No issues found, skipping code analysis")
        return state
    
    # Sort issues by severity
    issues.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x["severity"], 0), reverse=True)
    
    # Get the most severe issue
    issue = issues[0]
    pod_name = issue["pod_name"]
    namespace = issue["namespace"]
    issue_type = issue["type"]
    
    logger.info(f"Analyzing code for issue: {json.dumps(issue)}")
    
    try:
        # Get pod logs
        logger.info(f"Getting logs for pod {pod_name} in namespace {namespace}")
        logs_result = mcp_manager.use_tool("kubernetes", "get_logs", {
            "namespace": namespace,
            "pod_name": pod_name,
            "tail_lines": 1000
        })
        
        logs = logs_result.get("logs", "")
        logger.info(f"Retrieved {len(logs)} bytes of logs")
        
        # Get application code using the Kubernetes MCP server
        logger.info("Getting application code using Kubernetes MCP server")
        app_code = ""
        try:
            # Use the Kubernetes MCP server to get the application code
            app_code_result = mcp_manager.use_tool("kubernetes", "get_app_code", {
                "namespace": namespace,
                "pod_name": pod_name
            })
            
            app_code = app_code_result.get("code", "")
            logger.info(f"Retrieved {len(app_code)} bytes of application code")
        except Exception as e:
            logger.error(f"Error getting application code: {str(e)}")
            app_code = "# Error: Could not retrieve application code"
        
        # Step 1: Use LLM to generate the code fix as plain text
        code_fix_prompt = ChatPromptTemplate.from_template("""
        You are an AI agent tasked with analyzing logs, application code, and providing complete code fixes for Kubernetes pods.
        
        # Issue Information
        - Pod Name: {pod_name}
        - Namespace: {namespace}
        - Issue Type: {issue_type} (high usage)
        - This pod has been restarted multiple times today due to high {issue_type} usage
        
        # Pod Logs
        ```
        {logs}
        ```
        
        # Application Code
        ```python
        {app_code}
        ```
        
        # Task
        1. Analyze the logs and application code to identify patterns or issues that might be causing high {issue_type} usage
        2. Provide a COMPLETE code fix that resolves the issue
        3. Your response should ONLY include the ENTIRE function or class that needs to be modified, with all the changes implemented
        4. Do not include any explanations, JSON formatting, or anything else - ONLY the complete updated code for the function/class
        
        IMPORTANT: Include the ENTIRE function or class that needs to be modified, not just the changes.
        For example, if you're modifying a function, include the entire function definition and body.
        
        Respond with ONLY the complete updated code, nothing else.
        """)
        
        logger.info("Step 1: Generating code fix with LLM")
        code_fix_chain = code_fix_prompt | llm | StrOutputParser()
        
        code_fix_result = code_fix_chain.invoke({
            "pod_name": pod_name,
            "namespace": namespace,
            "issue_type": issue_type,
            "logs": logs,
            "app_code": app_code
        })
        
        logger.info(f"Code fix generated: {len(code_fix_result)} bytes")
        code_fix_result = code_fix_result.replace("```","").replace("python","")
        logger.info(f"Code fix generated: {code_fix_result} ")
        # Step 2: Use LLM to analyze and format the response with the code fix
        analysis_prompt = ChatPromptTemplate.from_template("""
        You are an AI agent tasked with analyzing logs, application code, and providing complete code fixes for Kubernetes pods.
        
        # Issue Information
        - Pod Name: {pod_name}
        - Namespace: {namespace}
        - Issue Type: {issue_type} (high usage)
        - This pod has been restarted multiple times today due to high {issue_type} usage
        
        # Pod Logs
        ```
        {logs}
        ```
        
        # Application Code
        ```python
        {app_code}
        ```
        
        # Generated Code Fix
        ```python
        {code_fix}
        ```
        
        # Task
        1. Analyze the logs, application code, and the generated code fix
        2. Format your response as a JSON object with the following fields:
           - "analysis": Your detailed analysis of the logs, code, and the issue
           - "fix_description": A clear description of the proposed fix
           - "fix_code": The COMPLETE code fix (use the generated code fix provided above)
           - "fix_file": The file that needs to be modified (e.g., "main.py")
           - "pr_title": A title for the pull request
           - "pr_body": A detailed description for the pull request
        
        Respond with only the JSON object, no additional text.
        """)
        
        logger.info("Step 2: Analyzing and formatting response with LLM")
        analysis_chain = analysis_prompt | llm | StrOutputParser()
        
        analysis_result = analysis_chain.invoke({
            "pod_name": pod_name,
            "namespace": namespace,
            "issue_type": issue_type,
            "logs": logs,
            "app_code": app_code,
            "code_fix": code_fix_result
        })
        
        logger.info(f"Analysis result: {len(analysis_result)} bytes")
        logger.info(f"Analysis result: {analysis_result}")
        # Parse the analysis result
        try:
            analysis_data = json.loads(analysis_result)
            logger.info("Successfully parsed LLM analysis result")
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM analysis result as JSON")
            analysis_data = {
                "analysis": "Failed to parse analysis result",
                "fix_description": "Unknown",
                "fix_code": None,
                "fix_file": "Unknown",
                "pr_title": f"Fix high {issue_type} usage in {pod_name}",
                "pr_body": "Failed to generate PR body"
            }
        
        # Create a GitHub issue for the analysis
        issue_title = f"Analysis: {issue_type.upper()} usage in pod {pod_name}"
        issue_body = f"""
# {issue_type.upper()} Usage Analysis

## Pod Information
- **Pod Name**: {pod_name}
- **Namespace**: {namespace}

## Analysis
{analysis_data.get("analysis", "No analysis available")}

## Proposed Fix
{analysis_data.get("fix_description", "No fix description available")}

### Code Change
```
{analysis_data.get("fix_code", "No code change available")}
```

### File to Modify
{analysis_data.get("fix_file", "Unknown")}

## Next Steps
A pull request will be created with the proposed fix.
        """
        
        logger.info(f"Creating GitHub issue: {issue_title}")
        github_issue = mcp_manager.use_tool("github", "create_issue", {
            "title": issue_title,
            "body": issue_body,
            "labels": [issue_type, "analysis", "needs-review"]
        })
        logger.info(f"GitHub issue created: {json.dumps(github_issue)}")
        
        # Create a pull request with the fix
        # For this PoC, we'll just create a PR with a placeholder file
        # In a real implementation, we would get the actual file, modify it, and create a PR
        
        # Create a new branch with a valid name format
        # Use the GitHub issue number in the branch name
        branch_name = f"bug_fix/{github_issue.get('number', 0)}"
        
        # Create a file with the fix
        file_path = analysis_data.get("fix_file")
        file_content = analysis_data.get("fix_code")
        
        # If no specific file or code is provided, create a generic fix file
        if not file_path or not file_content:
            file_path = f"kubernetes/deployment.yaml"
            if issue_type == "memory":
                file_content = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
      - name: test-app
        image: test-app:latest
        resources:
          limits:
            memory: "512Mi"  # Increased memory limit
            cpu: "500m"
          requests:
            memory: "256Mi"  # Increased memory request
            cpu: "100m"
        env:
        - name: NODE_OPTIONS
          value: "--max-old-space-size=256"  # Limit Node.js memory usage
"""
            else:  # CPU issue
                file_content = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  namespace: default
spec:
  replicas: 2  # Increased replicas for better load distribution
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
      - name: test-app
        image: test-app:latest
        resources:
          limits:
            memory: "256Mi"
            cpu: "1000m"  # Increased CPU limit
          requests:
            memory: "128Mi"
            cpu: "200m"  # Increased CPU request
"""
        
        commit_message = f"Fix high {issue_type} usage in {pod_name}"
        
        # Create the branch first
        logger.info(f"Creating branch {branch_name}")
        try:
            branch_result = mcp_manager.use_tool("github", "create_branch", {
                "branch": branch_name,
                "base": "develop"  # Use develop as the base branch
            })
            logger.info(f"Branch created: {json.dumps(branch_result)}")
            
            # Create the file in the new branch
            logger.info(f"Creating file {file_path} in branch {branch_name}")
            file_result = mcp_manager.use_tool("github", "create_file", {
                "path": file_path,
                "content": file_content,
                "message": commit_message,
                "branch": branch_name
            })
            logger.info(f"File created: {json.dumps(file_result)}")
        except Exception as e:
            logger.error(f"Error creating branch or file: {str(e)}")
            file_result = {"error": str(e)}
        
        # Create the pull request
        pr_title = analysis_data.get("pr_title", f"Fix high {issue_type} usage in {pod_name}")
        pr_body = analysis_data.get("pr_body", f"""
# Fix for high {issue_type} usage in {pod_name}

This PR addresses the high {issue_type} usage issue in pod {pod_name}.

## Analysis
{analysis_data.get("analysis", "No analysis available")}

## Changes
{analysis_data.get("fix_description", "No fix description available")}

## Related Issue
Closes #{github_issue.get("number", 0)}
        """)
        
        # We no longer need to create a dummy file since we're creating a real fix file
        
        logger.info(f"Creating pull request: {pr_title}")
        pr_result = mcp_manager.use_tool("github", "create_pull_request", {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": "develop"  # Use develop as the base branch
        })
        logger.info(f"Pull request created: {json.dumps(pr_result)}")
        
        # Create incident record
        incident_id = str(uuid.uuid4())
        logger.info(f"Creating incident record with ID {incident_id}")
        incident = Incident(
            id=incident_id,
            type=issue_type,
            pod_name=pod_name,
            namespace=namespace,
            timestamp=int(time.time()),
            severity=issue["severity"],
            metrics={
                "value": issue["value"],
                "threshold": issue["threshold"]
            },
            action_taken="analyze_code",
            github_issue=github_issue,
            github_pr=pr_result
        )
        
        incident_store.add_incident(incident)
        logger.info(f"Incident record created")
        
        # Create Grafana annotation
        dashboard_id = 1  # Assuming dashboard ID 1 for the test application dashboard
        logger.info(f"Creating Grafana annotation for dashboard {dashboard_id}")
        annotation_result = mcp_manager.use_tool("grafana", "create_annotation", {
            "dashboard_id": dashboard_id,
            "time": int(time.time() * 1000),  # Convert to milliseconds
            "text": f"Code analysis for pod {pod_name} due to persistent high {issue_type} usage",
            "tags": [issue_type, "analysis", "pr-created"]
        })
        logger.info(f"Grafana annotation created: {json.dumps(annotation_result)}")
        
        action = {
            "type": "analyze_code",
            "pod_name": pod_name,
            "namespace": namespace,
            "issue_type": issue_type,
            "analysis": analysis_data,
            "github_issue": github_issue,
            "github_pr": pr_result,
            "incident_id": incident_id,
            "annotation": annotation_result
        }
        
        logger.info(f"Code analysis completed successfully")
        
        return {
            **state,
            "action": action
        }
    except Exception as e:
        logger.error(f"Error analyzing code: {str(e)}", exc_info=True)
        return {
            **state,
            "error": f"Error analyzing code: {str(e)}"
        }

def format_response(state: AgentState) -> AgentState:
    """Format the response for the API"""
    logger.info("Formatting response")
    
    if state.get("error"):
        logger.warning(f"Formatting error response: {state.get('error')}")
        response = {
            "status": "error",
            "error": state["error"]
        }
    else:
        action = state.get("action", {})
        action_type = action.get("type")
        
        if action_type == "remediate":
            logger.info("Formatting remediate response")
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
            logger.info("Formatting analyze_code response")
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
            logger.info("Formatting no_action response")
            response = {
                "status": "success",
                "action": "no_action",
                "message": "No issues detected"
            }
    
    logger.info(f"Final response: {json.dumps(response)}")
    
    return {
        **state,
        "response": response
    }

# Define the routing function for conditional edges
def route_decide(state):
    """Route based on the decision"""
    # Get the decision from the state
    decision = state.get("decide", {}).get("next", "no_action")
    logger.info(f"Routing decision: {decision}")
    
    if decision == "remediate":
        return "remediate"
    elif decision == "analyze_code":
        return "analyze_code"
    else:
        return "format_response"

# Define the workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("monitor", monitor_metrics)
workflow.add_node("analyze", analyze_metrics)
workflow.add_node("decide", decide_action)
workflow.add_node("remediate", remediate_issue)
workflow.add_node("analyze_code", analyze_code)
workflow.add_node("format_response", format_response)

# Add edges
workflow.add_edge(START, "monitor")  # Add edge from START to monitor
workflow.add_edge("monitor", "analyze")
workflow.add_edge("analyze", "decide")

# Add conditional edges using a routing function
workflow.add_conditional_edges(
    "decide",
    route_decide
)

workflow.add_edge("remediate", "format_response")
workflow.add_edge("analyze_code", "format_response")
workflow.add_edge("format_response", END)

# Compile the workflow
agent = workflow.compile()

def run_agent(input_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run the agent workflow"""
    if input_data is None:
        input_data = {}
    
    logger.info("Starting agent run")
    
    # Clear old restart counts
    incident_store.clear_old_restart_counts()
    
    # Run the workflow
    result = agent.invoke({
        "input": input_data,
        "metrics": {},
        "analysis": {},
        "action": {},
        "response": {},
        "error": None
    })
    
    logger.info("Agent run completed")
    
    return result["response"]

def get_incidents(
    resolved: Optional[bool] = None,
    incident_type: Optional[str] = None,
    pod_name: Optional[str] = None,
    namespace: Optional[str] = None,
    since: Optional[int] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Get incidents with optional filtering"""
    incidents = incident_store.get_incidents(
        resolved=resolved,
        incident_type=incident_type,
        pod_name=pod_name,
        namespace=namespace,
        since=since,
        limit=limit
    )
    
    return [asdict(incident) for incident in incidents]

def get_restart_counts() -> Dict[str, Dict[str, int]]:
    """Get all restart counts"""
    return incident_store.get_all_restart_counts()
