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
import openai  # Used for both OpenAI and Azure OpenAI
# import anthropic
# from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI, AzureChatOpenAI
# from litellm import completion
# from litellm.llms.langchain import LangChainChat
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

from mcp_client import mcp_manager
from incident_store import incident_store, Incident

# Import agent modules
from sub_agents.logger import (
    logger, seer_logger, medic_logger, forge_logger, 
    smith_logger, vision_logger, herald_logger, oracle_logger
)
from sub_agents.seer import monitor_metrics, analyze_metrics, process_metric_result, calculate_severity
from sub_agents.oracle import decide_action, route_decide
from sub_agents.medic import remediate_issue
from sub_agents.smith import analyze_code
from sub_agents.herald import format_response
from sub_agents.forge import get_incidents, get_restart_counts
from sub_agents.vision import create_dashboard_annotation, update_dashboard_panel

# Load environment variables
load_dotenv()

# Initialize Anthropic client (commented out)
# anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
# if not anthropic_api_key:
#     raise ValueError("ANTHROPIC_API_KEY environment variable not set")

# Initialize OpenAI client (commented out)
# openai_api_key = os.environ.get("OPENAI_API_KEY")
# if not openai_api_key:
#     raise ValueError("OPENAI_API_KEY environment variable not set")

# Initialize Azure OpenAI client
azure_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
if not azure_api_key:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")

azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
if not azure_endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")

azure_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or "gpt-4o-modelia-rag"
azure_api_version = os.environ.get("AZURE_OPENAI_API_VERSION") or "2024-05-01-preview"

# Configure LiteLLM with Azure OpenAI
# No need to configure global settings as LiteLLM handles this per request

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
# Claude setup (commented out)
# llm = ChatAnthropic(model="claude-3-sonnet-20240229", temperature=0)

# OpenAI setup (commented out)
# llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Azure OpenAI setup
llm = AzureChatOpenAI(
    azure_deployment=azure_deployment,
    openai_api_version=azure_api_version,
    openai_api_key=azure_api_key,
    azure_endpoint=azure_endpoint,
    temperature=0
)

# LiteLLM setup with Anthropic only (commented out)
# llm = LangChainChat(
#     model="anthropic/claude-3-sonnet-20240229",
#     api_key=anthropic_api_key,
#     temperature=0
# )

# Claude setup (commented out)
# llm = ChatAnthropic(model="claude-3-sonnet-20240229", temperature=0)

