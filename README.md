# g2-aol-template 

Complete template for creating AOL-compliant services in the Pulse-AI multi-agent system architecture.

## 🎯 What This Template Is For

This template is **service-agnostic** and can be used to create:

- **AI Agents** - Reasoning, analysis, and decision-making services
- **Tools** - External API integrations, utilities, and helper services  
- **Plugins** - Extensible functionality modules
- **Services** - Any AOL-compliant microservice

All service types follow the same structure and patterns, making it easy to build a complete multi-agent system.

## 🆕 Architecture Update (2025)

The template has been updated to match the **new self-contained architecture**:

- ✅ **Self-contained utilities** - Each service has its own `utils/` folder (no shared dependencies)
- ✅ **Direct Consul registration** - Services register directly with Consul
- ✅ **aol-core discovery** - Services discover other services via aol-core API
- ✅ **Proper folder structure** - `service/`, `utils/`, `proto/`, `sidecar/` folders
- ✅ **Complete independence** - Each service is fully self-contained
- ✅ **Service-agnostic** - Works for agents, tools, plugins, and general services

## Architecture Overview

This template follows the **loosely coupled microservices architecture** designed for **multi-agent systems** where each service is completely independent:

- **Self-contained**: Each service has its own `utils/` folder with all utilities
- **Direct registration**: Services register directly with Consul on startup
- **Centralized discovery**: Services discover other services via aol-core's Service Discovery API
- **No shared files**: All utilities are duplicated in each service for complete independence
- **Multi-agent ready**: Supports agents, tools, plugins, and services working together

### Service Registration & Discovery Pattern

**Important**: This pattern is the SAME for ALL services (agents, tools, plugins, services):

1. **Register WITH Consul** (Direct)
   - Each service registers itself with Consul using `consul.Consul()` client
   - Consul is the central service registry
   - Environment variable: `CONSUL_HTTP_ADDR` (default: `consul-server:8500`)

2. **Discover OTHER services VIA aol-core** (Indirect)
   - aol-core reads from Consul and provides discovery API
   - **aol-core is the SAME instance for everyone** - it manages all services
   - Services use `AOLServiceDiscoveryClient` to query aol-core
   - Environment variable: `AOL_CORE_ENDPOINT` (default: `http://aol-core:8080`)

3. **aol-core Management**
   - aol-core is the central management service
   - It discovers services from Consul
   - It provides service discovery API (`/api/discovery/{service_name}`)
   - It manages routing, health checks, metrics, and data access
   - **Every service uses the same aol-core instance**

**Example Flow:**
```
Your Service → Registers with Consul → aol-core reads Consul → Other services query aol-core
```

### Multi-Agent System Context

This template is designed for building **AI multi-agent systems** that require:

- **Agent Orchestration** - AOL Core coordinates agents, tools, and plugins
- **Service Discovery** - Agents find and communicate with each other
- **Data Sharing** - Agents share knowledge and context through collections
- **Monitoring & Observability** - Track agent actions, health, and workflows
- **Tool Integration** - Agents access external APIs and specialized tools
- **Memory & Knowledge** - Persistent storage for agent context and learning

See `docs/multi-agent system-need.md` for more details on multi-agent system requirements.

## Template Structure

```
g2-aol-template/
├── service/                  # Service implementation
│   ├── __init__.py
│   └── main.py              # Main service implementation (Process method)
├── utils/                    # Self-contained utilities
│   ├── __init__.py
│   ├── consul_client.py     # Service discovery via aol-core
│   ├── db_client.py         # Database client
│   ├── grpc_client.py       # gRPC client with load balancing
│   ├── logging.py           # Structured logging
│   └── tracing.py           # OpenTelemetry tracing
├── proto/                    # Protocol buffer definitions
│   ├── common.proto
│   ├── health.proto
│   ├── metrics.proto
│   └── service.proto        # Your service-specific proto
├── sidecar/                  # Sidecar components
│   ├── __init__.py
│   ├── health.py
│   └── sidecar.py
├── examples/                 # Example implementations
│   ├── simple_storage_example.py
│   └── shared_collection_example.py
├── docs/                     # Documentation
│   ├── AOL-About.md
│   ├── AOL-components.md
│   ├── data_patterns.md
│   └── ...
├── config.yaml              # Runtime configuration
├── manifest.yaml            # Service manifest (supports Agent/Tool/Plugin/Service)
├── manifest-with-data.yaml  # Manifest with data storage enabled
├── Dockerfile               # Container definition
├── requirements.txt         # Python dependencies
├── create-service.sh        # Service creation script
└── README.md                # This file
```

## Quick Start

### Option A: Automated Setup (Recommended)

