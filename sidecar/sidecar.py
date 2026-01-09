"""
Sidecar for AOL Service - Protocol Translation, Tool Execution, and mTLS Proxying

This sidecar provides:
- Protocol translation (HTTP <-> gRPC, etc.)
- Tool/integration execution with circuit breakers
- Metrics collection for all interactions
- mTLS proxy for Consul Connect integration
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import aiohttp
import json

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for fault isolation"""

    name: str
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: int = 60  # seconds

    # State tracking
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None

    def record_success(self):
        """Record a successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"Circuit {self.name} CLOSED")
        else:
            self.failure_count = 0

    def record_failure(self):
        """Record a failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.success_count = 0

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit {self.name} OPEN after {self.failure_count} failures"
            )

    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).seconds
                if elapsed >= self.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit {self.name} HALF_OPEN")
                    return True
            return False

        # HALF_OPEN - allow limited requests
        return True


@dataclass
class ToolConfig:
    """Configuration for an external tool/integration"""

    name: str
    endpoint: str
    timeout: int = 30
    api_key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    health_check_interval: int = 30


@dataclass
class ToolMetrics:
    """Metrics for tool execution"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0
    last_call_time: Optional[datetime] = None
    last_error: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls


class ToolExecutor:
    """
    Executes external tool/API calls with circuit breakers and metrics.

    This provides a unified interface for invoking external integrations
    while handling failures gracefully and collecting observability data.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Tool registry
        self._tools: Dict[str, ToolConfig] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._metrics: Dict[str, ToolMetrics] = {}

        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None

        # Health check tasks
        self._health_tasks: Dict[str, asyncio.Task] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close executor and cleanup"""
        # Cancel health checks
        for task in self._health_tasks.values():
            task.cancel()

        # Close session
        if self._session:
            await self._session.close()
            self._session = None

    def register_tool(self, tool_config: ToolConfig):
        """Register a tool for execution"""
        self._tools[tool_config.name] = tool_config
        self._circuit_breakers[tool_config.name] = CircuitBreaker(
            name=tool_config.name,
            failure_threshold=self.config.get("resilience", {})
            .get("circuitBreaker", {})
            .get("failureThreshold", 5),
            timeout=self.config.get("resilience", {})
            .get("circuitBreaker", {})
            .get("timeout", 60),
        )
        self._metrics[tool_config.name] = ToolMetrics()

        self.logger.info(f"Registered tool: {tool_config.name}")

        # Start health check if enabled
        if tool_config.health_check_enabled:
            self._health_tasks[tool_config.name] = asyncio.create_task(
                self._health_check_loop(tool_config)
            )

    async def _health_check_loop(self, tool: ToolConfig):
        """Background health check for a tool"""
        while True:
            try:
                await asyncio.sleep(tool.health_check_interval)
                await self._check_tool_health(tool)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.debug(f"Health check error for {tool.name}: {e}")

    async def _check_tool_health(self, tool: ToolConfig) -> bool:
        """Check tool health"""
        try:
            session = await self._get_session()
            url = f"{tool.endpoint}{tool.health_check_path}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def execute(
        self,
        tool_name: str,
        method: str = "POST",
        path: str = "",
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool call with circuit breaker protection.

        Args:
            tool_name: Name of registered tool
            method: HTTP method
            path: API path (appended to tool endpoint)
            payload: Request payload
            headers: Additional headers
            timeout: Override timeout

        Returns:
            Response data or error information
        """
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not registered")

        tool = self._tools[tool_name]
        circuit = self._circuit_breakers[tool_name]
        metrics = self._metrics[tool_name]

        # Check circuit breaker
        if not circuit.can_execute():
            metrics.failed_calls += 1
            metrics.total_calls += 1
            return {
                "error": "Circuit breaker open",
                "tool": tool_name,
                "success": False,
            }

        # Prepare request
        url = f"{tool.endpoint}{path}"
        request_headers = {**tool.headers}
        if tool.api_key:
            request_headers["Authorization"] = f"Bearer {tool.api_key}"
        if headers:
            request_headers.update(headers)

        request_timeout = timeout or tool.timeout

        # Execute with metrics
        start_time = time.time()
        metrics.total_calls += 1
        metrics.last_call_time = datetime.now()

        try:
            session = await self._get_session()

            async with session.request(
                method,
                url,
                json=payload,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=request_timeout),
            ) as resp:
                latency_ms = (time.time() - start_time) * 1000

                if resp.status < 400:
                    metrics.successful_calls += 1
                    metrics.total_latency_ms += latency_ms
                    circuit.record_success()

                    try:
                        data = await resp.json()
                    except Exception:
                        data = await resp.text()

                    return {
                        "success": True,
                        "data": data,
                        "status": resp.status,
                        "latency_ms": latency_ms,
                    }
                else:
                    metrics.failed_calls += 1
                    metrics.last_error = f"HTTP {resp.status}"
                    circuit.record_failure()

                    return {
                        "success": False,
                        "error": f"HTTP {resp.status}",
                        "status": resp.status,
                        "latency_ms": latency_ms,
                    }

        except asyncio.TimeoutError:
            metrics.failed_calls += 1
            metrics.last_error = "Timeout"
            circuit.record_failure()
            return {"success": False, "error": "Timeout", "tool": tool_name}
        except Exception as e:
            metrics.failed_calls += 1
            metrics.last_error = str(e)
            circuit.record_failure()
            return {"success": False, "error": str(e), "tool": tool_name}

    def get_metrics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get tool execution metrics"""
        if tool_name:
            if tool_name not in self._metrics:
                return {}
            m = self._metrics[tool_name]
            return {
                "tool": tool_name,
                "total_calls": m.total_calls,
                "successful_calls": m.successful_calls,
                "failed_calls": m.failed_calls,
                "success_rate": m.success_rate,
                "avg_latency_ms": m.avg_latency_ms,
                "circuit_state": self._circuit_breakers[tool_name].state.value,
            }

        # Return all metrics
        return {name: self.get_metrics(name) for name in self._metrics}


class ProtocolAdapter:
    """
    Protocol translation adapter.

    Translates between different protocols (HTTP, gRPC, etc.)
    for services that need to communicate across protocol boundaries.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._adapters: Dict[str, Callable] = {}

    def register_adapter(self, name: str, adapter_fn: Callable):
        """Register a protocol adapter"""
        self._adapters[name] = adapter_fn
        self.logger.info(f"Registered protocol adapter: {name}")

    async def translate(
        self, adapter_name: str, data: Any, direction: str = "request"
    ) -> Any:
        """
        Translate data using specified adapter.

        Args:
            adapter_name: Name of adapter to use
            data: Data to translate
            direction: "request" or "response"

        Returns:
            Translated data
        """
        if adapter_name not in self._adapters:
            raise ValueError(f"Adapter {adapter_name} not registered")

        adapter = self._adapters[adapter_name]
        result = adapter(data, direction)
        if asyncio.iscoroutine(result):
            return await result
        return result


