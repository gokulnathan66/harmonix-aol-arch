"""AOL Core main entrypoint"""

import asyncio
import grpc
from concurrent import futures
import signal
import sys

from registry.service_registry import ServiceRegistry
from registry.consul_registry import (
    ConsulServiceRegistry,
    ServiceInstance as ConsulServiceInstance,
)
from router.grpc_router import GRPCRouter
from health.health_manager import HealthManager
from aol_core_servicer import AOLCoreServicer
from event_store import EventStore
from monitor_api import setup_monitor_api
from utils.tracing import setup_tracing
from utils.metrics import setup_metrics
from utils.logging import setup_logging
from api.service_discovery import setup_service_discovery_api
from api.proto_registry import setup_proto_registry_api, ProtoRegistry
from api.logging_service import setup_logging_service_api, LoggingService
from api.metrics_service import setup_metrics_service_api, MetricsService
from api.tracing_service import setup_tracing_service
import yaml
from aiohttp import web
import socket


class AOLCore:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.logger = setup_logging(self.config)
        self.logger.info("Initializing AOL Core with Consul")

        # Initialize Consul registry (REPLACE docker_discovery)
        consul_config = self.config["spec"].get("consul", {})
        self.consul_registry = ConsulServiceRegistry(
            consul_host=consul_config.get("host", "consul-server"),
            consul_port=consul_config.get("port", 8500),
        )

        # Initialize components
        self.registry = ServiceRegistry(self.config)
        self.event_store = EventStore(max_events=1000)
        self.router = GRPCRouter(self.config, self.registry)
        self.health_manager = HealthManager(
            self.config, self.registry, self.event_store
        )

        # Register self with Consul
        self._register_self()

        # Setup monitoring
        setup_tracing(self.config)
        setup_metrics(self.config)

        # Setup HTTP server with health and monitoring API
        self.health_app = web.Application()
        self.health_app.router.add_get("/health", self.health_handler)

        # Setup monitoring API
        setup_monitor_api(self.health_app, self.registry, self.event_store)

        # Setup aol-core service APIs
        setup_service_discovery_api(self.health_app, self.consul_registry)

        # Setup proto registry
        self.proto_registry = ProtoRegistry()
        setup_proto_registry_api(self.health_app, self.proto_registry)

        # Setup logging service
        self.logging_service = LoggingService()
        setup_logging_service_api(self.health_app, self.logging_service)

        # Setup metrics service
        self.metrics_service = MetricsService()
        setup_metrics_service_api(self.health_app, self.metrics_service)

        self.health_runner = None

    def _register_self(self):
        """Register AOL Core with Consul"""
        hostname = socket.gethostname()

        instance = ConsulServiceInstance(
            id=f"aol-core-{hostname}",
            name="aol-core",
            address=hostname,
            port=50051,
            health_port=50201,
            metrics_port=50201,
            tags=["aol", "core", "orchestrator"],
            meta={"version": "1.0.0", "health_port": "50201", "metrics_port": "50201"},
        )

        self.consul_registry.register_service(instance)

    async def health_handler(self, request):
        """HTTP health check endpoint"""
        return web.json_response(
            {"status": "healthy", "services": len(await self.registry.list_services())}
        )

    async def start(self):
        """Start all AOL Core services"""
        self.logger.info("Starting AOL Core services")

        # Start HTTP health server
        health_port = self.config["spec"]["monitoring"]["healthPort"]
        self.health_runner = web.AppRunner(self.health_app)
        await self.health_runner.setup()
        site = web.TCPSite(self.health_runner, "0.0.0.0", health_port)
        await site.start()
        self.logger.info(f"Health check server started on port {health_port}")

        # NO MORE docker discovery - Consul handles it

        # Start health checking
        asyncio.create_task(self.health_manager.run_health_checks())

        # Start gRPC server
        server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

        # Register gRPC services
        try:
            import aol_service_pb2_grpc

            servicer = AOLCoreServicer(self.registry, self.event_store)
            aol_service_pb2_grpc.add_AOLCoreServicer_to_server(servicer, server)
            self.logger.info("gRPC services registered")

            # Register tracing service (OTLP)
            setup_tracing_service(server)
        except ImportError as e:
            self.logger.warning(f"Protobuf stubs not available: {e}")
            self.logger.warning(
                "gRPC services will not be available until protobuf files are generated"
            )
        except Exception as e:
            self.logger.error(f"Error registering gRPC services: {e}")

        gateway_config = self.config["spec"]["gateway"]
        listen_addr = f"{gateway_config['host']}:{gateway_config['port']}"
        server.add_insecure_port(listen_addr)

        await server.start()
        self.logger.info(f"AOL Core gRPC gateway listening on {listen_addr}")

        await server.wait_for_termination()

    def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down AOL Core")
        hostname = socket.gethostname()
        self.consul_registry.deregister_service(f"aol-core-{hostname}")
        self.health_manager.stop()
        if self.health_runner:
            asyncio.create_task(self.health_runner.cleanup())


if __name__ == "__main__":
    aol = AOLCore()

    def signal_handler(sig, frame):
        aol.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(aol.start())
    except KeyboardInterrupt:
        aol.shutdown()
