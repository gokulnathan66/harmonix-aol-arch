"""
Health Reporter and Lifecycle Manager for AOL Services

This module provides:
- Health status reporting to AOL Core
- Heartbeat pulses for orchestration
- Lifecycle hooks (startup, shutdown, ready, live)
- Readiness and liveness probes
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status states"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    STARTING = "starting"
    STOPPING = "stopping"


class ReadinessStatus(Enum):
    """Readiness states"""

    READY = "ready"
    NOT_READY = "not_ready"


@dataclass
class HealthCheck:
    """Represents a health check"""

    name: str
    check_fn: Callable
    critical: bool = True  # If critical, failure = unhealthy
    timeout: float = 5.0
    last_result: Optional[bool] = None
    last_check_time: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class LifecycleHook:
    """Represents a lifecycle hook"""

    name: str
    hook_fn: Callable
    timeout: float = 30.0
    executed: bool = False
    success: Optional[bool] = None
    error: Optional[str] = None


class HealthReporter:
    """
    Reports health status to AOL Core and manages service lifecycle.

    This class handles:
    - Health check aggregation
    - Heartbeat pulses for orchestration
    - Readiness and liveness probes
    - Graceful startup/shutdown hooks
    """

    def __init__(self, config: Dict[str, Any], aol_core_endpoint: Optional[str] = None):
        self.config = config

        # Service identity
        self.service_name = (
            config.get("metadata", {}).get("name")
            or config.get("spec", {}).get("name")
            or config.get("service", {}).get("name")
            or config.get("name", "aol-service")
        )

        # AOL Core endpoint for health reporting
        import os

        self.aol_core_endpoint = aol_core_endpoint or os.getenv(
            "AOL_CORE_ENDPOINT", "http://aol-core:8080"
        )

        # Health configuration
        health_config = config.get("health", {})
        heartbeat_config = health_config.get("heartbeat", {})

        self.heartbeat_enabled = heartbeat_config.get("enabled", True)
        self.heartbeat_interval = heartbeat_config.get("interval", 10)  # seconds
        self.heartbeat_timeout = heartbeat_config.get("timeout", 5)  # seconds

        # State
        self._status = HealthStatus.STARTING
        self._readiness = ReadinessStatus.NOT_READY
        self._health_checks: Dict[str, HealthCheck] = {}
        self._lifecycle_hooks: Dict[str, List[LifecycleHook]] = {
            "startup": [],
            "ready": [],
            "shutdown": [],
            "pre_stop": [],
        }

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._check_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None

        # Metrics
        self._heartbeat_count = 0
        self._failed_heartbeats = 0
        self._last_heartbeat_time: Optional[datetime] = None

        self.logger = logging.getLogger(__name__)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.heartbeat_timeout)
            )
        return self._session

    # ==================== Health Check Registration ====================

    def register_health_check(
        self, name: str, check_fn: Callable, critical: bool = True, timeout: float = 5.0
    ):
        """
        Register a health check function.

        Args:
            name: Unique name for the check
            check_fn: Async function that returns True if healthy
            critical: If True, check failure makes service unhealthy
            timeout: Timeout for the check
        """
        self._health_checks[name] = HealthCheck(
            name=name, check_fn=check_fn, critical=critical, timeout=timeout
        )
        self.logger.info(f"Registered health check: {name} (critical={critical})")

    def unregister_health_check(self, name: str):
        """Unregister a health check"""
        if name in self._health_checks:
            del self._health_checks[name]
            self.logger.info(f"Unregistered health check: {name}")

    # ==================== Lifecycle Hooks ====================

    def register_startup_hook(
        self, name: str, hook_fn: Callable, timeout: float = 30.0
    ):
        """Register a startup hook"""
        self._lifecycle_hooks["startup"].append(
            LifecycleHook(name=name, hook_fn=hook_fn, timeout=timeout)
        )
        self.logger.info(f"Registered startup hook: {name}")

    def register_ready_hook(self, name: str, hook_fn: Callable, timeout: float = 30.0):
        """Register a ready hook (called when service becomes ready)"""
        self._lifecycle_hooks["ready"].append(
            LifecycleHook(name=name, hook_fn=hook_fn, timeout=timeout)
        )
        self.logger.info(f"Registered ready hook: {name}")

    def register_shutdown_hook(
        self, name: str, hook_fn: Callable, timeout: float = 30.0
    ):
        """Register a shutdown hook"""
        self._lifecycle_hooks["shutdown"].append(
            LifecycleHook(name=name, hook_fn=hook_fn, timeout=timeout)
        )
        self.logger.info(f"Registered shutdown hook: {name}")

    def register_pre_stop_hook(
        self, name: str, hook_fn: Callable, timeout: float = 10.0
    ):
        """Register a pre-stop hook (called before deregistration)"""
        self._lifecycle_hooks["pre_stop"].append(
            LifecycleHook(name=name, hook_fn=hook_fn, timeout=timeout)
        )
        self.logger.info(f"Registered pre-stop hook: {name}")

    async def _execute_hooks(self, phase: str) -> bool:
        """Execute all hooks for a lifecycle phase"""
        hooks = self._lifecycle_hooks.get(phase, [])
        if not hooks:
            return True

        self.logger.info(f"Executing {len(hooks)} {phase} hooks...")
        all_success = True

        for hook in hooks:
            if hook.executed:
                continue

            try:
                result = hook.hook_fn()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result, timeout=hook.timeout)

                hook.executed = True
                hook.success = True
                self.logger.info(f"✓ {phase} hook '{hook.name}' completed")

            except asyncio.TimeoutError:
                hook.executed = True
                hook.success = False
                hook.error = "Timeout"
                all_success = False
                self.logger.error(f"✗ {phase} hook '{hook.name}' timed out")

            except Exception as e:
                hook.executed = True
                hook.success = False
                hook.error = str(e)
                all_success = False
                self.logger.error(f"✗ {phase} hook '{hook.name}' failed: {e}")

        return all_success

    # ==================== Health Check Execution ====================

    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {}
        has_critical_failure = False
        has_any_failure = False

        for name, check in self._health_checks.items():
            try:
                result = check.check_fn()
                if asyncio.iscoroutine(result):
                    result = await asyncio.wait_for(result, timeout=check.timeout)

                check.last_result = bool(result)
                check.last_check_time = datetime.now()
                check.error_message = None

                if not result:
                    has_any_failure = True
                    if check.critical:
                        has_critical_failure = True

                results[name] = {
                    "healthy": check.last_result,
                    "critical": check.critical,
                }

            except asyncio.TimeoutError:
                check.last_result = False
                check.last_check_time = datetime.now()
                check.error_message = "Timeout"
                has_any_failure = True
                if check.critical:
                    has_critical_failure = True

                results[name] = {
                    "healthy": False,
                    "error": "Timeout",
                    "critical": check.critical,
                }

            except Exception as e:
                check.last_result = False
                check.last_check_time = datetime.now()
                check.error_message = str(e)
                has_any_failure = True
                if check.critical:
                    has_critical_failure = True

                results[name] = {
                    "healthy": False,
                    "error": str(e),
                    "critical": check.critical,
                }

        # Update overall status
        if has_critical_failure:
            self._status = HealthStatus.UNHEALTHY
        elif has_any_failure:
            self._status = HealthStatus.DEGRADED
        else:
            self._status = HealthStatus.HEALTHY

        return results

    # ==================== Heartbeat ====================

    async def _heartbeat_loop(self):
        """Background heartbeat loop for orchestration"""
        self.logger.info(
            f"Starting heartbeat loop (interval={self.heartbeat_interval}s)"
        )

        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._failed_heartbeats += 1
                self.logger.warning(f"Heartbeat failed: {e}")

    async def _send_heartbeat(self):
        """Send heartbeat pulse to AOL Core"""
        try:
            session = await self._get_session()

            payload = {
                "service_name": self.service_name,
                "status": self._status.value,
                "readiness": self._readiness.value,
                "timestamp": datetime.utcnow().isoformat(),
                "heartbeat_count": self._heartbeat_count,
                "checks": {
                    name: check.last_result
                    for name, check in self._health_checks.items()
                },
            }

            async with session.post(
                f"{self.aol_core_endpoint}/api/health/heartbeat", json=payload
            ) as resp:
                if resp.status == 200:
                    self._heartbeat_count += 1
                    self._last_heartbeat_time = datetime.now()
                    self.logger.debug(f"Heartbeat #{self._heartbeat_count} sent")
                else:
                    self._failed_heartbeats += 1
                    self.logger.warning(f"Heartbeat rejected: HTTP {resp.status}")

        except Exception as e:
            self._failed_heartbeats += 1
            self.logger.debug(f"Could not send heartbeat: {e}")

    # ==================== Public API ====================

    async def start(self):
        """Start health reporter and execute startup hooks"""
        self.logger.info(f"Starting health reporter for {self.service_name}")

        # Execute startup hooks
        await self._execute_hooks("startup")

        # Start health check loop
        self._check_task = asyncio.create_task(self._health_check_loop())

        # Start heartbeat if enabled
        if self.heartbeat_enabled:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        self.logger.info("Health reporter started")

    async def _health_check_loop(self):
        """Background health check loop"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self.run_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"Health check loop error: {e}")

    async def stop(self):
        """Stop health reporter and execute shutdown hooks"""
        self.logger.info(f"Stopping health reporter for {self.service_name}")
        self._status = HealthStatus.STOPPING

        # Execute pre-stop hooks
        await self._execute_hooks("pre_stop")

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

        # Execute shutdown hooks
        await self._execute_hooks("shutdown")

        # Close session
        if self._session:
            await self._session.close()
            self._session = None

        self.logger.info("Health reporter stopped")

    async def set_ready(self):
        """Mark service as ready"""
        self._readiness = ReadinessStatus.READY
        await self._execute_hooks("ready")
        self.logger.info(f"{self.service_name} is now READY")

    async def set_not_ready(self):
        """Mark service as not ready"""
        self._readiness = ReadinessStatus.NOT_READY
        self.logger.info(f"{self.service_name} is now NOT_READY")

    async def report_health(self, status: str):
        """Report health status (backward compatibility)"""
        self.logger.debug(f"Reporting health: {status}")
        try:
            self._status = HealthStatus(status.lower())
        except ValueError:
            self._status = (
                HealthStatus.HEALTHY if status == "healthy" else HealthStatus.UNHEALTHY
            )

    # ==================== Status Getters ====================

    def get_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "service": self.service_name,
            "status": self._status.value,
            "readiness": self._readiness.value,
            "checks": {
                name: {
                    "healthy": check.last_result,
                    "last_check": (
                        check.last_check_time.isoformat()
                        if check.last_check_time
                        else None
                    ),
                    "error": check.error_message,
                }
                for name, check in self._health_checks.items()
            },
            "heartbeat": {
                "enabled": self.heartbeat_enabled,
                "count": self._heartbeat_count,
                "failed": self._failed_heartbeats,
                "last_time": (
                    self._last_heartbeat_time.isoformat()
                    if self._last_heartbeat_time
                    else None
                ),
            },
        }

    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        return self._status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self._readiness == ReadinessStatus.READY

    # ==================== HTTP Handlers ====================

    async def health_handler(self) -> Dict[str, Any]:
        """Handler for /health endpoint"""
        await self.run_health_checks()
        return {
            "status": "healthy" if self.is_healthy() else "unhealthy",
            "service": self.service_name,
            "checks": {
                name: check.last_result for name, check in self._health_checks.items()
            },
        }

    async def ready_handler(self) -> Dict[str, Any]:
        """Handler for /ready endpoint"""
        return {"ready": self.is_ready(), "service": self.service_name}

    async def live_handler(self) -> Dict[str, Any]:
        """Handler for /live endpoint"""
        return {
            "live": self._status != HealthStatus.STOPPING,
            "service": self.service_name,
        }
