# harmonix-aol-arch 

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: flake8](https://img.shields.io/badge/code%20style-flake8-000000.svg)](https://github.com/PyCQA/flake8)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security Policy](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)

Complete template for creating AOL-compliant services in the multi-agent system architecture.

> **Note**: This project is open source and welcomes contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🎯 What This Template Is For

This template is **service-agnostic** and can be used to create:

- **AI Agents** - Reasoning, analysis, and decision-making services
- **Tools** - External API integrations, utilities, and helper services  
- **Plugins** - Extensible functionality modules
- **Services** - Any AOL-compliant microservice

All service types follow the same structure and patterns, making it easy to build a complete multi-agent system.

## 🆕 Architecture Update (2025)

The template implements the **comprehensive AOL service configuration** for multi-agent collaboration:

- ✅ **Service Registration & Discovery** - Consul-based auto-registration with aol-core discovery
- ✅ **Communication Interfaces** - gRPC/HTTP with health checks and structured messaging
- ✅ **Data Brokering** - Namespace-isolated collections via brokered client
- ✅ **Integration Hooks** - Tool dependencies, LLM adapters, and pluggable APIs
- ✅ **Loose Coupling Enablers** - Event-driven pub-sub and circuit breakers
- ✅ **Lifecycle Management** - Heartbeats, hooks, and graceful shutdown
- ✅ **Observability** - Metrics, tracing, and structured logging

## Architecture Overview

This template follows the **loosely coupled microservices architecture** designed for **multi-agent systems**:

```
                    ┌─────────────────────────────────────────────┐
                    │              AOL-Core                       │
                    │  (Central Orchestration & Discovery)        │
                    │                                             │
                    │  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
                    │  │Discovery│  │EventBus │  │ Router  │    │
                    │  │   API   │  │ (PubSub)│  │ (gRPC)  │    │
                    │  └────┬────┘  └────┬────┘  └────┬────┘    │
                    └───────┼────────────┼───────────┼──────────┘
                            │            │           │
          ┌─────────────────┼────────────┼───────────┼─────────────────┐
          │                 │            │           │                 │
    ┌─────▼─────┐     ┌─────▼─────┐ ┌────▼────┐ ┌────▼────┐     ┌──────▼─────┐
    │  Agent 1  │     │  Agent 2  │ │  Tool 1 │ │  Tool 2 │     │  Plugin 1  │
    │(AOLAgent) │     │(AOLAgent) │ │(AOLTool)│ │(AOLTool)│     │(AOLPlugin) │
    └───────────┘     └───────────┘ └─────────┘ └─────────┘     └────────────┘
          │                 │            │           │                 │
          └─────────────────┴────────────┴───────────┴─────────────────┘
                                         │
                                   ┌─────▼─────┐
                                   │  Consul   │
                                   │ (Registry)│
                                   └───────────┘
```

### Key Patterns

1. **Register WITH Consul** (Direct) - All services register themselves
2. **Discover VIA aol-core** (Indirect) - Services find each other through aol-core
3. **Communicate via Events** (Loose Coupling) - Pub-sub messaging through event bus
4. **Store via Brokered Client** (Isolation) - Namespaced data access

## Template Structure

```
harmonix-aol-arch/
├── service/                  # Service implementation
│   ├── __init__.py
│   └── main.py              # Main service with lifecycle hooks
├── utils/                    # Self-contained utilities
│   ├── __init__.py
│   ├── consul_client.py     # Service discovery via aol-core
│   ├── db_client.py         # Brokered database client
│   ├── grpc_client.py       # gRPC client with circuit breakers
│   ├── event_bus.py         # Async pub-sub messaging
│   ├── validators.py        # Schema and manifest validation
│   ├── logging.py           # Structured logging
│   └── tracing.py           # OpenTelemetry tracing
├── sidecar/                  # Sidecar components
│   ├── __init__.py
│   ├── health.py            # Health reporter with heartbeats
│   └── sidecar.py           # Tool executor & protocol translation
├── integration/              # External integrations
│   ├── __init__.py
│   ├── base.py              # Base integration classes
│   ├── llm_adapter.py       # LLM provider adapters
│   └── tool_registry.py     # Dynamic tool registry
├── proto/                    # Protocol buffer definitions
│   ├── common.proto
│   ├── health.proto
│   ├── metrics.proto
│   └── service.proto
├── examples/                 # Example implementations
│   ├── simple_storage_example.py
│   └── shared_collection_example.py
├── docs/                     # Documentation
├── config.yaml              # Unified runtime configuration (all features)
├── manifest.yaml            # Unified service manifest (all features)
├── Dockerfile               # Container definition
├── requirements.txt         # Python dependencies
├── create-service.sh        # Service creation script
└── README.md                # This file
```

## Quick Start

### Option A: Automated Setup (Recommended)

```bash
cd harmonix-aol-arch
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
- ✅ Create service directory
- ✅ Copy template files including integration module
- ✅ Ask about data storage, integrations, and pub-sub needs
- ✅ Configure ports and service identity
- ✅ Validate the generated manifest
- ✅ Provide docker-compose snippet

### Option B: Manual Setup

#### 1. Copy Template
```bash
mkdir -p app/my-service
cp -r harmonix-aol-arch/* app/my-service/
cd app/my-service
```

#### 2. Customize Manifest
```yaml
kind: "AOLService"  # Options: AOLAgent, AOLTool, AOLPlugin, AOLService
apiVersion: "v1"
metadata:
  name: "my-service"
  version: "1.0.0"
  labels:
    role: "service"

spec:
  endpoints:
    grpc: "50070"
    health: "50220"
    metrics: "8095"
  
  dependencies:
    - service: "aol-core"
      optional: false
  
  # Enable data storage if needed (set enabled: true)
  dataRequirements:
    enabled: false
  
  # Enable integrations if needed (set enabled: true)
  integrations:
    enabled: false
```

#### 3. Implement Logic
```python
# service/main.py
async def Process(self, request):
    """Override this method with your service logic"""
    
    # Use event bus for async coordination
    await self._publish_event(
        topic="task.completed",
        event_type="TaskCompleted",
        payload={'result': 'success'}
    )
    
    # Use data client for persistence
    if self.data_client:
        await self.data_client.insert('events', {
            'timestamp': datetime.utcnow().isoformat(),
            'data': request
        })
    
    return {"status": "completed"}
```

## Core Components

### 1. Event Bus (Pub-Sub)

The event bus enables loose coupling through async messaging:

```python
# Subscribe to events
await self.event_bus.subscribe(
    topic="orchestration.commands",
    handler=self._handle_command
)

# Publish events
await self._publish_event(
    topic="task.completed",
    event_type="TaskCompleted",
    payload={'result': data},
    priority=EventPriority.HIGH
)
```

### 2. Health Reporter & Lifecycle Hooks

Services have full lifecycle management:

```python
# Startup hook - initialize connections
async def _on_startup(self):
    await self.event_bus.start()
    await self.sidecar.start()

# Ready hook - subscribe to events  
async def _on_ready(self):
    await self.event_bus.subscribe(...)

# Pre-stop hook - drain requests
async def _on_pre_stop(self):
    await asyncio.sleep(5)  # Grace period

# Shutdown hook - cleanup
async def _on_shutdown(self):
    await self.event_bus.stop()
    await self.data_client.close()
```

### 3. Tool Registry & Integrations

Register and execute external tools:

```python
# Register a tool
self.tool_registry.register(
    name="websearch",
    description="Web search API",
    endpoint="http://search-api:8080/search"
)

# Execute tool
result = await self.tool_registry.execute(
    tool_name="websearch",
    params={'query': 'AI agents'}
)
```

### 4. LLM Adapters

Swap LLM providers without changing code:

```python
from integration import create_llm_adapter

# Create adapter (OpenAI, Anthropic, etc.)
llm = create_llm_adapter(
    provider='openai',
    model='gpt-4o',
    api_key=os.getenv('OPENAI_API_KEY')
)

# Use unified interface
response = await llm.complete(
    prompt="Analyze this text",
    system_prompt="You are a helpful assistant"
)
```

### 5. Data Client (Brokered Persistence)

Namespace-isolated data access:

```python
# Request a collection
await self.data_client.request_collection(
    name="thoughts",
    schema_hint={'timestamp': 'datetime', 'analysis': 'text'}
)

# Insert with automatic namespacing
# Stored as: "my-service.thoughts"
await self.data_client.insert('thoughts', {
    'timestamp': datetime.utcnow().isoformat(),
    'analysis': 'Some insight'
})

# Query with filters
results = await self.data_client.query(
    'thoughts',
    filters={'timestamp': {'$gte': recent_time}},
    limit=10,
    sort={'timestamp': 'desc'}
)
```

## Configuration Reference

### manifest.yaml Schema

```yaml
kind: "AOLService"  # AOLAgent, AOLTool, AOLPlugin, AOLService
apiVersion: "v1"

metadata:
  name: "service-name"
  version: "1.0.0"
  labels: {}

spec:
  # Endpoints
  endpoints:
    grpc: "50050"
    health: "50200"
    metrics: "8080"
  
  # Dependencies
  dependencies:
    - service: "aol-core"
      optional: false
  
  # Data storage
  dataRequirements:
    enabled: false
    collections: []
    accessRequests: []
  
  # Communication
  communication:
    grpc: {}
    pubsub:
      enabled: true
      publish: []
      subscribe: []
  
  # Integrations
  integrations:
    enabled: false
    tools: []
    llmAdapters: []
  
  # Resilience
  resilience:
    retry:
      maxAttempts: 3
    circuitBreaker:
      enabled: true
      threshold: 5
  
  # Health
  health:
    heartbeat:
      enabled: true
      interval: "10s"
  
  # Observability
  monitoring:
    tracing:
      enabled: true
    metrics:
      enabled: true
    logging:
      level: "INFO"
```

### config.yaml Schema

```yaml
# Service identity
service:
  name: "service-name"
  kind: "AOLService"

# Data client
dataClient:
  enabled: false
  aolCoreEndpoint: "aol-core:50051"

# Pub-sub
pubsub:
  enabled: true
  maxQueueSize: 1000

# Resilience
resilience:
  circuitBreaker:
    enabled: true
    failureThreshold: 5
  retry:
    maxAttempts: 3

# Health
health:
  heartbeat:
    enabled: true
    interval: 10

# Monitoring
monitoring:
  tracingEnabled: false
  metricsEnabled: true
  logLevel: "INFO"

# Discovery
discovery:
  consul:
    host: "consul-server:8500"
  aolCore:
    endpoint: "http://aol-core:8080"
```

## Service Types

| Type | Kind | Use Cases | Key Method |
|------|------|-----------|------------|
| Agent | AOLAgent | Reasoning, analysis, decisions | `Process()` → `Think()` |
| Tool | AOLTool | API wrappers, utilities | `Process()` → `Execute()` |
| Plugin | AOLPlugin | Extensions, add-ons | `Process()` → `Handle()` |
| Service | AOLService | General microservices | `Process()` |

## API Endpoints

Each service exposes these HTTP endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (for Consul) |
| `/ready` | GET | Readiness probe |
| `/live` | GET | Liveness probe |
| `/metrics` | GET | Prometheus metrics |
| `/api/process` | POST | Main processing endpoint |
| `/api/status` | GET | Service status and metrics |

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/gokulnathan66/harmonix-aol-arch.git
cd harmonix-aol-arch

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio flake8
```

## Running Tests

The repository includes a comprehensive test suite to ensure code quality and correctness.

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Tests

```bash
# Test validators
pytest tests/test_validators.py -v

# Test manifest validation
pytest tests/test_manifest.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=utils --cov-report=html
```

### Linting

```bash
# Check for syntax errors
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Full linting
flake8 . --count --max-complexity=10 --max-line-length=127 --statistics
```

## CI/CD

This repository uses GitHub Actions for continuous integration. The CI pipeline automatically:

- Runs on every push to `main` and `develop` branches
- Runs on all pull requests
- Executes linting checks with `flake8`
- Runs the full test suite with `pytest`

### CI Workflow

The workflow is defined in [`.github/workflows/ci.yaml`](.github/workflows/ci.yaml) and includes:

1. **Setup:** Python 3.11 environment
2. **Dependencies:** Install requirements and test dependencies
3. **Linting:** Check code quality and syntax
4. **Testing:** Run all tests with verbose output

### Local CI Simulation

To simulate the CI environment locally:

```bash
# Install dependencies
pip install -r requirements.txt
pip install flake8 pytest pytest-asyncio

# Run linting
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Run tests
pytest tests/ -v
```

## Testing

```bash
# Build
docker-compose build my-service

# Start
docker-compose up -d consul-server aol-core my-service

# Verify health
curl http://localhost:50220/health

# Check readiness
curl http://localhost:50220/ready

# Check service status
curl http://localhost:50220/api/status

# Check Consul registration
curl http://localhost:8500/v1/catalog/service/my-service

# Check service discovery via aol-core
curl http://localhost:8080/api/discovery/my-service
```


```bash
# Build
docker-compose build my-service

# Start
docker-compose up -d consul-server aol-core my-service

# Verify health
curl http://localhost:50220/health

# Check readiness
curl http://localhost:50220/ready

# Check service status
curl http://localhost:50220/api/status

# Check Consul registration
curl http://localhost:8500/v1/catalog/service/my-service

# Check service discovery via aol-core
curl http://localhost:8080/api/discovery/my-service
```

## Best Practices

### Port Allocation
- **gRPC:** 50051-50099
- **Sidecar:** 50100-50199
- **Health:** 50200-50299
- **Metrics:** 8080-8099

### Dependencies
Always declare in manifest:
```yaml
dependencies:
  - service: "aol-core"
    optional: false
  - service: "knowledge-db"  # If using data
    optional: false
```

### Event Topics
Use consistent naming:
- `service.lifecycle` - Service lifecycle events
- `task.{service}` - Task requests for specific service
- `task.completed` - Task completion notifications
- `orchestration.commands` - Commands from aol-core

### Circuit Breakers
Enable for all external calls:
```yaml
resilience:
  circuitBreaker:
    enabled: true
    threshold: 5
    timeout: "60s"
```

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** - System architecture and patterns
- **[Multi-Agent System](docs/multi-agent%20system-need.md)** - Requirements for AI systems
- **[AOL Components](docs/AOL-components.md)** - Detailed component breakdown
- **[Data Patterns](docs/data_patterns.md)** - Storage patterns and examples
- **[Best Practices](docs/BEST_PRACTICES.md)** - Production patterns
- **[Infrastructure](infrastructure/README.md)** - aol-core and Consul setup

## Infrastructure

Required infrastructure components in `infrastructure/`:

- **[aol-core](infrastructure/aol-core/)** - Central orchestration (required)
- **[consul](infrastructure/consul/)** - Service registry (required)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup and workflow
- Code standards and best practices
- Testing guidelines
- Pull request process
- Architecture guidelines

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`pytest tests/ -v` and `flake8 .`)
5. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

See our [Code of Conduct](CODE_OF_CONDUCT.md) for community guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security

If you discover a security vulnerability, please follow our [Security Policy](SECURITY.md) and report it responsibly.

## Support

1. Check manifest validation output
2. Review service logs: `docker-compose logs my-service`
3. Verify Consul registration: http://localhost:8500
4. Check aol-core discovery: http://localhost:8080/api/discovery
