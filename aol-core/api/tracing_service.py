"""Tracing Service API - Receives traces and forwards to Jaeger"""
import os
import logging
import grpc
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse
)
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2_grpc
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

logger = logging.getLogger(__name__)

class TracingServiceServicer(trace_service_pb2_grpc.TraceServiceServicer):
    """gRPC servicer for OTLP trace ingestion"""
    
    def __init__(self, jaeger_endpoint: str = None):
        self.jaeger_endpoint = jaeger_endpoint or os.getenv('JAEGER_ENDPOINT', 'jaeger:4317')
        self.exporter = None
        
        if self.jaeger_endpoint:
            try:
                self.exporter = OTLPSpanExporter(
                    endpoint=self.jaeger_endpoint,
                    insecure=True
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Jaeger exporter: {e}")
    
    async def Export(self, request: ExportTraceServiceRequest, context):
        """Export traces to Jaeger"""
        try:
            if self.exporter:
                # Forward to Jaeger
                await self.exporter.export(request.resource_spans)
                logger.debug(f"Exported {len(request.resource_spans)} trace spans")
            else:
                logger.warning("Tracing exporter not configured, traces not forwarded")
            
            return ExportTraceServiceResponse()
        except Exception as e:
            logger.error(f"Error exporting traces: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return ExportTraceServiceResponse()

def setup_tracing_service(server, jaeger_endpoint: str = None):
    """Setup tracing service gRPC endpoint"""
    servicer = TracingServiceServicer(jaeger_endpoint)
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(servicer, server)
    logger.info("Tracing service (OTLP) registered on gRPC server")