# Node functions
def monitor_metrics(state: AgentState) -> AgentState:
    """Seer Agent: Monitor metrics from Prometheus and API status endpoint"""
    try:
        seer_logger.info("Seer is starting to monitor metrics")
        
        # Query Prometheus for CPU metrics
        seer_logger.info("Seer is querying Prometheus for CPU metrics")
        cpu_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_cpu_usage_percent"
        })
        seer_logger.info(f"Seer received CPU metrics: {json.dumps(cpu_result)}")
        
        # Query Prometheus for memory metrics (we'll override this with the API status endpoint)
        seer_logger.info("Seer is querying Prometheus for memory metrics")
        memory_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_memory_usage_bytes"
        })
        seer_logger.info(f"Seer received memory metrics from Prometheus: {json.dumps(memory_result)}")
        
        # Query API status endpoint for more accurate memory metrics
        seer_logger.info("Seer is querying API status endpoint for accurate memory metrics")
        try:
            import requests
            status_response = requests.get("http://api:8000/status", timeout=5)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            # Create a memory metric result that matches the format from Prometheus
            api_memory_value = status_data.get("memory_usage", 0)
            memory_spike_active = status_data.get("memory_spike_active", False)
            
            seer_logger.info(f"Seer received API status endpoint memory: {api_memory_value} bytes, memory_spike_active: {memory_spike_active}")
            
            # Override the memory result with the API status data
            if api_memory_value > 0:
                # Create a memory metric that matches the format from Prometheus
                # Use the same instance name "test-app:8001" to ensure consistent tracking
                memory_metric = {
                    "metric": {"__name__": "app_memory_usage_bytes", "instance": "test-app:8001", "job": "test-app"},
                    "value": api_memory_value,
                    "timestamp": int(time.time())
                }
                
                # Replace the memory metrics with our custom one
                memory_result = {"result": [{"metric": memory_metric["metric"], "value": [int(time.time()), str(api_memory_value)]}]}
                seer_logger.info(f"Seer using memory metrics from API status endpoint: {json.dumps(memory_result)}")
        except Exception as e:
            seer_logger.error(f"Seer encountered error querying API status endpoint: {str(e)}")
            seer_logger.info("Seer falling back to Prometheus memory metrics")
        
        # Query Prometheus for CPU spike counter
        seer_logger.info("Seer is querying Prometheus for CPU spike counter")
        cpu_spike_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_cpu_spike_total"
        })
        seer_logger.info(f"Seer received CPU spike counter: {json.dumps(cpu_spike_result)}")
        
        # Query Prometheus for memory spike counter
        seer_logger.info("Seer is querying Prometheus for memory spike counter")
        memory_spike_result = mcp_manager.use_tool("prometheus", "query", {
            "query": "app_memory_spike_total"
        })
        seer_logger.info(f"Seer received memory spike counter: {json.dumps(memory_spike_result)}")
        
        # Get Kubernetes pods
        seer_logger.info("Seer is getting Kubernetes pods")
        pods_result = mcp_manager.use_tool("kubernetes", "list_pods", {
            "namespace": "default"
        })
        seer_logger.info(f"Seer received pods: {json.dumps(pods_result)}")
        
        # Process metrics
        metrics = {
            "cpu": process_metric_result(cpu_result),
            "memory": process_metric_result(memory_result),
            "cpu_spike": process_metric_result(cpu_spike_result),
            "memory_spike": process_metric_result(memory_spike_result),
            "pods": pods_result.get("pods", []),
            "timestamp": int(time.time())
        }
        
        seer_logger.info(f"Seer processed metrics: {json.dumps(metrics)}")
        herald_logger.info(f"Herald: Seer has completed monitoring and collected all metrics")
        
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
    """Seer Agent: Analyze metrics to detect issues"""
    if state.get("error"):
        seer_logger.warning(f"Seer is skipping metrics analysis due to error: {state.get('error')}")
        return state
    
    seer_logger.info("Seer is starting metrics analysis")
    
    metrics = state.get("metrics", {})
    cpu_metrics = metrics.get("cpu", [])
    memory_metrics = metrics.get("memory", [])
    pods = metrics.get("pods", [])
    
    seer_logger.info(f"Seer analyzing CPU metrics: {json.dumps(cpu_metrics)}")
    seer_logger.info(f"Seer analyzing memory metrics: {json.dumps(memory_metrics)}")
    seer_logger.info(f"Seer analyzing pods: {json.dumps(pods)}")
    
    issues = []
    
    # Check CPU usage
    for cpu_metric in cpu_metrics:
        seer_logger.info(f"Seer checking CPU metric: {json.dumps(cpu_metric)}")
        if cpu_metric["value"] > CPU_THRESHOLD:
            seer_logger.info(f"Seer detected CPU usage {cpu_metric['value']} exceeds threshold {CPU_THRESHOLD}")
            pod_name = cpu_metric["metric"].get("instance", "unknown")
            namespace = "default"
            
            # Find the pod in the list
            for pod in pods:
                if pod["name"] in pod_name:
                    pod_name = pod["name"]
                    namespace = pod["namespace"]
                    break
            
            seer_logger.info(f"Seer identified pod {pod_name} in namespace {namespace}")
            
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
        
        seer_logger.info(f"Seer checking memory metric: {json.dumps(memory_metric)}, value: {memory_value} bytes ({memory_percent:.2f}%)")
        
        if memory_value > MEMORY_THRESHOLD:
            seer_logger.info(f"Seer detected memory usage {memory_value} bytes exceeds threshold {MEMORY_THRESHOLD} bytes")
            pod_name = memory_metric["metric"].get("instance", "unknown")
            namespace = "default"
            
            # Find the pod in the list
            for pod in pods:
                if pod["name"] in pod_name:
                    pod_name = pod["name"]
                    namespace = pod["namespace"]
                    break
            
            seer_logger.info(f"Seer identified pod {pod_name} in namespace {namespace}")
            
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
    
    seer_logger.info(f"Seer completed analysis: {json.dumps(analysis)}")
    
    if analysis.get("issues", []):
        herald_logger.info(f"Herald: Seer has detected {len(analysis.get('issues', []))} issues requiring attention")
    else:
        herald_logger.info(f"Herald: Seer reports all systems operating within normal parameters")
    
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
    """Oracle Agent: Decide what action to take based on analysis"""
    if state.get("error"):
        oracle_logger.warning(f"Oracle is skipping action decision due to error: {state.get('error')}")
        return state
    
    oracle_logger.info("Oracle is deciding action based on analysis")
    
    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])
    
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
    
    oracle_logger.info(f"Oracle identified most severe issue: {json.dumps(issue)}")
    
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

