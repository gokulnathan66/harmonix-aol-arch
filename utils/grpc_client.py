"""gRPC client with load balancing using aol-core service discovery"""

import grpc
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from typing import List, Optional, Dict
import random
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from utils.consul_client import AOLServiceDiscoveryClient

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking"""

    failures: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    threshold: int = 5
    timeout: int = 60  # seconds


class LoadBalancedGRPCClient:
    """gRPC client with round-robin load balancing using aol-core service discovery"""

    def __init__(self, service_name: str, aol_core_endpoint: str = None):
        self.service_name = service_name
        self.discovery_client = AOLServiceDiscoveryClient(aol_core_endpoint)
        self.current_index = 0
        self.circuit_breaker = CircuitBreakerState()
        self.logger = logging.getLogger(__name__)
        self._cached_instances = []
        self._cache_ttl = timedelta(seconds=30)
        self._cache_time = None

    async def _get_service_instances(self) -> List[Dict]:
        """Get service instances from aol-core (with caching)"""
        now = datetime.now()

        # Use cache if still valid
        if self._cached_instances and self._cache_time:
            if (now - self._cache_time) < self._cache_ttl:
                return self._cached_instances

        # Query aol-core
        instances = await self.discovery_client.discover_service(
            self.service_name, healthy_only=True
        )

        if instances:
            self._cached_instances = instances
            self._cache_time = now

        return instances

    def _get_next_endpoint(self, instances: List[Dict]) -> Optional[str]:
        """Round-robin endpoint selection"""
        if not instances:
            self.logger.error(f"No healthy instances found for {self.service_name}")
            return None

        # Round-robin selection
        instance = instances[self.current_index % len(instances)]
        self.current_index = (self.current_index + 1) % len(instances)

        return f"{instance['address']}:{instance['port']}"

    def _check_circuit_breaker(self):
        """Check if circuit breaker is open"""
        if self.circuit_breaker.state == "OPEN":
            if self.circuit_breaker.last_failure_time:
                elapsed = (
                    datetime.now() - self.circuit_breaker.last_failure_time
                ).seconds
                if elapsed > self.circuit_breaker.timeout:
                    self.circuit_breaker.state = "HALF_OPEN"
                    self.logger.info(
                        f"Circuit breaker HALF_OPEN for {self.service_name}"
                    )
                else:
                    raise Exception(f"Circuit breaker OPEN for {self.service_name}")
            else:
                self.circuit_breaker.state = "CLOSED"

    def _record_success(self):
        """Record successful call"""
        if self.circuit_breaker.state == "HALF_OPEN":
            self.circuit_breaker.state = "CLOSED"
            self.circuit_breaker.failures = 0
            self.logger.info(f"Circuit breaker CLOSED for {self.service_name}")
        elif self.circuit_breaker.state == "CLOSED":
            self.circuit_breaker.failures = 0

    def _record_failure(self):
        """Record failed call"""
        self.circuit_breaker.failures += 1
        self.circuit_breaker.last_failure_time = datetime.now()

        if self.circuit_breaker.failures >= self.circuit_breaker.threshold:
            self.circuit_breaker.state = "OPEN"
            self.logger.warning(f"Circuit breaker OPEN for {self.service_name}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(grpc.RpcError),
    )
    async def call(self, stub_class, method_name, request, timeout=30):
        """Execute gRPC call with load balancing, retry, and circuit breaker"""

        # Check circuit breaker
        self._check_circuit_breaker()

        # Get service instances from aol-core
        instances = await self._get_service_instances()
        if not instances:
            raise Exception(f"No available instances for {self.service_name}")

        # Get endpoint
        endpoint = self._get_next_endpoint(instances)
        if not endpoint:
            raise Exception(f"No available endpoints for {self.service_name}")

        try:
            # Create channel with keepalive
            channel = grpc.aio.insecure_channel(
                endpoint,
                options=[
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                    ("grpc.keepalive_permit_without_calls", True),
                    ("grpc.http2.max_pings_without_data", 0),
                    ("grpc.lb_policy_name", "round_robin"),
                ],
            )

            stub = stub_class(channel)
            method = getattr(stub, method_name)

            response = await method(request, timeout=timeout)

            # Record success
            self._record_success()

            await channel.close()
            return response

        except grpc.RpcError as e:
            self.logger.error(f"gRPC error calling {self.service_name}: {e.code()}")
            self._record_failure()
            raise
        except Exception as e:
            self.logger.error(f"Error calling {self.service_name}: {e}")
            self._record_failure()
            raise

    async def close(self):
        """Close discovery client"""
        await self.discovery_client.close()
