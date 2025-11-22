# g2-aol-template 

Complete template for creating AOL-compliant agents and services in the Pulse-AI multi-mesh architecture.

## 🆕 Recent Updates (2025-11-22)

The template has been enhanced with **production-ready data storage patterns**:

- ✅ **Improved error handling** - Graceful degradation when database unavailable
- ✅ **Flexible configuration** - Supports multiple config structures
- ✅ **Robust initialization** - Better collection setup with progress tracking
- ✅ **Production settings** - Retry logic, timeouts, connection pooling
- ✅ **Enhanced logging** - Clear feedback with unicode checkmarks
- ✅ **Better documentation** - New BEST_PRACTICES.md guide

See [`BEST_PRACTICES.md`](BEST_PRACTICES.md) for details.

---

## Files

### Core Template Files
- [`agent.py`](agent.py) - Template agent implementation with data client integration
- [`config.yaml`](config.yaml) - Basic runtime configuration
- [`sidecar.py`](sidecar.py) - Sidecar for health checks and metrics

### Enhanced Templates (with Data Storage)
- [`manifest-with-data.yaml`](manifest-with-data.yaml) - Manifest showing `dataRequirements` section
- [`config-with-data.yaml`](config-with-data.yaml) - Config with `dataClient` settings

### Documentation
- [`AOL-components.md`](AOL-components.md) - Complete guide to AOL service requirements
- [`data_patterns.md`](data_patterns.md) - Data storage patterns and best practices
- **[`BEST_PRACTICES.md`](BEST_PRACTICES.md)** - **NEW: Production-ready patterns and troubleshooting**

### Examples
- [`examples/simple_storage_example.py`](examples/simple_storage_example.py) - Basic CRUD operations
- [`examples/shared_collection_example.py`](examples/shared_collection_example.py) - Cross-service data sharing

## Quick Start

### Option A: Automated Setup (Recommended)

Use the interactive setup script:

```bash
cd g2-aol-template
./create-service.sh my-new-service
```

The script will:
- ✅ Create service directory in `app/my-new-service/`
- ✅ Copy all template files
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
mkdir -p my-service
cp -r g2-aol-template/* my-service/
cd my-service
```

### 2. Customize Manifest

Edit `manifest.yaml` (or use `manifest-with-data.yaml` if you need storage):

```yaml
metadata:
  name: "my-service"  # Change this
  version: "1.0.0"

spec:
  endpoints:
    grpc: "50070"  # Pick unused port
    health: "50220"
    metrics: "8095"
```

### 3. Configure Runtime

Edit `config.yaml`:

```yaml
spec:
  name: "my-service"
  grpcPort: 50070
  healthPort: 50220
  metricsPort: 8095
```

### 4. Implement Logic

Edit `agent.py` and implement your service logic in the `Think` method.

### 5. Add to Docker Compose

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
```

## Data Storage Integration

If your service needs to store data:

### 1. Declare Data Requirements

Use `manifest-with-data.yaml` as reference and add:

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
spec:
  dataClient:
    enabled: true
    aolCoreEndpoint: "aol-core:50051"
```

### 3. Use Data Client

The template `agent.py` already includes data client usage:

```python
# Initialize happens automatically in __init__
# Collections are requested on startup

# In your Think method:
async def Think(self, request):
    # Store data
    await self.data_client.insert('my_data', {
        'timestamp': datetime.utcnow().isoformat(),
        'value': 123
    })
    
    # Query data
    results = await self.data_client.query(
        'my_data',
        filters={'value': {'$gt': 100}},
        limit=10
    )
```

## Best Practices

### Port Allocation
- **gRPC:** 50051-50099
- **Health:** 50200-50299
- **Metrics:** 8080-8099

### Service Naming
- Use lowercase with hyphens: `my-service`
- Be descriptive: `text-analyzer` not `agent1`

### Dependencies
Always declare in manifest.yaml:
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
```

## Documentation

- [AOL Components](AOL-components.md): Detailed breakdown of system components.
- [Data Patterns](data_patterns.md): Guide to using the Data Client and storage patterns.
- [Logging Setup](docs/LOGGING.md): Guide to centralized logging with ELK and Filebeat.
- See examples in `examples/` directory

## Support

For issues or questions:
1. Check [`AOL-components.md`](AOL-components.md) requirements
2. Review example implementations
3. Verify manifest.yaml follows schema
4. Check Consul UI for service registration