Use the interactive setup script:

```bash
cd g2-aol-template
./create-service.sh my-new-service [ServiceType]
```

**Service Types:**
- `Agent` - AI reasoning and decision-making service
- `Tool` - External API integration or utility service
- `Plugin` - Extensible functionality module
- `Service` - General microservice (default)

**Example:**
```bash
./create-service.sh text-analyzer Agent
./create-service.sh web-scraper Tool
./create-service.sh auth-plugin Plugin
./create-service.sh api-gateway Service
```

The script will:
- ✅ Create service directory in `app/my-new-service/`
- ✅ Copy all template files
- ✅ Set service type (kind) in manifest.yaml
- ✅ Ask if you need data storage
- ✅ Prompt for port numbers
- ✅ Customize manifest and config
- ✅ Provide next steps and docker-compose snippet

**That's it!** Your service is ready to implement.

---

### Option B: Manual Setup

#### 1. Copy Template Files

```bash
# Create your new service
mkdir -p app/my-service
cp -r g2-aol-template/* app/my-service/
cd app/my-service
```

#### 2. Customize Manifest

Edit `manifest.yaml` (or use `manifest-with-data.yaml` if you need storage):

```yaml
kind: "AOLService"  # Options: AOLAgent, AOLTool, AOLPlugin, AOLService
apiVersion: "v1"
metadata:
  name: "my-service"  # Change this
  version: "1.0.0"
  labels:
    service-type: "custom"
    role: "service"

spec:
  endpoints:
    grpc: "50070"     # Pick unused port
    sidecar: "50120"
    health: "50220"
    metrics: "8095"
```

#### 3. Configure Runtime

Edit `config.yaml`:

```yaml
# Data client configuration (if needed)
dataClient:
  enabled: false
  aolCoreEndpoint: "aol-core:50051"

monitoring:
  tracingEnabled: false
  metricsEnabled: true
  logLevel: "INFO"
```

#### 4. Implement Logic

Edit `service/main.py` and implement your service logic in the `Process` method:

```python
async def Process(self, request):
    """Override this method with your service logic"""
    # For Agents: Implement reasoning/analysis logic
    # For Tools: Implement execution logic
    # For Plugins: Implement handling logic
    # For Services: Implement processing logic
    
    result = {
        "service": self.config.get('name'),
        "request_id": request.get('request_id'),
        "result": "Your logic here"
    }
    return result
```

#### 5. Add to Docker Compose

Add your service to `app/docker-compose.yml`:

```yaml
my-service:
  build:
    context: .
    dockerfile: ./my-service/Dockerfile
  container_name: my-service
  hostname: my-service
  ports:
    - "50070:50070"
    - "50220:50220"
    - "8095:8095"
  networks:
    - heart-pulse-network
  depends_on:
    - consul-server
    - aol-core
  environment:
    - CONSUL_HTTP_ADDR=consul-server:8500
    - AOL_CORE_ENDPOINT=http://aol-core:8080
    - HEALTH_PORT=50220
```

## Data Storage Integration

If your service needs to store data:

### 1. Declare Data Requirements

Use `manifest-with-data.yaml` as reference and add to `manifest.yaml`:

```yaml
spec:
  dataRequirements:
    enabled: true
    collections:
      - name: "my_data"
        schemaHint:
          timestamp: "datetime"
          value: "number"
        indexes:
          - fields: ["timestamp"]
            type: "ascending"
```

### 2. Enable Data Client

In `config.yaml`:

```yaml
dataClient:
  enabled: true
  aolCoreEndpoint: "aol-core:50051"
```

### 3. Use Data Client

The template `service/main.py` already includes data client usage:

```python
# In your Process method:
async def Process(self, request):
    # Store data
    if self.data_client:
        await self.data_client.insert('my_data', {
            'timestamp': datetime.utcnow().isoformat(),
            'value': 123
        })
    
    # Query data
    if self.data_client:
        results = await self.data_client.query(
            'my_data',
            filters={'value': {'$gt': 100}},
            limit=10
        )
```

## Key Architectural Patterns

### Service Discovery

**Registration**: Services register directly with Consul (same for all services):
```python
# Register WITH Consul directly
consul_host = os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[0]
consul_port = int(os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[1])
self.consul_client = consul.Consul(host=consul_host, port=consul_port)
self.consul_client.agent.service.register(...)
```

**Discovery**: Services discover OTHER services via aol-core (aol-core is same for everyone):
```python
# Discover OTHER services VIA aol-core
# aol-core reads from Consul and provides discovery API
aol_core_endpoint = os.getenv('AOL_CORE_ENDPOINT', 'http://aol-core:8080')
self.discovery_client = AOLServiceDiscoveryClient(aol_core_endpoint)
instances = await self.discovery_client.discover_service('service-name')
```

