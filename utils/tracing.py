"""OpenTelemetry tracing setup (optional)"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource


def setup_tracing(config):
    """Setup OpenTelemetry tracing (disabled by default)"""
    # Check if tracing is enabled
    if isinstance(config, dict):
        tracing_enabled = config.get("monitoring", {}).get("tracingEnabled", False)
        jaeger_endpoint = os.getenv(
            "JAEGER_ENDPOINT", config.get("monitoring", {}).get("tracingEndpoint", None)
        )
    else:
        tracing_enabled = False
        jaeger_endpoint = None

    # If tracing is disabled or no endpoint, use a no-op tracer provider
    if not tracing_enabled or not jaeger_endpoint:
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)

    resource = Resource.create(
        {
            "service.name": os.getenv("SERVICE_NAME", "aol-agent"),
            "service.version": "1.0.0",
        }
    )

    provider = TracerProvider(resource=resource)

    try:
        otlp_exporter = OTLPSpanExporter(endpoint=jaeger_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)
    except Exception:
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)
