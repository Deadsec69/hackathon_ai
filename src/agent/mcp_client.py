import os
import json
import time
import logging
import requests
from typing import Dict, List, Any, Optional, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logger = logging.getLogger("agent.mcp_client")

class MCPClient:
    """Client for interacting with MCP servers"""
    
    def __init__(self, server_url: str, max_retries: int = 3, retry_backoff: float = 0.5):
        """Initialize MCP client with server URL"""
        self.server_url = server_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.session = self._create_session()
        self.schema = self._get_schema()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_schema(self) -> Dict[str, Any]:
        """Get the MCP schema from the server"""
        try:
            logger.info(f"Getting schema from {self.server_url}")
            response = self.session.get(f"{self.server_url}/mcp/schema")
            response.raise_for_status()
            schema = response.json()
            logger.info(f"Got schema with {len(schema.get('tools', []))} tools and {len(schema.get('resources', []))} resources")
            return schema
        except requests.RequestException as e:
            logger.error(f"Error getting MCP schema: {e}", exc_info=True)
            return {"tools": [], "resources": []}
    
    def use_tool(self, tool_name: str, arguments: Dict[str, Any], retry_count: int = 0) -> Dict[str, Any]:
        """Use an MCP tool with retry logic"""
        # Check if tool exists in schema
        tool_exists = False
        for tool in self.schema.get("tools", []):
            if tool.get("name") == tool_name:
                tool_exists = True
                break
        
        if not tool_exists:
            logger.error(f"Tool '{tool_name}' not found in MCP schema")
            raise ValueError(f"Tool '{tool_name}' not found in MCP schema")
        
        # Call the tool
        try:
            logger.info(f"Using tool '{tool_name}' with arguments: {json.dumps(arguments)}")
            response = self.session.post(
                f"{self.server_url}/mcp/tools/{tool_name}",
                json=arguments
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Tool '{tool_name}' executed successfully")
            return result
        except requests.RequestException as e:
            logger.error(f"Error using MCP tool '{tool_name}': {e}", exc_info=True)
            
            # Check if we should retry
            if retry_count < self.max_retries and self._should_retry(e):
                retry_count += 1
                wait_time = self.retry_backoff * (2 ** (retry_count - 1))
                logger.info(f"Retrying tool '{tool_name}' in {wait_time:.2f} seconds (attempt {retry_count}/{self.max_retries})")
                time.sleep(wait_time)
                return self.use_tool(tool_name, arguments, retry_count)
            
            # Return error response
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    return {"error": error_data.get("detail", str(e))}
                except:
                    return {"error": str(e)}
            return {"error": str(e)}
    
    def _should_retry(self, exception: requests.RequestException) -> bool:
        """Determine if we should retry based on the exception"""
        if hasattr(exception, "response") and exception.response is not None:
            status_code = exception.response.status_code
            # Retry on server errors and rate limiting
            return status_code >= 500 or status_code == 429
        # Retry on connection errors
        return isinstance(exception, (requests.ConnectionError, requests.Timeout))
    
    def access_resource(self, resource_uri: str, retry_count: int = 0) -> Dict[str, Any]:
        """Access an MCP resource with retry logic"""
        # Check if resource exists in schema
        resource_exists = False
        for resource in self.schema.get("resources", []):
            if resource.get("uri") == resource_uri:
                resource_exists = True
                break
        
        if not resource_exists:
            logger.error(f"Resource '{resource_uri}' not found in MCP schema")
            raise ValueError(f"Resource '{resource_uri}' not found in MCP schema")
        
        # Access the resource
        try:
            logger.info(f"Accessing resource '{resource_uri}'")
            response = self.session.get(
                f"{self.server_url}/mcp/resources/{resource_uri}"
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Resource '{resource_uri}' accessed successfully")
            return result
        except requests.RequestException as e:
            logger.error(f"Error accessing MCP resource '{resource_uri}': {e}", exc_info=True)
            
            # Check if we should retry
            if retry_count < self.max_retries and self._should_retry(e):
                retry_count += 1
                wait_time = self.retry_backoff * (2 ** (retry_count - 1))
                logger.info(f"Retrying resource '{resource_uri}' in {wait_time:.2f} seconds (attempt {retry_count}/{self.max_retries})")
                time.sleep(wait_time)
                return self.access_resource(resource_uri, retry_count)
            
            # Return error response
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    return {"error": error_data.get("detail", str(e))}
                except:
                    return {"error": str(e)}
            return {"error": str(e)}

class MCPClientManager:
    """Manager for multiple MCP clients"""
    
    def __init__(self):
        """Initialize MCP client manager"""
        self.clients = {}
        
        # Initialize clients from environment variables
        kubernetes_mcp_url = os.environ.get("KUBERNETES_MCP_URL")
        prometheus_mcp_url = os.environ.get("PROMETHEUS_MCP_URL")
        grafana_mcp_url = os.environ.get("GRAFANA_MCP_URL")
        github_mcp_url = os.environ.get("GITHUB_MCP_URL")
        
        if kubernetes_mcp_url:
            logger.info(f"Initializing Kubernetes MCP client with URL: {kubernetes_mcp_url}")
            self.clients["kubernetes"] = MCPClient(kubernetes_mcp_url)
        if prometheus_mcp_url:
            logger.info(f"Initializing Prometheus MCP client with URL: {prometheus_mcp_url}")
            self.clients["prometheus"] = MCPClient(prometheus_mcp_url)
        if grafana_mcp_url:
            logger.info(f"Initializing Grafana MCP client with URL: {grafana_mcp_url}")
            self.clients["grafana"] = MCPClient(grafana_mcp_url)
        if github_mcp_url:
            logger.info(f"Initializing GitHub MCP client with URL: {github_mcp_url}")
            self.clients["github"] = MCPClient(github_mcp_url)
    
    def get_client(self, server_name: str) -> MCPClient:
        """Get an MCP client by server name"""
        if server_name not in self.clients:
            logger.error(f"MCP client for server '{server_name}' not found")
            raise ValueError(f"MCP client for server '{server_name}' not found")
        return self.clients[server_name]
    
    def add_client(self, server_name: str, server_url: str) -> MCPClient:
        """Add a new MCP client"""
        logger.info(f"Adding new MCP client for server '{server_name}' with URL: {server_url}")
        client = MCPClient(server_url)
        self.clients[server_name] = client
        return client
    
    def use_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Use an MCP tool on a specific server"""
        try:
            client = self.get_client(server_name)
            return client.use_tool(tool_name, arguments)
        except Exception as e:
            logger.error(f"Error using tool '{tool_name}' on server '{server_name}': {e}", exc_info=True)
            return {"error": str(e)}
    
    def access_resource(self, server_name: str, resource_uri: str) -> Dict[str, Any]:
        """Access an MCP resource on a specific server"""
        try:
            client = self.get_client(server_name)
            return client.access_resource(resource_uri)
        except Exception as e:
            logger.error(f"Error accessing resource '{resource_uri}' on server '{server_name}': {e}", exc_info=True)
            return {"error": str(e)}

# Create a global instance of the MCP client manager
mcp_manager = MCPClientManager()