class Sidecar:
    """
    Protocol adapter sidecar for AOL services.

    Provides:
    - Tool execution with circuit breakers
    - Protocol translation
    - Metrics collection
    - mTLS proxy support (via Consul Connect)

    Supports all service types: agents, tools, plugins, and general services.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Service identity
        self.service_name = (
            config.get("metadata", {}).get("name")
            or config.get("spec", {}).get("name")
            or config.get("service", {}).get("name")
            or config.get("name", "aol-service")
        )
        self.service_kind = config.get("kind", "AOLService")

        # Components
        self.tool_executor = ToolExecutor(config)
        self.protocol_adapter = ProtocolAdapter()

        # State
        self._running = False

    async def start(self):
        """Start the sidecar"""
        if self._running:
            return

        self._running = True
        self.logger.info(
            f"Starting sidecar for {self.service_name} ({self.service_kind})"
        )

        # Initialize tools from config
        await self._initialize_tools()

        # Register default protocol adapters
        self._register_default_adapters()

        self.logger.info(f"Sidecar started for {self.service_name}")

    async def stop(self):
        """Stop the sidecar"""
        if not self._running:
            return

        self._running = False
        await self.tool_executor.close()
        self.logger.info(f"Sidecar stopped for {self.service_name}")

    async def _initialize_tools(self):
        """Initialize tools from configuration"""
        integrations = self.config.get("integrations", {})
        if not integrations.get("enabled", False):
            return

        tools_config = integrations.get("tools", {})
        if isinstance(tools_config, list):
            for tool in tools_config:
                self._register_tool_from_config(tool)
        elif isinstance(tools_config, dict):
            for name, tool_cfg in tools_config.items():
                tool_cfg["name"] = name
                self._register_tool_from_config(tool_cfg)

    def _register_tool_from_config(self, tool_cfg: Dict[str, Any]):
        """Register a tool from config"""
        import os

        name = tool_cfg.get("name")
        endpoint = tool_cfg.get("endpoint", "")

        # Resolve environment variables
        if endpoint.startswith("${") and endpoint.endswith("}"):
            env_var = endpoint[2:-1]
            endpoint = os.getenv(env_var, "")

        if not name or not endpoint:
            return

        config = ToolConfig(
            name=name,
            endpoint=endpoint,
            timeout=tool_cfg.get("timeout", 30),
            api_key=tool_cfg.get("apiKey"),
            health_check_enabled=tool_cfg.get("healthCheck", {}).get("enabled", True),
            health_check_interval=int(
                tool_cfg.get("healthCheck", {}).get("interval", "30s").rstrip("s")
            ),
        )

        self.tool_executor.register_tool(config)

    def _register_default_adapters(self):
        """Register default protocol adapters"""

        # JSON <-> Dict adapter
        def json_adapter(data: Any, direction: str) -> Any:
            if direction == "request":
                if isinstance(data, str):
                    return json.loads(data)
                return data
            else:
                if isinstance(data, (dict, list)):
                    return json.dumps(data)
                return data

        self.protocol_adapter.register_adapter("json", json_adapter)

    async def register_with_aol(self):
        """Register this service with AOL Core"""
        self.logger.info(
            f"Registering {self.service_name} (kind: {self.service_kind}) with AOL Core"
        )

    async def execute_tool(
        self,
        tool_name: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute a tool action.

        Wrapper around ToolExecutor for convenient tool invocation.

        Args:
            tool_name: Name of tool
            action: Action/path to execute
            payload: Request payload
            **kwargs: Additional arguments

        Returns:
            Execution result
        """
        return await self.tool_executor.execute(
            tool_name=tool_name, path=f"/{action}", payload=payload, **kwargs
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get sidecar metrics"""
        return {
            "service": self.service_name,
            "kind": self.service_kind,
            "tools": self.tool_executor.get_metrics(),
        }