def remediate_issue(state: AgentState) -> AgentState:
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
        logger.error(f"Error remediating issue: {str(e)}", exc_info=True)
        return {
            **state,
            "error": f"Error remediating issue: {str(e)}"
        }

def analyze_code(state: AgentState) -> AgentState:
    """Smith Agent: Analyze code and logs to find the root cause and create a PR"""
    if state.get("error"):
        smith_logger.warning(f"Smith is skipping code analysis due to error: {state.get('error')}")
        return state
    
    smith_logger.info("Smith is starting code analysis")
    
    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])
    
    if not issues:
        smith_logger.warning("Smith found no issues to analyze")
        return state
    
    # Sort issues by severity
    issues.sort(key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x["severity"], 0), reverse=True)
    
    # Get the most severe issue
    issue = issues[0]
    pod_name = issue["pod_name"]
    namespace = issue["namespace"]
    issue_type = issue["type"]
    
    smith_logger.info(f"Smith is analyzing code for issue: {json.dumps(issue)}")
    
    try:
        # Get pod logs
        smith_logger.info(f"Smith is retrieving logs for pod {pod_name} in namespace {namespace}")
        logs_result = mcp_manager.use_tool("kubernetes", "get_logs", {
            "namespace": namespace,
            "pod_name": pod_name,
            "tail_lines": 1000
        })
        
        logs = logs_result.get("logs", "")
        smith_logger.info(f"Smith retrieved {len(logs)} bytes of logs")
        
        # Get application code using the Kubernetes MCP server
        smith_logger.info("Smith is retrieving application code using Kubernetes MCP server")
        app_code = ""
        try:
            # Use the Kubernetes MCP server to get the application code
            app_code_result = mcp_manager.use_tool("kubernetes", "get_app_code", {
                "namespace": namespace,
                "pod_name": pod_name
            })
            
            app_code = app_code_result.get("code", "")
            smith_logger.info(f"Smith retrieved {len(app_code)} bytes of application code")
        except Exception as e:
            smith_logger.error(f"Smith encountered error getting application code: {str(e)}")
            app_code = "# Error: Could not retrieve application code"
        # logger.info(f"------------APP_CODE-------------: {app_code}")
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
        
        smith_logger.info("Smith is generating code fix with LLM")
        code_fix_chain = code_fix_prompt | llm | StrOutputParser()
        
        code_fix_result = code_fix_chain.invoke({
            "pod_name": pod_name,
            "namespace": namespace,
            "issue_type": issue_type,
            "logs": logs,
            "app_code": app_code
        })
        
        smith_logger.info(f"Smith generated code fix: {len(code_fix_result)} bytes")
        code_fix_result = code_fix_result.replace("```","").replace("python","").replace("json","")
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
           - "fix_file": The file that needs to be modified (e.g., "main.py")
           - "pr_title": A title for the pull request
           - "pr_body": A detailed description for the pull request
        
        Respond with only the JSON object, no additional text.
        """)
        
        smith_logger.info("Smith is analyzing and formatting response with LLM")
        analysis_chain = analysis_prompt | llm | StrOutputParser()
        
        analysis_result = analysis_chain.invoke({
            "pod_name": pod_name,
            "namespace": namespace,
            "issue_type": issue_type,
            "logs": logs,
            "app_code": app_code,
            "code_fix": code_fix_result
        })
        analysis_result = analysis_result.replace("json","").replace("```","")
        smith_logger.info(f"Smith completed analysis: {len(analysis_result)} bytes")
        # Parse the analysis result
        try:
            analysis_data = json.loads(analysis_result)
            analysis_data['fix_code'] = code_fix_result
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
        forge_logger.info(f"Forge is creating analysis ticket for {issue_type.upper()} issue in pod {pod_name}")
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
        
        forge_logger.info(f"Forge is creating GitHub issue: {issue_title}")
        github_issue = mcp_manager.use_tool("github", "create_issue", {
            "title": issue_title,
            "body": issue_body,
            "labels": [issue_type, "analysis", "needs-review"]
        })
        forge_logger.info(f"Forge created GitHub issue #{github_issue.get('number')}: {github_issue.get('html_url')}")
        herald_logger.info(f"Herald: Forge has created analysis issue #{github_issue.get('number')} for {issue_type} in {pod_name}")
        
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
        smith_logger.info(f"Smith is creating branch {branch_name}")
        try:
            branch_result = mcp_manager.use_tool("github", "create_branch", {
                "branch": branch_name,
                "base": "develop"  # Use develop as the base branch
            })
            smith_logger.info(f"Smith created branch: {json.dumps(branch_result)}")
            
            # Create the file in the new branch
            smith_logger.info(f"Smith is creating file {file_path} in branch {branch_name}")
            file_result = mcp_manager.use_tool("github", "create_file", {
                "path": file_path,
                "content": file_content,
                "message": commit_message,
                "branch": branch_name
            })
            smith_logger.info(f"Smith created file: {json.dumps(file_result)}")
        except Exception as e:
            smith_logger.error(f"Smith encountered error creating branch or file: {str(e)}")
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
        forge_logger.info(f"Forge is creating incident record with ID {incident_id}")
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
        forge_logger.info(f"Forge created incident record {incident_id}")
        
        # Create Grafana annotation
        dashboard_id = 1  # Assuming dashboard ID 1 for the test application dashboard
        vision_logger.info(f"Vision is updating dashboard {dashboard_id} with analysis for {pod_name}")
        annotation_result = mcp_manager.use_tool("grafana", "create_annotation", {
            "dashboard_id": dashboard_id,
            "time": int(time.time() * 1000),  # Convert to milliseconds
            "text": f"Code analysis for pod {pod_name} due to persistent high {issue_type} usage",
            "tags": [issue_type, "analysis", "pr-created"]
        })
        vision_logger.info(f"Vision created dashboard annotation: {json.dumps(annotation_result)}")
        herald_logger.info(f"Herald: Vision has updated the monitoring dashboard with code analysis for {pod_name}")
        
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
        
        smith_logger.info(f"Smith completed code analysis successfully")
        herald_logger.info(f"Herald: Smith has analyzed issue in {pod_name}, created PR #{pr_result.get('number')} with fix")
        
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

# Define the routing function for conditional edges
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
    """Oracle Agent: Run the agent workflow"""
    if input_data is None:
        input_data = {}
    
    oracle_logger.info("Oracle is starting agent workflow")
    herald_logger.info("Herald: Agent workflow initiated by Oracle")
    
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
    
    oracle_logger.info("Oracle has completed agent workflow")
    herald_logger.info("Herald: Agent workflow completed successfully")
    
    return result["response"]

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
