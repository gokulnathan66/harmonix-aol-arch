"""
AOL Service Utilities

This module provides utility functions and clients for:
- Service discovery via aol-core
- Database access via brokered client
- gRPC communication with load balancing
- Event bus for pub-sub messaging
- Schema validation
- Logging and tracing
"""

from utils.consul_client import AOLServiceDiscoveryClient
from utils.db_client import (
    DatabaseClient,
    DataClientError,
    PermissionDeniedError,
    CollectionNotFoundError,
)
from utils.grpc_client import LoadBalancedGRPCClient
from utils.event_bus import EventBusClient, LocalEventBus, Event, EventPriority
from utils.validators import (
    ManifestValidator,
    ConfigValidator,
    PayloadValidator,
    ValidationResult,
    ValidationIssue,
    validate_manifest,
    validate_config,
)
from utils.logging import setup_logging
from utils.tracing import setup_tracing

__all__ = [
    # Service discovery
    "AOLServiceDiscoveryClient",
    # Database
    "DatabaseClient",
    "DataClientError",
    "PermissionDeniedError",
    "CollectionNotFoundError",
    # gRPC
    "LoadBalancedGRPCClient",
    # Event bus
    "EventBusClient",
    "LocalEventBus",
    "Event",
    "EventPriority",
    # Validation
    "ManifestValidator",
    "ConfigValidator",
    "PayloadValidator",
    "ValidationResult",
    "ValidationIssue",
    "validate_manifest",
    "validate_config",
    # Observability
    "setup_logging",
    "setup_tracing",
]
