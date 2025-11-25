"""
Base Integration - Abstract base classes for integrations

This module provides the foundation for building pluggable integrations
that can be easily swapped without affecting service logic.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class IntegrationStatus(Enum):
    """Integration status states"""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class IntegrationError(Exception):
    """Base exception for integration errors"""
    
    def __init__(
        self,
        message: str,
        integration_name: str = None,
        error_code: str = None,
        retryable: bool = False,
        details: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.integration_name = integration_name
        self.error_code = error_code
        self.retryable = retryable
        self.details = details or {}


@dataclass
class IntegrationConfig:
    """Configuration for an integration"""
    name: str
    endpoint: str
    timeout: int = 30
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    
    # Health check settings
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    health_check_interval: int = 30
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_multiplier: float = 2.0


@dataclass
class IntegrationResult:
    """Result from an integration call"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    latency_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, data: Any, latency_ms: float = 0, **metadata) -> 'IntegrationResult':
        """Create a successful result"""
        return cls(success=True, data=data, latency_ms=latency_ms, metadata=metadata)
    
    @classmethod
    def fail(
        cls,
        error: str,
        error_code: str = None,
        latency_ms: float = 0,
        **metadata
    ) -> 'IntegrationResult':
        """Create a failed result"""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            latency_ms=latency_ms,
            metadata=metadata
        )


class BaseIntegration(ABC):
    """
    Abstract base class for all integrations.
    
    Provides common functionality like:
    - Health checking
    - Metrics collection
    - Error handling
    - Configuration management
    
    Subclass this to create specific integrations (LLM, search, etc.)
    """
    
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.name}")
        
        # State
        self._status = IntegrationStatus.UNKNOWN
        self._initialized = False
        self._last_health_check: Optional[datetime] = None
        
        # Metrics
        self._total_calls = 0
        self._successful_calls = 0
        self._failed_calls = 0
        self._total_latency_ms = 0
    
    @property
    def name(self) -> str:
        """Integration name"""
        return self.config.name
    
    @property
    def status(self) -> IntegrationStatus:
        """Current status"""
        return self._status
    
    @property
    def is_healthy(self) -> bool:
        """Check if integration is healthy"""
        return self._status in (IntegrationStatus.HEALTHY, IntegrationStatus.DEGRADED)
    
    # ==================== Lifecycle ====================
    
    async def initialize(self):
        """Initialize the integration"""
        if self._initialized:
            return
        
        self.logger.info(f"Initializing integration: {self.name}")
        
        try:
            await self._do_initialize()
            self._initialized = True
            
            # Initial health check
            if self.config.health_check_enabled:
                await self.check_health()
            else:
                self._status = IntegrationStatus.HEALTHY
            
            self.logger.info(f"Integration {self.name} initialized successfully")
            
        except Exception as e:
            self._status = IntegrationStatus.UNHEALTHY
            self.logger.error(f"Failed to initialize {self.name}: {e}")
            raise IntegrationError(
                f"Initialization failed: {e}",
                integration_name=self.name,
                retryable=True
            )
    
    async def shutdown(self):
        """Shutdown the integration"""
        if not self._initialized:
            return
        
        self.logger.info(f"Shutting down integration: {self.name}")
        
        try:
            await self._do_shutdown()
            self._initialized = False
            self.logger.info(f"Integration {self.name} shut down successfully")
        except Exception as e:
            self.logger.error(f"Error shutting down {self.name}: {e}")
    
    @abstractmethod
    async def _do_initialize(self):
        """Perform integration-specific initialization"""
        pass
    
    async def _do_shutdown(self):
        """Perform integration-specific shutdown (optional override)"""
        pass
    
    # ==================== Health Check ====================
    
    async def check_health(self) -> bool:
        """Check integration health"""
        try:
            healthy = await self._do_health_check()
            self._last_health_check = datetime.now()
            
            if healthy:
                if self._status == IntegrationStatus.DEGRADED:
                    self._status = IntegrationStatus.HEALTHY
                    self.logger.info(f"{self.name} recovered to HEALTHY")
                else:
                    self._status = IntegrationStatus.HEALTHY
            else:
                self._status = IntegrationStatus.DEGRADED
                self.logger.warning(f"{self.name} is DEGRADED")
            
            return healthy
            
        except Exception as e:
            self._status = IntegrationStatus.UNHEALTHY
            self._last_health_check = datetime.now()
            self.logger.error(f"{self.name} health check failed: {e}")
            return False
    
    async def _do_health_check(self) -> bool:
        """Perform integration-specific health check (override as needed)"""
        return True
    
    # ==================== Execution ====================
    
    async def execute(
        self,
        action: str,
        payload: Dict[str, Any] = None,
        **kwargs
    ) -> IntegrationResult:
        """
        Execute an action on the integration.
        
        Args:
            action: Action/method to execute
            payload: Request payload
            **kwargs: Additional arguments
            
        Returns:
            IntegrationResult with success/failure and data
        """
        if not self._initialized:
            await self.initialize()
        
        import time
        start_time = time.time()
        self._total_calls += 1
        
        try:
            result = await self._do_execute(action, payload or {}, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            
            self._successful_calls += 1
            self._total_latency_ms += latency_ms
            
            return IntegrationResult.ok(
                data=result,
                latency_ms=latency_ms,
                action=action
            )
            
        except IntegrationError:
            self._failed_calls += 1
            raise
            
        except Exception as e:
            self._failed_calls += 1
            latency_ms = (time.time() - start_time) * 1000
            
            self.logger.error(f"{self.name} execute failed: {e}")
            
            return IntegrationResult.fail(
                error=str(e),
                latency_ms=latency_ms,
                action=action
            )
    
    @abstractmethod
    async def _do_execute(
        self,
        action: str,
        payload: Dict[str, Any],
        **kwargs
    ) -> Any:
        """Perform integration-specific execution"""
        pass
    
    # ==================== Metrics ====================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get integration metrics"""
        return {
            'name': self.name,
            'status': self._status.value,
            'initialized': self._initialized,
            'total_calls': self._total_calls,
            'successful_calls': self._successful_calls,
            'failed_calls': self._failed_calls,
            'success_rate': (
                self._successful_calls / self._total_calls
                if self._total_calls > 0 else 0
            ),
            'avg_latency_ms': (
                self._total_latency_ms / self._successful_calls
                if self._successful_calls > 0 else 0
            ),
            'last_health_check': (
                self._last_health_check.isoformat()
                if self._last_health_check else None
            )
        }

