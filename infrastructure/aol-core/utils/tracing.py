"""Enhanced OpenTelemetry tracing setup for AOL Core

This module provides comprehensive observability including:
- Agent-specific span attributes
- Workflow tracing
- Integration with external observability platforms
- Anomaly detection for proactive failure identification
"""
import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)


class AOLSpanAttributes:
    """Standard span attributes for AOL Core tracing"""
    # Service identification
    SERVICE_NAME = "aol.service.name"
    SERVICE_VERSION = "aol.service.version"
    SERVICE_TYPE = "aol.service.type"
    
    # Agent specific
    AGENT_ID = "aol.agent.id"
    AGENT_CONTRIBUTION = "aol.agent.contribution"
    AGENT_HEALTH = "aol.agent.health"
    
    # Workflow
    WORKFLOW_ID = "aol.workflow.id"
    WORKFLOW_STEP = "aol.workflow.step"
    
    # Routing
    ROUTE_SOURCE = "aol.route.source"
    ROUTE_TARGET = "aol.route.target"
    ROUTE_LATENCY_MS = "aol.route.latency_ms"
    
    # Health
    HEALTH_CHECK_TARGET = "aol.health.target"
    HEALTH_STATUS = "aol.health.status"


def setup_tracing(config: Dict) -> trace.Tracer:
    """Setup OpenTelemetry tracing with enhanced observability
    
    Features:
    - OTLP export to Jaeger/Tempo/Grafana
    - Agent-specific resource attributes
    - Automatic span context propagation
    
    Args:
        config: AOL Core configuration dictionary
        
    Returns:
        Configured tracer instance
    """
    # Extract configuration
    if isinstance(config, dict):
        spec = config.get('spec', {})
        monitoring = spec.get('monitoring', {})
        
        tracing_enabled = monitoring.get('tracingEnabled', False)
        otlp_endpoint = os.getenv(
            'OTEL_EXPORTER_OTLP_ENDPOINT',
            os.getenv(
                'JAEGER_ENDPOINT',
                monitoring.get('tracingEndpoint')
            )
        )
        
        service_name = config.get('metadata', {}).get('name', 'aol-core')
        service_version = config.get('metadata', {}).get('version', '1.0.0')
    else:
        tracing_enabled = False
        otlp_endpoint = None
        service_name = 'aol-core'
        service_version = '1.0.0'
    
    # Build resource with AOL-specific attributes
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "service.namespace": "aol",
        "deployment.environment": os.getenv('ENVIRONMENT', 'development'),
        "aol.component": "core",
        "aol.datacenter": os.getenv('DATACENTER', 'heart-pulse-dc1'),
    })
    
    provider = TracerProvider(resource=resource)
    
    # Configure exporters if tracing is enabled
    if tracing_enabled and otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=True
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"Tracing enabled with OTLP endpoint: {otlp_endpoint}")
        except Exception as e:
            logger.warning(f"Failed to setup OTLP exporter: {e}")
    else:
        logger.info("Tracing disabled or no endpoint configured")
    
    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Get a tracer instance"""
    return trace.get_tracer(name)


def trace_route(
    source_service: str,
    target_service: str,
    method: str
):
    """Decorator for tracing route calls"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                f"route:{source_service}->{target_service}",
                attributes={
                    AOLSpanAttributes.ROUTE_SOURCE: source_service,
                    AOLSpanAttributes.ROUTE_TARGET: target_service,
                    "rpc.method": method,
                }
            ) as span:
                start_time = datetime.utcnow()
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                finally:
                    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    span.set_attribute(AOLSpanAttributes.ROUTE_LATENCY_MS, latency_ms)
        return wrapper
    return decorator


def trace_health_check(target_service: str):
    """Decorator for tracing health checks"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                f"health_check:{target_service}",
                attributes={
                    AOLSpanAttributes.HEALTH_CHECK_TARGET: target_service,
                }
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    status = result if isinstance(result, str) else "healthy"
                    span.set_attribute(AOLSpanAttributes.HEALTH_STATUS, status)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_attribute(AOLSpanAttributes.HEALTH_STATUS, "unhealthy")
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        return wrapper
    return decorator


def trace_workflow_step(
    workflow_id: str,
    step_name: str,
    agent_id: Optional[str] = None
):
    """Decorator for tracing workflow steps"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            attributes = {
                AOLSpanAttributes.WORKFLOW_ID: workflow_id,
                AOLSpanAttributes.WORKFLOW_STEP: step_name,
            }
            if agent_id:
                attributes[AOLSpanAttributes.AGENT_ID] = agent_id
            
            with tracer.start_as_current_span(
                f"workflow_step:{step_name}",
                attributes=attributes
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator
