# Infrastructure Components

This directory contains the core infrastructure components needed for the AOL multi-agent system:

- **aol-core** - Central orchestration and service management service
- **consul** - Service registry configuration

## aol-core

The **Agent Orchestration Layer (AOL) Core** is the central management service that:

- Discovers services registered with Consul
- Provides service discovery API (`/api/discovery/{service_name}`)
- Manages service health checks
- Routes requests between services
- Provides monitoring and metrics APIs
- Manages proto file registry
- Handles logging and tracing

### Key Features

- **Service Discovery**: Services register with Consul, aol-core discovers them
- **Health Management**: Periodic health checks for all registered services
- **Monitoring API**: REST API for service monitoring and WebSocket for real-time updates
- **gRPC Gateway**: gRPC server for service-to-service communication
- **Event Store**: Tracks system events (service registration, health changes, routing)

### Setup

1. **Build the Docker image:**
```bash
cd infrastructure/aol-core
docker build -t aol-core .
```

2. **Run with docker-compose:**
```yaml
aol-core:
  build:
    context: .
    dockerfile: ./infrastructure/aol-core/Dockerfile
  container_name: aol-core
  hostname: aol-core
  ports:
    - "50051:50051"  # gRPC
    - "50201:50201"  # Health/HTTP API
    - "9090:9090"    # Metrics
  environment:
    - CONSUL_HTTP_ADDR=consul-server:8500
  networks:
    - heart-pulse-network
  depends_on:
    - consul-server
```

3. **Configuration:**
   - Edit `config.yaml` to customize settings
   - Default Consul connection: `consul-server:8500`
   - Default HTTP API port: `50201`
   - Default gRPC port: `50051`

### API Endpoints

- `GET /health` - Health check
- `GET /api/discovery` - List all services
- `GET /api/discovery/{service_name}` - Discover service instances
- `GET /api/services` - List registered services (monitoring)
- `GET /api/events` - Get system events
- `GET /api/routes` - Get communication flow data
- `GET /ws` - WebSocket for real-time updates
- `GET /api/proto/list` - List proto files
- `POST /api/logging/log` - Submit logs
- `POST /api/metrics` - Submit metrics

### Architecture

```
Services → Register with Consul → aol-core reads Consul → Provides Discovery API
```

**Important**: aol-core is the **SAME instance for everyone**. All services use the same aol-core endpoint (`http://aol-core:8080` by default).

## Consul

Consul is the service registry where all services register themselves.

### Configuration

The Consul configuration file is in `consul/config/consul-config.hcl`:

- Datacenter: `heart-pulse-dc1`
- UI enabled: Yes
- Service mesh (Consul Connect): Enabled
- Script checks: Enabled

### Setup

Consul typically runs as a Docker container:

```yaml
consul-server:
  image: consul:latest
  container_name: consul-server
  hostname: consul-server
  volumes:
    - ./infrastructure/consul/config:/consul/config
    - consul-data:/consul/data
  ports:
    - "8500:8500"  # HTTP API
    - "8600:8600/udp"  # DNS
  command: agent -server -ui -client=0.0.0.0 -bootstrap-expect=1 -config-dir=/consul/config
  networks:
    - heart-pulse-network
```

### Access

- Consul UI: http://localhost:8500
- Consul API: http://localhost:8500/v1/

## Integration with Services

All services created using the template automatically:

1. **Register with Consul** (direct connection)
2. **Discover other services via aol-core** (indirect, through aol-core API)

See the main [README.md](../README.md) for details on how services integrate with aol-core and Consul.

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CONSUL_HTTP_ADDR` | Consul address | `consul-server:8500` |
| `AOL_CORE_ENDPOINT` | aol-core HTTP endpoint | `http://aol-core:8080` |
| `JAEGER_ENDPOINT` | Tracing endpoint (optional) | None |

## See Also

- [Architecture Documentation](../docs/ARCHITECTURE.md) - Detailed architecture explanation
- [Service Template](../README.md) - How to create services that use aol-core

