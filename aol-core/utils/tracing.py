"""OpenTelemetry tracing setup (optional)"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource


def setup_tracing(config):
    """Setup OpenTelemetry tracing (disabled by default)"""
    # Check if tracing is enabled
    tracing_enabled = (
        config.get("spec", {}).get("monitoring", {}).get("tracingEnabled", False)
    )
    jaeger_endpoint = os.getenv(
        "JAEGER_ENDPOINT",
        config.get("spec", {}).get("monitoring", {}).get("tracingEndpoint", None),
    )

    # If tracing is disabled or no endpoint, use a no-op tracer provider
    if not tracing_enabled or not jaeger_endpoint:
        # Set a no-op tracer provider that does nothing
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)

    resource = Resource.create(
        {
            "service.name": config.get("metadata", {}).get("name", "unknown-service"),
            "service.version": config.get("metadata", {}).get("version", "1.0.0"),
        }
    )

    provider = TracerProvider(resource=resource)

    try:
        otlp_exporter = OTLPSpanExporter(endpoint=jaeger_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)
    except Exception:
        # If tracing setup fails, use no-op provider
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)