**Key Points:**
- ✅ All services register with Consul directly
- ✅ All services discover other services via aol-core
- ✅ aol-core is the SAME instance for everyone
- ✅ aol-core manages all services by reading from Consul

### Self-Contained Utilities

Each service has its own `utils/` folder with:
- `consul_client.py` - Service discovery client
- `db_client.py` - Database operations
- `grpc_client.py` - gRPC with load balancing
- `logging.py` - Structured logging
- `tracing.py` - OpenTelemetry tracing

### Health Checks

Services expose HTTP health endpoints:
```python
@app.router.add_get('/health', self.health_handler)
```

Consul monitors these endpoints automatically.

## Best Practices

### Port Allocation
- **gRPC:** 50051-50099
- **Sidecar:** 50100-50199
- **Health:** 50200-50299
- **Metrics:** 8080-8099

### Service Naming
- Use lowercase with hyphens: `my-service`
- Be descriptive: `text-analyzer` not `service1`
- Include type hint if helpful: `text-analyzer-agent`, `web-scraper-tool`

### Service Types
Choose the appropriate `kind` in `manifest.yaml`:
- **AOLAgent** - AI reasoning, analysis, decision-making
- **AOLTool** - External integrations, utilities, helpers
- **AOLPlugin** - Extensible modules, add-ons
- **AOLService** - General microservices

### Dependencies
Always declare in `manifest.yaml`:
```yaml
dependencies:
  - service: "aol-core"
    optional: false
  - service: "knowledge-db"  # If using data storage
    optional: false
```

### Health Checks
Implement `/health` endpoint returning:
```json
{
  "status": "healthy",
  "service": "my-service"
}
```

## Testing Your Service

### 1. Build
```bash
cd app
docker-compose build my-service
```

### 2. Start
```bash
docker-compose up -d consul-server aol-core my-service
```

### 3. Verify
```bash
# Check health
curl http://localhost:50220/health

# Check Consul registration
curl http://localhost:8500/v1/catalog/service/my-service

# Check metrics
curl http://localhost:8095/metrics

# Check service discovery via aol-core
curl http://localhost:8080/api/discovery/my-service
```

## Service Types Explained

### AOLAgent
AI reasoning services that process information, make decisions, and generate responses.
- **Use cases**: Text analysis, decision-making, reasoning, critique
- **Example**: `critic-agent`, `synthesizer-agent`, `validator-agent`
- **Method**: Override `Process()` to implement `Think()` logic

### AOLTool
External integrations and utilities that provide specific functionality.
- **Use cases**: API wrappers, data processors, external service integrations
- **Example**: `web-scraper-tool`, `database-tool`, `email-tool`
- **Method**: Override `Process()` to implement `Execute()` logic

### AOLPlugin
Extensible modules that add functionality to the system.
- **Use cases**: Add-ons, extensions, optional features
- **Example**: `auth-plugin`, `cache-plugin`, `analytics-plugin`
- **Method**: Override `Process()` to implement `Handle()` logic

### AOLService
General microservices that don't fit the above categories.
- **Use cases**: API gateways, data processors, background workers
- **Example**: `api-gateway`, `event-processor`, `scheduler-service`
- **Method**: Override `Process()` to implement your logic

## Infrastructure Components

This template includes infrastructure components in `infrastructure/`:

- **[aol-core](infrastructure/aol-core/)** - Central orchestration service (required)
- **[consul](infrastructure/consul/)** - Service registry configuration (required)

See [infrastructure/README.md](infrastructure/README.md) for setup instructions.

## Documentation

- **[Architecture Pattern](docs/ARCHITECTURE.md)**: How services register with Consul and discover via aol-core (same for all services)
- **[Infrastructure Setup](infrastructure/README.md)**: How to set up aol-core and Consul
- [Multi-Agent System Needs](docs/multi-agent%20system-need.md): Requirements for AI multi-agent systems
- [AOL Components](docs/AOL-components.md): Detailed breakdown of system components
- [Data Patterns](docs/data_patterns.md): Guide to using the Data Client and storage patterns
- [Best Practices](docs/BEST_PRACTICES.md): Production-ready patterns and troubleshooting
- [Logging Setup](docs/LOGGING.md): Guide to centralized logging with ELK and Filebeat
- See examples in `examples/` directory

## Support

For issues or questions:
1. Check [`AOL-components.md`](AOL-components.md) requirements
2. Review example implementations in `app/agents/`
3. Verify `manifest.yaml` follows schema
4. Check Consul UI for service registration: http://localhost:8500
