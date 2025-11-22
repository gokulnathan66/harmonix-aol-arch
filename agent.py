"""AOL Agent Template - Consul-based service discovery"""
import asyncio
import os
import sys
import yaml
import logging
import socket
from aiohttp import web
from opentelemetry import trace
from prometheus_client import Counter, Histogram

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'aol-core'))

from shared.utils.tracing import setup_tracing
from shared.utils.logging import setup_logging
from registry.consul_registry import ConsulServiceRegistry, ServiceInstance as ConsulServiceInstance

tracer = trace.get_tracer(__name__)

# Metrics
agent_counter = Counter('agent_operations_total', 'Total agent operations')
agent_duration = Histogram('agent_operation_duration_seconds', 'Operation duration')

class AOLAgent:
    """Template AOL Agent with Consul integration"""
    
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
        setup_tracing({
            'metadata': {'name': self.config.get('name', 'aol-agent'), 'version': '1.0.0'},
            'spec': {
                'monitoring': {
                    'tracingEnabled': self.config.get('monitoring', {}).get('tracingEnabled', True),
                    'tracingEndpoint': os.getenv('JAEGER_ENDPOINT', 'jaeger:4317')
                }
            }
        })
        
        # Initialize Consul registry
        self.consul_registry = ConsulServiceRegistry(
            consul_host=os.getenv('CONSUL_HTTP_ADDR', 'consul-server').split(':')[0],
            consul_port=int(os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[1] if ':' in os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500') else 8500)
        )
        
        # Register with Consul
        self._register_self()
        
        # Initialize data client if enabled
        self.data_client = None
        self._initialize_data_client()
    
    def _register_self(self):
        """Register agent with Consul"""
        hostname = socket.gethostname()
        agent_name = self.config.get('name', 'aol-agent')
        
        instance = ConsulServiceInstance(
            id=f"{agent_name}-{hostname}",
            name=agent_name,
            address=hostname,
            port=int(self.config.get('grpcPort', 50050)),
            health_port=int(self.config.get('healthPort', 50200)),
            metrics_port=int(self.config.get('metricsPort', 8080)),
            tags=self.config.get('tags', ['agent']),
            meta={
                "version": self.config.get('version', '1.0.0'),
                "health_port": str(self.config.get('healthPort', 50200)),
                "metrics_port": str(self.config.get('metricsPort', 8080))
            }
        )
        
        self.consul_registry.register_service(instance)
    
    def _initialize_data_client(self):
        """Initialize data client if enabled"""
        # Support both flat and nested config structures
        data_config = self.config.get('dataClient') or self.config.get('spec', {}).get('dataClient', {})
        
        if not data_config.get('enabled', False):
            self.data_client = None
            self.logger.info("Data client disabled")
            return
        
        try:
            # Import data client
            from shared.utils.data_client import AOLDataClient
            
            # Get service name from config
            service_name = self.config.get('metadata', {}).get('name') or self.config.get('name', 'aol-agent')
            
            # Initialize client
            self.data_client = AOLDataClient(
                aol_core_endpoint=data_config.get('aolCoreEndpoint', 'aol-core:50051'),
                service_name=service_name
            )
            
            self.logger.info(f"Data client initialized for service '{service_name}'")
        except Exception as e:
            self.logger.error(f"Failed to initialize data client: {e}")
            self.data_client = None
            raise
    
    async def _initialize_collections(self):
        """Initialize collections declared in manifest.yaml"""
        if not self.data_client:
            self.logger.debug("Skipping collection initialization - data client not enabled")
            return
        
        # Load manifest to get dataRequirements
        manifest_path = os.path.join(os.path.dirname(__file__), 'manifest.yaml')
        if not os.path.exists(manifest_path):
            self.logger.warning("manifest.yaml not found, skipping collection initialization")
            return
        
        try:
            import yaml
            with open(manifest_path, 'r') as f:
                manifest = yaml.safe_load(f)
            
            data_reqs = manifest.get('spec', {}).get('dataRequirements', {})
            
            if not data_reqs.get('enabled'):
                self.logger.debug("Data requirements not enabled in manifest")
                return
            
            collections = data_reqs.get('collections', [])
            if not collections:
                self.logger.warning("No collections defined in manifest dataRequirements")
                return
            
            self.logger.info(f"Initializing {len(collections)} collections...")
            
            # Request each collection
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
            
        except Exception as e:
            self.logger.error(f"Error during collection initialization: {e}")

    
    @tracer.start_as_current_span("agent_think")
    async def Think(self, request):
        """Process a request and generate response"""
        span = trace.get_current_span()
        pulse_id = request.get('pulse_id', 'unknown')
        span.set_attribute("pulse.id", pulse_id)
        
        self.logger.info(f"Agent thinking on pulse {pulse_id}")
        agent_counter.inc()
        
        with agent_duration.time():
            # EXAMPLE: Retrieve historical context from database
            context = []
            if self.data_client:
                try:
                    from datetime import datetime, timedelta
                    recent_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                    
                    # Query recent thoughts for context
                    recent_thoughts = await self.data_client.query(
                        'thoughts',
                        filters={'timestamp': {'$gte': recent_time}},
                        limit=5,
                        sort={'timestamp': 'desc'}
                    )
                    context = recent_thoughts
                    self.logger.debug(f"Retrieved {len(context)} recent thoughts for context")
                except Exception as e:
                    self.logger.warning(f"Failed to retrieve historical context: {e}")
                    context = []  # Graceful degradation
            
            # Implement your agent logic here
            result = {
                "agent": self.config.get('name', 'aol-agent'),
                "pulse_id": pulse_id,
                "result": "Template response",
                "context_size": len(context)
            }
            
            # EXAMPLE: Store thought in database
            if self.data_client:
                try:
                    from datetime import datetime
                    service_name = self.config.get('metadata', {}).get('name') or self.config.get('name', 'aol-agent')
                    
                    doc_id = await self.data_client.insert('thoughts', {
                        'thought_id': f"{pulse_id}-{service_name}",
                        'pulse_id': pulse_id,
                        'timestamp': datetime.utcnow().isoformat(),
                        'analysis': result['result'],
                        'confidence': 0.8,
                        'context_size': len(context)
                    })
                    self.logger.debug(f"Stored thought in database: {doc_id}")
                except Exception as e:
                    self.logger.error(f"Failed to store thought: {e}")
                    # Continue execution - storage failure shouldn't break agent operation
            
            return result
    
    def _get_recent_timestamp(self, hours=1):
        """Get timestamp for recent data (default: last 1 hour)"""
        from datetime import datetime, timedelta
        recent = datetime.utcnow() - timedelta(hours=hours)
        return recent.isoformat()

class AOLAgentApp:
    def __init__(self):
        self.agent = AOLAgent()
        self.app = web.Application()
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_post('/api/think', self.think_handler)
    
    async def health_handler(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'agent': self.agent.config.get('name', 'aol-agent')
        })
    
    async def think_handler(self, request):
        """Handle think request"""
        try:
            data = await request.json()
            result = await self.agent.Think(data)
            return web.json_response(result)
        except Exception as e:
            self.agent.logger.error(f"Think error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def start(self):
        """Start the agent"""
        self.agent.logger.info(f"Starting {self.agent.config.get('name', 'AOL Agent')}")
        
        # Initialize collections if data client is enabled
        if self.agent.data_client:
            try:
                await self.agent._initialize_collections()
            except Exception as e:
                self.agent.logger.error(f"Failed to initialize collections: {e}")
        
        health_port = int(os.getenv('HEALTH_PORT', self.agent.config.get('healthPort', 50200)))
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', health_port)
        await site.start()
        self.agent.logger.info(f"HTTP server started on port {health_port}")
        
        # Keep running
        await asyncio.Event().wait()

if __name__ == '__main__':
    import signal
    
    app = AOLAgentApp()
    
    def signal_handler(sig, frame):
        hostname = socket.gethostname()
        agent_name = app.agent.config.get('name', 'aol-agent')
        app.agent.consul_registry.deregister_service(f"{agent_name}-{hostname}")
        logging.info(f"Shutting down {agent_name}")
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        signal_handler(None, None)

