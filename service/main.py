"""
AOL Service Template - Full Multi-Agent Orchestration Support

This template implements the comprehensive AOL service requirements:
- Service Registration & Discovery (Consul-based)
- Communication Interfaces (gRPC/HTTP with health checks)
- Data Brokering (namespace-isolated collections)
- Integration Hooks (tool dependencies, LLM adapters)
- Loose Coupling (event-driven pub-sub, circuit breakers)
- Lifecycle Management (heartbeats, hooks, graceful shutdown)
"""
import asyncio
import os
import sys
import yaml
import logging
import socket
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from aiohttp import web
from opentelemetry import trace
from prometheus_client import Counter, Histogram, Gauge

from utils.tracing import setup_tracing
from utils.logging import setup_logging
from utils.db_client import DatabaseClient
from utils.consul_client import AOLServiceDiscoveryClient
from utils.event_bus import EventBusClient, Event, EventPriority
from utils.validators import validate_manifest, validate_config
from sidecar.health import HealthReporter, HealthStatus
from sidecar.sidecar import Sidecar
from integration.tool_registry import ToolRegistry

import consul

tracer = trace.get_tracer(__name__)

# Metrics
service_counter = Counter('service_operations_total', 'Total service operations', ['operation', 'status'])
service_duration = Histogram('service_operation_duration_seconds', 'Operation duration', ['operation'])
active_requests = Gauge('service_active_requests', 'Currently active requests')
event_counter = Counter('service_events_total', 'Events published/received', ['direction', 'topic'])


