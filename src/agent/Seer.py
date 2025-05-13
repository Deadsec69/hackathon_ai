import json
import logging
import sys
import time

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from mcp_client import mcp_manager
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

from agent import AgentState, process_metric_result, CPU_THRESHOLD, MEMORY_THRESHOLD,calculate_severity

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

        logger.info(
            f"Checking memory metric: {json.dumps(memory_metric)}, value: {memory_value} bytes ({memory_percent:.2f}%)")

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