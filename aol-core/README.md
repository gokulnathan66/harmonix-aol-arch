# AOL Core

The Agent Orchestration Layer (AOL) Core is the central management service for the multi-agent system.

## What It Does

- **Service Discovery**: Discovers services registered with Consul and provides discovery API
- **Health Management**: Monitors health of all registered services
- **Service Routing**: Routes requests between services
- **Monitoring**: Provides REST API and WebSocket for real-time monitoring
- **Proto Registry**: Manages proto file storage and retrieval
- **Logging & Metrics**: Centralized logging and metrics collection

## Quick Start

### Using Docker

```bash
docker build -t aol-core .
docker run -p 50051:50051 -p 50201:50201 -p 9090:9090 \
  -e CONSUL_HTTP_ADDR=consul-server:8500 \
  aol-core
```

### Configuration

Edit `config.yaml` to customize:

- Consul connection settings
- Port numbers
- Health check intervals
- Monitoring settings

## API Endpoints

### Service Discovery
- `GET /api/discovery` - List all services
- `GET /api/discovery/{service_name}` - Get service instances
- `GET /api/discovery/{service_name}/health` - Get service health

### Monitoring
- `GET /api/services` - List registered services
- `GET /api/events` - Get system events
- `GET /api/routes` - Get communication flow
- `GET /ws` - WebSocket for real-time updates

### Other
- `GET /health` - Health check
- `GET /api/proto/list` - List proto files
- `POST /api/logging/log` - Submit logs
- `POST /api/metrics` - Submit metrics

## Architecture

aol-core reads from Consul (where services register) and provides discovery APIs that other services use.

```
Services → Consul → aol-core → Discovery API → Other Services
```

See [../README.md](../README.md) for more details.