class AOLService:
    """
    Template AOL Service with full multi-agent orchestration support.
    
    This base class can be used for:
    - AI Agents (reasoning, analysis, decision-making)
    - Tools (external API integrations, utilities)
    - Plugins (extensible functionality)
    - Services (any AOL-compliant microservice)
    
    Key Features:
    - Consul-based service registration
    - aol-core service discovery
    - Event-driven pub-sub messaging
    - Brokered data persistence
    - Circuit breakers and retries
    - Health monitoring and heartbeats
    - Lifecycle hooks
    """
    
    def __init__(self, config_path: str = 'config.yaml', manifest_path: str = 'manifest.yaml'):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Load manifest for declarative configuration
        self.manifest = {}
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                self.manifest = yaml.safe_load(f)
        
        # Service identity
        self.service_name = self._get_service_name()
        self.service_kind = self.manifest.get('kind', 'AOLService')
        self.service_version = self.manifest.get('metadata', {}).get('version', '1.0.0')
        
        # Setup logging
        self.logger = setup_logging({
            'spec': {
                'logging': {
                    'level': self.config.get('monitoring', {}).get('logLevel', 'INFO'),
                    'format': 'json'
                }
            }
        })
        
        # Validate configuration on startup
        self._validate_configuration()
        
        # Setup tracing
        setup_tracing({
            'metadata': {'name': self.service_name, 'version': self.service_version},
            'spec': {
                'monitoring': {
                    'tracingEnabled': self.config.get('monitoring', {}).get('tracingEnabled', False),
                    'tracingEndpoint': os.getenv('JAEGER_ENDPOINT', None)
                }
            }
        })
        
        # ============================================================
        # ARCHITECTURE PATTERN (Same for ALL services):
        # ============================================================
        # 1. Register WITH Consul directly (service registry)
        #    - All services register themselves with Consul
        #    - Consul is the central service registry
        # 2. Discover OTHER services VIA aol-core (service discovery)
        #    - aol-core reads from Consul and provides discovery API
        #    - aol-core is the SAME instance for everyone
        #    - Use AOLServiceDiscoveryClient to query aol-core
        # 3. Communicate via events (loose coupling)
        #    - Use EventBusClient for async pub-sub
        #    - Services don't call each other directly
        # ============================================================
        
        # Initialize Consul client for registration
        consul_host = os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[0]
        consul_port = int(os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[1] if ':' in os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500') else 8500)
        self.consul_client = consul.Consul(host=consul_host, port=consul_port)
        
        # Initialize aol-core service discovery client
        aol_core_endpoint = os.getenv('AOL_CORE_ENDPOINT', 'http://aol-core:8080')
        self.discovery_client = AOLServiceDiscoveryClient(aol_core_endpoint)
        
        # Initialize event bus for pub-sub
        self.event_bus: Optional[EventBusClient] = None
        if self.config.get('pubsub', {}).get('enabled', True):
            self.event_bus = EventBusClient(
                service_name=self.service_name,
                aol_core_endpoint=aol_core_endpoint,
                max_queue_size=self.config.get('pubsub', {}).get('maxQueueSize', 1000)
            )
        
        # Initialize health reporter with lifecycle hooks
        self.health_reporter = HealthReporter(
            config=self.config,
            aol_core_endpoint=aol_core_endpoint
        )
        
        # Initialize sidecar for tool execution
        self.sidecar = Sidecar(self.config)
        
        # Initialize tool registry
        self.tool_registry = ToolRegistry(self.config)
        
        # Initialize data client if enabled
        self.data_client: Optional[DatabaseClient] = None
        self._initialize_data_client()
        
        # Register lifecycle hooks
        self._register_lifecycle_hooks()
        
        # Register this service with Consul
        self._register_self()
    
    def _get_service_name(self) -> str:
        """Get service name from config or manifest"""
        return (
            self.manifest.get('metadata', {}).get('name') or
            self.config.get('service', {}).get('name') or
            self.config.get('metadata', {}).get('name') or
            self.config.get('name', 'aol-service')
        )
    
    def _validate_configuration(self):
        """Validate manifest and config on startup"""
        # Validate manifest if exists
        manifest_path = os.path.join(os.path.dirname(__file__), '..', 'manifest.yaml')
        if os.path.exists(manifest_path):
            result = validate_manifest(manifest_path)
            if not result.valid:
                self.logger.warning(f"Manifest validation warnings: {len(result.warnings)} warnings, {len(result.errors)} errors")
                for issue in result.errors:
                    self.logger.error(f"Manifest error: {issue}")
        
        # Validate config
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        if os.path.exists(config_path):
            result = validate_config(config_path)
            if not result.valid:
                for issue in result.errors:
                    self.logger.error(f"Config error: {issue}")
    
    def _register_lifecycle_hooks(self):
        """Register default lifecycle hooks"""
        # Startup hooks
        self.health_reporter.register_startup_hook(
            name="initialize_connections",
            hook_fn=self._on_startup
        )
        
        # Ready hooks
        self.health_reporter.register_ready_hook(
            name="subscribe_to_events",
            hook_fn=self._on_ready
        )
        
        # Shutdown hooks
        self.health_reporter.register_shutdown_hook(
            name="cleanup_connections",
            hook_fn=self._on_shutdown
        )
        
        # Pre-stop hooks
        self.health_reporter.register_pre_stop_hook(
            name="drain_requests",
            hook_fn=self._on_pre_stop
        )
        
        # Register health checks
        self.health_reporter.register_health_check(
            name="data_client",
            check_fn=self._check_data_client_health,
            critical=False
        )
        
        self.health_reporter.register_health_check(
            name="consul",
            check_fn=self._check_consul_health,
            critical=True
        )
    
    async def _on_startup(self):
        """Startup hook - initialize connections"""
        self.logger.info(f"Starting {self.service_name} ({self.service_kind})...")
        
        # Start event bus
        if self.event_bus:
            await self.event_bus.start()
        
        # Start sidecar
        await self.sidecar.start()
        
        # Publish startup event
        await self._publish_event(
            topic="service.lifecycle",
            event_type="ServiceStarted",
            payload={
                'service': self.service_name,
                'kind': self.service_kind,
                'version': self.service_version
            }
        )
    
    async def _on_ready(self):
        """Ready hook - subscribe to events"""
        self.logger.info(f"{self.service_name} is ready")
        
        # Subscribe to orchestration commands
        if self.event_bus:
            await self.event_bus.subscribe(
                topic="orchestration.commands",
                handler=self._handle_orchestration_command
            )
            
            # Subscribe to task requests for this service
            await self.event_bus.subscribe(
                topic=f"task.{self.service_name}",
                handler=self._handle_task_request
            )
        
        # Publish ready event
        await self._publish_event(
            topic="service.lifecycle",
            event_type="ServiceReady",
            payload={
                'service': self.service_name,
                'kind': self.service_kind
            }
        )
    
    async def _on_pre_stop(self):
        """Pre-stop hook - prepare for shutdown"""
        self.logger.info(f"Preparing {self.service_name} for shutdown...")
        
        # Publish pre-stop event
        await self._publish_event(
            topic="service.lifecycle",
            event_type="ServiceStopping",
            payload={'service': self.service_name}
        )
        
        # Give in-flight requests time to complete
        grace_period = self.config.get('health', {}).get('lifecycle', {}).get('preStopDelay', 5)
        await asyncio.sleep(grace_period)
    
    async def _on_shutdown(self):
        """Shutdown hook - cleanup connections"""
        self.logger.info(f"Shutting down {self.service_name}...")
        
        # Publish shutdown event
        await self._publish_event(
            topic="service.lifecycle",
            event_type="ServiceStopped",
            payload={'service': self.service_name}
        )
        
        # Stop event bus
        if self.event_bus:
            await self.event_bus.stop()
        
        # Stop sidecar
        await self.sidecar.stop()
        
        # Close data client
        if self.data_client:
            await self.data_client.close()
        
        # Close discovery client
        await self.discovery_client.close()
        
        # Close tool registry
        await self.tool_registry.close()
    
    async def _check_data_client_health(self) -> bool:
        """Health check for data client"""
        if not self.data_client:
            return True  # Not configured, so not unhealthy
        # Could add actual health check here
        return True
    
    async def _check_consul_health(self) -> bool:
        """Health check for Consul connection"""
        try:
            self.consul_client.status.leader()
            return True
        except Exception:
            return False
    
    async def _handle_orchestration_command(self, event: Event):
        """Handle orchestration commands from aol-core"""
        self.logger.info(f"Received orchestration command: {event.event_type}")
        
        command = event.payload.get('command')
        if command == 'health_check':
            # Respond with health status
            await self._publish_event(
                topic="orchestration.responses",
                event_type="HealthCheckResponse",
                payload={
                    'service': self.service_name,
                    'status': self.health_reporter.get_status()
                },
                correlation_id=event.correlation_id
            )
    
    async def _handle_task_request(self, event: Event):
        """Handle incoming task requests"""
        self.logger.info(f"Received task request: {event.event_id}")
        
        try:
            # Process the task
            result = await self.Process(event.payload)
            
            # Publish completion event
            await self._publish_event(
                topic="task.completed",
                event_type="TaskCompleted",
                payload={
                    'task_id': event.event_id,
                    'service': self.service_name,
                    'result': result,
                    'success': True
                },
                correlation_id=event.correlation_id
            )
            
        except Exception as e:
            # Publish failure event
            await self._publish_event(
                topic="task.completed",
                event_type="TaskFailed",
                payload={
                    'task_id': event.event_id,
                    'service': self.service_name,
                    'error': str(e),
                    'success': False
                },
                correlation_id=event.correlation_id
            )
    
    async def _publish_event(
        self,
        topic: str,
        event_type: str,
        payload: Dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: str = None
    ):
        """Publish an event to the event bus"""
        if self.event_bus:
            await self.event_bus.publish(
                topic=topic,
                event_type=event_type,
                payload=payload,
                priority=priority,
                correlation_id=correlation_id
            )
            event_counter.labels(direction='published', topic=topic).inc()
    
    def _register_self(self):
        """Register service with Consul directly"""
        hostname = socket.gethostname()
        service_id = f"{self.service_name}-{hostname}"
        
        # Get ports from manifest or config
        endpoints = self.manifest.get('spec', {}).get('endpoints', {})
        grpc_port = int(endpoints.get('grpc') or self.config.get('spec', {}).get('grpcPort') or 50050)
        health_port = int(endpoints.get('health') or self.config.get('spec', {}).get('healthPort') or 50200)
        metrics_port = int(endpoints.get('metrics') or self.config.get('spec', {}).get('metricsPort') or 8080)
        
        # Build tags from manifest labels
        labels = self.manifest.get('metadata', {}).get('labels', {})
        tags = [self.service_kind.lower()] + list(labels.values())
        
        try:
            self.consul_client.agent.service.register(
                name=self.service_name,
                service_id=service_id,
                address=hostname,
                port=grpc_port,
                tags=tags,
                meta={
                    "version": self.service_version,
                    "kind": self.service_kind,
                    "health_port": str(health_port),
                    "metrics_port": str(metrics_port)
                },
                check=consul.Check.http(
                    url=f"http://{hostname}:{health_port}/health",
                    interval="10s"
                )
            )
            self.logger.info(f"Registered with Consul as {service_id}")
        except Exception as e:
            self.logger.error(f"Failed to register with Consul: {e}")
    
    def _initialize_data_client(self):
        """Initialize data client if enabled"""
        data_config = self.config.get('dataClient') or self.config.get('spec', {}).get('dataClient', {})
        
        # Also check manifest dataRequirements
        data_reqs = self.manifest.get('spec', {}).get('dataRequirements', {})
        
        if not data_config.get('enabled', False) and not data_reqs.get('enabled', False):
            self.data_client = None
            self.logger.info("Data client disabled")
            return
        
        aol_core_endpoint = data_config.get('aolCoreEndpoint', 'http://aol-core:8080')
        if not aol_core_endpoint.startswith('http'):
            aol_core_endpoint = f"http://{aol_core_endpoint}"
        
        self.data_client = DatabaseClient(
            aol_core_endpoint=aol_core_endpoint,
            service_name=self.service_name
        )
        
        self.logger.info("Data client initialized")
    
    async def _initialize_collections(self):
        """Initialize collections declared in manifest.yaml"""
        if not self.data_client:
            return
        
        data_reqs = self.manifest.get('spec', {}).get('dataRequirements', {})
        
        if not data_reqs.get('enabled'):
            return
        
        collections = data_reqs.get('collections', [])
        if not collections:
            return
        
        self.logger.info(f"Initializing {len(collections)} collections...")
        initialized_count = 0
        
        for collection_spec in collections:
            collection_name = collection_spec.get('name')
            if not collection_name:
                continue
            
            try:
                collection_id = await self.data_client.request_collection(
                    name=collection_name,
                    schema_hint=collection_spec.get('schemaHint'),
                    indexes=collection_spec.get('indexes')
                )
                self.logger.info(f"✓ Collection '{collection_name}' ready: {collection_id}")
                initialized_count += 1
            except Exception as e:
                self.logger.error(f"✗ Failed to initialize collection '{collection_name}': {e}")
        
        self.logger.info(f"Collection initialization: {initialized_count}/{len(collections)} successful")
    
    @tracer.start_as_current_span("service_process")
    async def Process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request - override this method in your service implementation.
        
        This is the main entry point for service logic. For agents, this might
        be called Think(). For tools, this might be Execute(). For plugins,
        this might be Handle().
        
        Args:
            request: Dictionary containing request data
            
        Returns:
            Dictionary containing response data
        """
        span = trace.get_current_span()
        request_id = request.get('request_id') or request.get('pulse_id', 'unknown')
        span.set_attribute("request.id", request_id)
        
        self.logger.info(f"Processing request {request_id}")
        service_counter.labels(operation='process', status='started').inc()
        active_requests.inc()
        
        try:
            with service_duration.labels(operation='process').time():
                # EXAMPLE: Retrieve historical context from database
                context = []
                if self.data_client:
                    try:
                        recent_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                        recent_data = await self.data_client.query(
                            'events',
                            filters={'timestamp': {'$gte': recent_time}},
                            limit=5,
                            sort={'timestamp': 'desc'}
                        )
                        context = recent_data
                    except Exception as e:
                        self.logger.warning(f"Failed to retrieve context: {e}")
                
                # ============================================
                # IMPLEMENT YOUR SERVICE LOGIC HERE
                # ============================================
                # For Agents: Add reasoning logic
                # For Tools: Add execution logic
                # For Plugins: Add handler logic
                # For Services: Add processing logic
                # ============================================
                
                result = {
                    "service": self.service_name,
                    "kind": self.service_kind,
                    "request_id": request_id,
                    "result": "Template response - implement your logic here",
                    "context_size": len(context),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # EXAMPLE: Store result in database
                if self.data_client:
                    try:
                        doc_id = await self.data_client.insert('events', {
                            'request_id': request_id,
                            'service': self.service_name,
                            'timestamp': datetime.utcnow().isoformat(),
                            'result': result['result']
                        })
                        self.logger.debug(f"Stored result: {doc_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to store result: {e}")
                
                # Publish completion event
                await self._publish_event(
                    topic="task.completed",
                    event_type="TaskCompleted",
                    payload={
                        'request_id': request_id,
                        'service': self.service_name,
                        'success': True
                    }
                )
                
                service_counter.labels(operation='process', status='success').inc()
                return result
                
        except Exception as e:
            service_counter.labels(operation='process', status='error').inc()
            self.logger.error(f"Process error: {e}")
            raise
        finally:
            active_requests.dec()


class AOLServiceApp:
    """Application wrapper for AOL Service with HTTP endpoints"""
    
    def __init__(self):
        self.service = AOLService()
        self.app = web.Application()
        
        # Health endpoints
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/ready', self.ready_handler)
        self.app.router.add_get('/live', self.live_handler)
        
        # Metrics endpoint
        self.app.router.add_get('/metrics', self.metrics_handler)
        
        # API endpoints
        self.app.router.add_post('/api/process', self.process_handler)
        self.app.router.add_post('/api/think', self.process_handler)  # Alias for agents
        self.app.router.add_post('/api/execute', self.process_handler)  # Alias for tools
        
        # Status endpoint
        self.app.router.add_get('/api/status', self.status_handler)
    
    async def health_handler(self, request):
        """Health check endpoint"""
        status = await self.service.health_reporter.health_handler()
        return web.json_response(status)
    
    async def ready_handler(self, request):
        """Readiness probe endpoint"""
        status = await self.service.health_reporter.ready_handler()
        http_status = 200 if status.get('ready') else 503
        return web.json_response(status, status=http_status)
    
    async def live_handler(self, request):
        """Liveness probe endpoint"""
        status = await self.service.health_reporter.live_handler()
        http_status = 200 if status.get('live') else 503
        return web.json_response(status, status=http_status)
    
    async def metrics_handler(self, request):
        """Prometheus metrics endpoint"""
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return web.Response(
            body=generate_latest(),
            content_type=CONTENT_TYPE_LATEST
        )
    
    async def process_handler(self, request):
        """Handle process request"""
        try:
            data = await request.json()
            result = await self.service.Process(data)
            return web.json_response(result)
        except Exception as e:
            self.service.logger.error(f"Process error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def status_handler(self, request):
        """Get service status"""
        return web.json_response({
            'service': self.service.service_name,
            'kind': self.service.service_kind,
            'version': self.service.service_version,
            'health': self.service.health_reporter.get_status(),
            'tools': self.service.tool_registry.get_metrics(),
            'sidecar': self.service.sidecar.get_metrics()
        })
    
    async def start(self):
        """Start the service"""
        self.service.logger.info(f"Starting {self.service.service_name}")
        
        # Start health reporter (runs startup hooks)
        await self.service.health_reporter.start()
        
        # Initialize collections if data client is enabled
        if self.service.data_client:
            try:
                await self.service._initialize_collections()
            except Exception as e:
                self.service.logger.error(f"Failed to initialize collections: {e}")
        
        # Mark service as ready
        await self.service.health_reporter.set_ready()
        
        # Start HTTP server
        endpoints = self.service.manifest.get('spec', {}).get('endpoints', {})
        health_port = int(os.getenv(
            'HEALTH_PORT',
            endpoints.get('health') or self.service.config.get('healthPort', 50200)
        ))
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', health_port)
        await site.start()
        
        self.service.logger.info(f"HTTP server started on port {health_port}")
        self.service.logger.info(f"{self.service.service_name} is running")
        
        # Keep running
        await asyncio.Event().wait()


if __name__ == '__main__':
    import signal
    
    app = AOLServiceApp()
    
    def signal_handler(sig, frame):
        async def shutdown():
            hostname = socket.gethostname()
            service_name = app.service.service_name
            
            try:
                # Stop health reporter (runs shutdown hooks)
                await app.service.health_reporter.stop()
                
                # Deregister from Consul
                app.service.consul_client.agent.service.deregister(f"{service_name}-{hostname}")
                
            except Exception as e:
                logging.error(f"Error during shutdown: {e}")
            
            logging.info(f"Shutting down {service_name}")
        
        asyncio.run(shutdown())
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        signal_handler(None, None)
