"""
Tool Registry - Dynamic Tool Registration and Execution

This module provides a registry for external tools/APIs that services
can invoke. Tools are registered with schemas and executed with
automatic validation, retries, and metrics.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class ToolStatus(Enum):
    """Tool availability status"""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ToolSchema:
    """Schema definition for a tool"""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)
    returns: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Tool:
    """Represents an external tool/API"""

    name: str
    description: str
    endpoint: str
    method: str = "POST"
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    schema: Optional[ToolSchema] = None
    health_check_path: Optional[str] = "/health"
    api_key_header: Optional[str] = None
    api_key: Optional[str] = None

    # Runtime state
    status: ToolStatus = ToolStatus.UNKNOWN
    last_check: Optional[datetime] = None

    # Metrics
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0


@dataclass
class ToolResult:
    """Result from a tool execution"""

    success: bool
    tool_name: str
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Registry for managing and executing external tools.

    Provides:
    - Dynamic tool registration
    - Parameter validation
    - Automatic retries
    - Health checking
    - Metrics collection
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Tool storage
        self._tools: Dict[str, Tool] = {}
        self._custom_handlers: Dict[str, Callable] = {}

        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None

        # Configuration
        retry_config = self.config.get("resilience", {}).get("retry", {})
        self._max_retries = retry_config.get("maxAttempts", 3)
        self._retry_delay = retry_config.get("initialDelay", 1)
        self._retry_multiplier = retry_config.get("multiplier", 2.0)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close registry and cleanup"""
        if self._session:
            await self._session.close()
            self._session = None

    # ==================== Registration ====================

    def register(
        self,
        name: str,
        description: str,
        endpoint: str,
        method: str = "POST",
        schema: ToolSchema = None,
        **kwargs,
    ) -> Tool:
        """
        Register a new tool.

        Args:
            name: Unique tool name
            description: Tool description
            endpoint: API endpoint URL
            method: HTTP method
            schema: Optional parameter schema
            **kwargs: Additional tool configuration

        Returns:
            Registered Tool object
        """
        tool = Tool(
            name=name,
            description=description,
            endpoint=endpoint,
            method=method,
            schema=schema,
            **kwargs,
        )

        self._tools[name] = tool
        self.logger.info(f"Registered tool: {name}")

        return tool

    def register_handler(
        self, name: str, description: str, handler: Callable, schema: ToolSchema = None
    ) -> Tool:
        """
        Register a custom handler function as a tool.

        Args:
            name: Unique tool name
            description: Tool description
            handler: Async callable that handles the tool execution
            schema: Optional parameter schema

        Returns:
            Registered Tool object
        """
        tool = Tool(
            name=name,
            description=description,
            endpoint="local://handler",
            schema=schema,
        )

        self._tools[name] = tool
        self._custom_handlers[name] = handler
        self.logger.info(f"Registered handler tool: {name}")

        return tool

    def unregister(self, name: str):
        """Unregister a tool"""
        if name in self._tools:
            del self._tools[name]
            if name in self._custom_handlers:
                del self._custom_handlers[name]
            self.logger.info(f"Unregistered tool: {name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "status": tool.status.value,
                "schema": tool.schema.__dict__ if tool.schema else None,
            }
            for tool in self._tools.values()
        ]

    # ==================== Execution ====================

    async def execute(
        self, tool_name: str, params: Dict[str, Any] = None, **kwargs
    ) -> ToolResult:
        """
        Execute a tool with the given parameters.

        Args:
            tool_name: Name of tool to execute
            params: Tool parameters
            **kwargs: Additional execution options

        Returns:
            ToolResult with success/failure and data
        """
        if tool_name not in self._tools:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' not found",
            )

        tool = self._tools[tool_name]
        params = params or {}

        # Validate parameters if schema exists
        if tool.schema:
            validation_error = self._validate_params(tool.schema, params)
            if validation_error:
                return ToolResult(
                    success=False, tool_name=tool_name, error=validation_error
                )

        # Execute with retries
        start_time = time.time()
        tool.total_calls += 1

        for attempt in range(self._max_retries):
            try:
                if tool_name in self._custom_handlers:
                    result = await self._execute_handler(tool_name, params)
                else:
                    result = await self._execute_http(tool, params, **kwargs)

                latency_ms = (time.time() - start_time) * 1000
                tool.successful_calls += 1
                tool.total_latency_ms += latency_ms
                tool.status = ToolStatus.AVAILABLE

                return ToolResult(
                    success=True,
                    tool_name=tool_name,
                    data=result,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (self._retry_multiplier**attempt)
                    self.logger.warning(
                        f"Tool {tool_name} failed (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    latency_ms = (time.time() - start_time) * 1000
                    tool.failed_calls += 1
                    tool.status = ToolStatus.DEGRADED

                    return ToolResult(
                        success=False,
                        tool_name=tool_name,
                        error=str(e),
                        latency_ms=latency_ms,
                    )

        # Should not reach here, but just in case
        return ToolResult(
            success=False, tool_name=tool_name, error="Max retries exceeded"
        )

    async def _execute_handler(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a custom handler tool"""
        handler = self._custom_handlers[tool_name]
        result = handler(params)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    async def _execute_http(self, tool: Tool, params: Dict[str, Any], **kwargs) -> Any:
        """Execute an HTTP-based tool"""
        session = await self._get_session()

        headers = dict(tool.headers)
        if tool.api_key and tool.api_key_header:
            headers[tool.api_key_header] = tool.api_key

        timeout = aiohttp.ClientTimeout(total=kwargs.get("timeout", tool.timeout))

        async with session.request(
            tool.method, tool.endpoint, json=params, headers=headers, timeout=timeout
        ) as resp:
            if resp.status >= 400:
                error = await resp.text()
                raise Exception(f"HTTP {resp.status}: {error}")

            try:
                return await resp.json()
            except:
                return await resp.text()

    def _validate_params(
        self, schema: ToolSchema, params: Dict[str, Any]
    ) -> Optional[str]:
        """Validate parameters against schema"""
        # Check required parameters
        for required in schema.required_params:
            if required not in params:
                return f"Missing required parameter: {required}"

        # Type checking could be added here
        return None

    # ==================== Health Checking ====================

    async def check_health(self, tool_name: str = None) -> Dict[str, Any]:
        """
        Check health of tools.

        Args:
            tool_name: Specific tool to check, or None for all

        Returns:
            Health status dictionary
        """
        if tool_name:
            tools = [self._tools.get(tool_name)]
            if not tools[0]:
                return {"error": f"Tool '{tool_name}' not found"}
        else:
            tools = list(self._tools.values())

        results = {}

        for tool in tools:
            if not tool:
                continue

            if tool.name in self._custom_handlers:
                # Custom handlers are always available
                tool.status = ToolStatus.AVAILABLE
                results[tool.name] = {"status": "available", "type": "handler"}
                continue

            if not tool.health_check_path:
                results[tool.name] = {"status": "unknown", "reason": "no health check"}
                continue

            try:
                session = await self._get_session()
                # Extract base URL for health check
                from urllib.parse import urlparse, urlunparse

                parsed = urlparse(tool.endpoint)
                health_url = urlunparse(
                    (parsed.scheme, parsed.netloc, tool.health_check_path, "", "", "")
                )

                async with session.get(
                    health_url, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        tool.status = ToolStatus.AVAILABLE
                        results[tool.name] = {"status": "available"}
                    else:
                        tool.status = ToolStatus.DEGRADED
                        results[tool.name] = {"status": "degraded", "code": resp.status}

            except Exception as e:
                tool.status = ToolStatus.UNAVAILABLE
                results[tool.name] = {"status": "unavailable", "error": str(e)}

            tool.last_check = datetime.now()

        return results

    # ==================== Metrics ====================

    def get_metrics(self, tool_name: str = None) -> Dict[str, Any]:
        """Get tool execution metrics"""
        if tool_name:
            tool = self._tools.get(tool_name)
            if not tool:
                return {}
            return self._tool_metrics(tool)

        return {name: self._tool_metrics(tool) for name, tool in self._tools.items()}

    def _tool_metrics(self, tool: Tool) -> Dict[str, Any]:
        """Get metrics for a single tool"""
        return {
            "name": tool.name,
            "status": tool.status.value,
            "total_calls": tool.total_calls,
            "successful_calls": tool.successful_calls,
            "failed_calls": tool.failed_calls,
            "success_rate": (
                tool.successful_calls / tool.total_calls if tool.total_calls > 0 else 0
            ),
            "avg_latency_ms": (
                tool.total_latency_ms / tool.successful_calls
                if tool.successful_calls > 0
                else 0
            ),
            "last_check": tool.last_check.isoformat() if tool.last_check else None,
        }
