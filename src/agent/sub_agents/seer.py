import json
import time
from typing import Dict, List, Any, Optional, Union, TypedDict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_client import mcp_manager
from sub_agents.logger import seer_logger, herald_logger

def monitor_metrics(state: Dict[str, Any]) -> Dict[str, Any]:
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
        seer_logger.error(f"Error monitoring metrics: {str(e)}")
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

def analyze_metrics(state: Dict[str, Any]) -> Dict[str, Any]:
    """Seer Agent: Analyze metrics to detect issues"""
    if state.get("error"):
        seer_logger.warning(f"Seer is skipping metrics analysis due to error: {state.get('error')}")
        return state
    
    seer_logger.info("Seer is starting metrics analysis")
    
    metrics = state.get("metrics", {})
    cpu_metrics = metrics.get("cpu", [])
    memory_metrics = metrics.get("memory", [])
    pods = metrics.get("pods", [])
    
    # Get thresholds from environment or use defaults
    CPU_THRESHOLD = 10  # CPU usage percentage threshold (lowered to 10% for testing)
    MEMORY_THRESHOLD = 600000000  # Memory threshold in bytes (500 MB)
    
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
