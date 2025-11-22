# AOL Template Architecture

## Core Architecture Pattern

This template follows a **standardized architecture pattern** that is the same for ALL services (agents, tools, plugins, and general services).

## Service Registration & Discovery

### The Pattern (Same for Everyone)

```
┌─────────────────┐
│  Your Service   │
│  (Agent/Tool/   │
│   Plugin/etc)   │
└────────┬────────┘
         │
         │ 1. Register WITH Consul (direct)
         ▼
┌─────────────────┐
│     Consul      │ ◄─── Central Service Registry
│  (consul-server)│      All services register here
└────────┬────────┘
         │
         │ 2. aol-core reads from Consul
         ▼
┌─────────────────┐
│   aol-core      │ ◄─── Central Management Service
│  (SAME for all) │      - Discovers services from Consul
│                 │      - Provides discovery API
│                 │      - Manages routing, health, metrics
└────────┬────────┘
         │
         │ 3. Other services query aol-core
         ▼
┌─────────────────┐
│  Other Services │
│  (via discovery)│
└─────────────────┘
```

### Implementation Details

#### 1. Register WITH Consul (Direct)

Every service registers itself directly with Consul:

```python
# In service/main.py __init__
consul_host = os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[0]
consul_port = int(os.getenv('CONSUL_HTTP_ADDR', 'consul-server:8500').split(':')[1])
self.consul_client = consul.Consul(host=consul_host, port=consul_port)

# Register service
self.consul_client.agent.service.register(
    name=service_name,
    service_id=service_id,
    address=hostname,
    port=grpc_port,
    check=consul.Check.http(url=f"http://{hostname}:{health_port}/health")
)
```

**Environment Variables:**
- `CONSUL_HTTP_ADDR` - Consul address (default: `consul-server:8500`)

#### 2. Discover OTHER Services VIA aol-core (Indirect)

Services discover other services through aol-core, not Consul directly:

```python
# In service/main.py __init__
aol_core_endpoint = os.getenv('AOL_CORE_ENDPOINT', 'http://aol-core:8080')
self.discovery_client = AOLServiceDiscoveryClient(aol_core_endpoint)

# Discover other services
instances = await self.discovery_client.discover_service('other-service-name')
```

**Environment Variables:**
- `AOL_CORE_ENDPOINT` - aol-core HTTP endpoint (default: `http://aol-core:8080`)

#### 3. aol-core Management

**aol-core is the SAME instance for everyone:**

- aol-core reads from Consul to discover all registered services
- aol-core provides service discovery API: `GET /api/discovery/{service_name}`
- aol-core manages:
  - Service routing
  - Health checks
  - Metrics collection
  - Data access (via database service)
  - Service orchestration

**Why this pattern?**
- ✅ Centralized management through aol-core
- ✅ Services don't need direct Consul access for discovery
- ✅ aol-core can add features like load balancing, caching, etc.
- ✅ Easier to monitor and manage the entire system

## Data Access Pattern

Services access data through aol-core (not directly to database):

```python
# Initialize data client (uses aol-core)
self.data_client = DatabaseClient(
    aol_core_endpoint='http://aol-core:8080',
    service_name='my-service'
)

# aol-core routes to database service
await self.data_client.insert('collection', data)
await self.data_client.query('collection', filters={...})
```

**Flow:**
```
Service → aol-core → Database Service → Physical Database
```

## Example: Creating a New Service

When you create a new service using this template:

1. **Service registers with Consul** ✅
   - Template handles this automatically

2. **aol-core discovers your service** ✅
   - aol-core reads from Consul automatically

3. **Your service discovers other services** ✅
   - Use `AOLServiceDiscoveryClient` to query aol-core

4. **Other services discover your service** ✅
   - They query aol-core, which knows about your service

## Key Points

- ✅ **Consul** = Service registry (all services register here)
- ✅ **aol-core** = Central management (same instance for everyone)
- ✅ **Pattern** = Register with Consul, discover via aol-core
- ✅ **Template** = Implements this pattern automatically

## Environment Variables Summary

| Variable | Purpose | Default | Used By |
|----------|----------|---------|---------|
| `CONSUL_HTTP_ADDR` | Consul address for registration | `consul-server:8500` | All services |
| `AOL_CORE_ENDPOINT` | aol-core HTTP endpoint for discovery | `http://aol-core:8080` | All services |
| `HEALTH_PORT` | Health check port | From manifest.yaml | All services |
| `JAEGER_ENDPOINT` | Tracing endpoint (optional) | None | All services |

## See Also

- [AOL Components](AOL-components.md) - Detailed component breakdown
- [Best Practices](BEST_PRACTICES.md) - Production patterns
- [Data Patterns](data_patterns.md) - Data access patterns

