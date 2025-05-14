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
from sub_agents.logger import smith_logger, forge_logger, vision_logger, herald_logger

def analyze_code(state: Dict[str, Any]) -> Dict[str, Any]:
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
        
        # Import LLM components
        from langchain.prompts import ChatPromptTemplate
        from langchain.schema import StrOutputParser
        
        # Get LLM from agent.py
        import agent
        llm = agent.llm
        
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
            smith_logger.info("Successfully parsed LLM analysis result")
        except json.JSONDecodeError:
            smith_logger.error("Failed to parse LLM analysis result as JSON")
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
        
        smith_logger.info(f"Smith is creating pull request: {pr_title}")
        pr_result = mcp_manager.use_tool("github", "create_pull_request", {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": "develop"  # Use develop as the base branch
        })
        smith_logger.info(f"Smith created pull request: {json.dumps(pr_result)}")
        
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
        smith_logger.error(f"Error analyzing code: {str(e)}")
        return {
            **state,
            "error": f"Error analyzing code: {str(e)}"
        }
