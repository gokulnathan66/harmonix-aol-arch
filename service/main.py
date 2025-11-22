"""AOL Service Template - Self-contained service with direct Consul registration"""
import asyncio
import os
import sys
import yaml
import logging
import socket
from aiohttp import web
from opentelemetry import trace
from prometheus_client import Counter, Histogram

from utils.tracing import setup_tracing
from utils.logging import setup_logging
from utils.db_client import DatabaseClient
from utils.consul_client import AOLServiceDiscoveryClient
import consul

tracer = trace.get_tracer(__name__)

# Metrics
service_counter = Counter('service_operations_total', 'Total service operations')
service_duration = Histogram('service_operation_duration_seconds', 'Operation duration')

class AOLService:
    """Template AOL Service with self-contained utilities
    
    This base class can be used for:
    - AI Agents (reasoning, analysis, decision-making)
    - Tools (external API integrations, utilities)
    - Plugins (extensible functionality)
    - Services (any AOL-compliant microservice)
    """
    
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.logger = setup_logging({
            'spec': {
                'logging': {
                    'level': self.config.get('monitoring', {}).get('logLevel', 'INFO'),
                    'format': 'json'
                }
            }
        })
        
        # Setup tracing
        service_name = self.config.get('metadata', {}).get('name') or self.config.get('spec', {}).get('name') or self.config.get('name', 'aol-service')
        setup_tracing({
            'metadata': {'name': service_name, 'version': '1.0.0'},
            'spec': {
                'monitoring': {
                    'tracingEnabled': self.config.get('monitoring', {}).get('tracingEnabled', False),
                    'tracingEndpoint': os.getenv('JAEGER_ENDPOINT', None)
                }
            }
        })
        
        # Initialize Consul client for registration (direct Consul access for registration)
        consul_host = os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[0]
        consul_port = int(os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[1] if ':' in os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500') else 8500)
        self.consul_client = consul.Consul(host=consul_host, port=consul_port)
        
        # Initialize aol-core service discovery client (for discovering other services)
        aol_core_endpoint = os.getenv('AOL_CORE_ENDPOINT', 'http://aol-core:8080')
        self.discovery_client = AOLServiceDiscoveryClient(aol_core_endpoint)
        
        # Register with Consul
        self._register_self()
        
        # Initialize data client if enabled
        self.data_client = None
        self._initialize_data_client()
    
    def _register_self(self):
        """Register service with Consul directly"""
        hostname = socket.gethostname()
        service_name = self.config.get('metadata', {}).get('name') or self.config.get('spec', {}).get('name') or self.config.get('name', 'aol-service')
        service_id = f"{service_name}-{hostname}"
        
        # Get ports from config (support multiple config formats)
        endpoints = self.config.get('spec', {}).get('endpoints', {})
        grpc_port = int(endpoints.get('grpc') or self.config.get('spec', {}).get('grpcPort') or self.config.get('grpcPort', 50050))
        health_port = int(endpoints.get('health') or self.config.get('spec', {}).get('healthPort') or self.config.get('healthPort', 50200))
        metrics_port = int(endpoints.get('metrics') or self.config.get('spec', {}).get('metricsPort') or self.config.get('metricsPort', 8080))
        
        # Get service type from manifest or config
        service_type = self.config.get('kind', 'AOLService').lower()
        tags = self.config.get('spec', {}).get('tags', []) or self.config.get('metadata', {}).get('labels', {}).values() or [service_type]
        if isinstance(tags, dict):
            tags = list(tags.values())
        
        try:
            self.consul_client.agent.service.register(
                name=service_name,
                service_id=service_id,
                address=hostname,
                port=grpc_port,
                tags=tags if isinstance(tags, list) else [tags],
                meta={
                    "version": self.config.get('metadata', {}).get('version') or self.config.get('version', '1.0.0'),
                    "kind": self.config.get('kind', 'AOLService'),
                    "health_port": str(health_port),
                    "metrics_port": str(metrics_port)
                },
                check=consul.Check.http(
                    url=f"http://{hostname}:{health_port}/health",
                    interval="10s"
                )
            )
            self.logger.info(f"Registered with Consul as {service_id} (type: {service_type})")
        except Exception as e:
            self.logger.error(f"Failed to register with Consul: {e}")
    
    def _initialize_data_client(self):
        """Initialize data client if enabled"""
        # Support both flat and nested config structures
        data_config = self.config.get('dataClient') or self.config.get('spec', {}).get('dataClient', {})
        
        if not data_config.get('enabled', False):
            self.data_client = None
            self.logger.info("Data client disabled")
            return
        
        # Initialize client (uses aol-core for discovery)
        service_name = self.config.get('metadata', {}).get('name') or self.config.get('spec', {}).get('name') or self.config.get('name', 'aol-service')
        aol_core_endpoint = data_config.get('aolCoreEndpoint', 'http://aol-core:8080')
        if not aol_core_endpoint.startswith('http'):
            aol_core_endpoint = f"http://{aol_core_endpoint}"
        self.data_client = DatabaseClient(
            aol_core_endpoint=aol_core_endpoint,
            service_name=service_name
        )
        
        self.logger.info("Data client initialized")
    
    async def _initialize_collections(self):
        """Initialize collections declared in manifest.yaml"""
        if not self.data_client:
            return
        
        # Load manifest to get dataRequirements
        manifest_path = os.path.join(os.path.dirname(__file__), '..', 'manifest.yaml')
        if not os.path.exists(manifest_path):
            self.logger.warning("manifest.yaml not found, skipping collection initialization")
            return
        
        with open(manifest_path, 'r') as f:
            manifest = yaml.safe_load(f)
        
        data_reqs = manifest.get('spec', {}).get('dataRequirements', {})
        
        if not data_reqs.get('enabled'):
            return
        
        # Request each collection
        collections = data_reqs.get('collections', [])
        if not collections:
            self.logger.warning("No collections defined in manifest dataRequirements")
            return
        
        self.logger.info(f"Initializing {len(collections)} collections...")
        initialized_count = 0
        
        for collection_spec in collections:
            collection_name = collection_spec.get('name')
            if not collection_name:
                self.logger.warning("Collection spec missing 'name' field, skipping")
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
        
        self.logger.info(f"Collection initialization complete: {initialized_count}/{len(collections)} successful")
    
    @tracer.start_as_current_span("service_process")
    async def Process(self, request):
        """Process a request - override this method in your service implementation
        
        This is the main entry point for service logic. For agents, this might be
        called Think(). For tools, this might be Execute(). For plugins, this
        might be Handle().
        
        Args:
            request: Dictionary containing request data
            
        Returns:
            Dictionary containing response data
        """
        span = trace.get_current_span()
        request_id = request.get('request_id') or request.get('pulse_id', 'unknown')
        span.set_attribute("request.id", request_id)
        
        service_name = self.config.get('metadata', {}).get('name') or self.config.get('spec', {}).get('name') or self.config.get('name', 'aol-service')
        self.logger.info(f"Service {service_name} processing request {request_id}")
        service_counter.inc()
        
        with service_duration.time():
            # EXAMPLE: Retrieve historical context from database
            context = []
            if self.data_client:
                try:
                    from datetime import datetime, timedelta
                    recent_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                    
                    # Query recent data for context (adjust collection name as needed)
                    recent_data = await self.data_client.query(
                        'events',  # Adjust collection name based on your service
                        filters={'timestamp': {'$gte': recent_time}},
                        limit=5,
                        sort={'timestamp': 'desc'}
                    )
                    context = recent_data
                    self.logger.debug(f"Retrieved {len(context)} recent records for context")
                except Exception as e:
                    self.logger.warning(f"Failed to retrieve historical context: {e}")
                    context = []
            
            # Implement your service logic here
            result = {
                "service": service_name,
                "request_id": request_id,
                "result": "Template response - implement your logic here",
                "context_size": len(context)
            }
            
            # EXAMPLE: Store result in database
            if self.data_client:
                try:
                    from datetime import datetime
                    doc_id = await self.data_client.insert('events', {
                        'request_id': request_id,
                        'service': service_name,
                        'timestamp': datetime.utcnow().isoformat(),
                        'result': result['result'],
                        'context_size': len(context)
                    })
                    self.logger.debug(f"Stored result in database: {doc_id}")
                except Exception as e:
                    self.logger.error(f"Failed to store result: {e}")
                    # Continue execution - storage failure shouldn't break service operation
            
            self.logger.info(f"Service {service_name} processing complete for request {request_id}")
            return result

class AOLServiceApp:
    """Application wrapper for AOL Service"""
    
    def __init__(self):
        self.service = AOLService()
        self.app = web.Application()
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/metrics', self.metrics_handler)
        self.app.router.add_post('/api/process', self.process_handler)
        # For backward compatibility with agent template
        self.app.router.add_post('/api/think', self.process_handler)
    
    async def health_handler(self, request):
        """Health check endpoint"""
        service_name = self.service.config.get('metadata', {}).get('name') or self.service.config.get('spec', {}).get('name') or self.service.config.get('name', 'aol-service')
        return web.json_response({
            'status': 'healthy',
            'service': service_name,
            'kind': self.service.config.get('kind', 'AOLService')
        })
    
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
    
    async def start(self):
        """Start the service"""
        service_name = self.service.config.get('metadata', {}).get('name') or self.service.config.get('spec', {}).get('name') or self.service.config.get('name', 'AOL Service')
        self.service.logger.info(f"Starting {service_name}")
        
        # Initialize collections if data client is enabled
        if self.service.data_client:
            try:
                await self.service._initialize_collections()
            except Exception as e:
                self.service.logger.error(f"Failed to initialize collections: {e}")
        
        endpoints = self.service.config.get('spec', {}).get('endpoints', {})
        health_port = int(os.getenv('HEALTH_PORT', endpoints.get('health') or self.service.config.get('healthPort', 50200)))
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', health_port)
        await site.start()
        self.service.logger.info(f"HTTP server started on port {health_port}")
        
        # Keep running
        await asyncio.Event().wait()

if __name__ == '__main__':
    import signal
    
    app = AOLServiceApp()
    
    def signal_handler(sig, frame):
        async def shutdown():
            hostname = socket.gethostname()
            service_name = app.service.config.get('metadata', {}).get('name') or app.service.config.get('spec', {}).get('name') or app.service.config.get('name', 'aol-service')
            try:
                app.service.consul_client.agent.service.deregister(f"{service_name}-{hostname}")
            except Exception as e:
                logging.error(f"Error deregistering from Consul: {e}")
            if app.service.data_client:
                await app.service.data_client.close()
            if app.service.discovery_client:
                await app.service.discovery_client.close()
            logging.info(f"Shutting down {service_name}")
        
        asyncio.run(shutdown())
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        signal_handler(None, None)

