# Consul Service Discovery Migration Guide

## Overview

This document describes the migration from Docker-based service discovery to Consul-based service discovery with gRPC load balancing and service mesh capabilities in the Heart-Pulse AOL system.

## Migration Summary

The system has been migrated from Docker socket-based service discovery to HashiCorp Consul, providing:

- **Service Discovery**: Automatic service registration and health-based routing
- **Load Balancing**: Client-side round-robin load balancing with circuit breakers
- **Service Mesh**: Consul Connect for mTLS between services
- **Observability**: Integration with Prometheus for service discovery
- **Resilience**: Circuit breakers and retry logic with exponential backoff

## Architecture Changes

### Before (Docker Discovery)

```
Services → Docker Socket → Docker Discovery → Service Registry
```

### After (Consul Discovery)

```
Services → Consul Agent → Consul Server → Service Registry
         ↓
    Load Balanced gRPC Client
         ↓
    Circuit Breaker + Retry Logic
```

## Key Components

### 1. Consul Infrastructure

**Location**: `app/consul/config/consul-config.hcl`

Consul server configuration with:
- Service mesh enabled (Consul Connect)
- UI enabled for service visualization
- Health check configuration

### 2. Consul Service Registry

**Location**: `app/aol-core/registry/consul_registry.py`

Provides:
- Service registration and deregistration
- Service discovery with health filtering
- Configuration management via Consul KV store
- Service watching for dynamic updates

### 3. Load-Balanced gRPC Client

**Location**: `app/shared/utils/grpc_client.py`

Features:
- Round-robin endpoint selection
- Circuit breaker pattern (CLOSED → OPEN → HALF_OPEN)
- Exponential backoff retry logic
- Connection pooling and keepalive

## Service Registration

All services now register themselves with Consul on startup:

### AOL Core
- Service Name: `aol-core`
- Ports: gRPC (50051), Health (50201), Metrics (9090)
- Tags: `aol`, `core`, `orchestrator`

### Heart-Pulse
- Service Name: `heart-pulse`
- Ports: gRPC (50052), Health (50202), Metrics (8080)
- Tags: `heart-pulse`, `orchestrator`

### Agents (Critic, Validator)
- Service Names: `critic-agent`, `validator-agent`
- Ports: gRPC (50053/50054), Health (50203/50204), Metrics (8081/8082)
- Tags: `agent`, `critic`/`validator`, `llm`

## Configuration Changes

### AOL Core Config (`app/aol-core/config.yaml`)

**Removed**:
```yaml
discovery:
  method: "docker"
  dockerSocket: "/var/run/docker.sock"
```

**Added**:
```yaml
consul:
  host: "consul-server"
  port: 8500
  datacenter: "heart-pulse-dc1"
  connect:
    enabled: true
```

### Docker Compose Changes

**Removed**:
- Docker socket volume mounts (`/var/run/docker.sock`)
- Hardcoded service endpoints (`AOL_CORE_HOST`, `AOL_CORE_PORT`)

**Added**:
- Consul server service
- Consul environment variables (`CONSUL_HTTP_ADDR`, `CONSUL_GRPC_ADDR`)
- Consul data volume

## Load Balancing

### Client-Side Load Balancing

Services use `LoadBalancedGRPCClient` for gRPC calls:

```python
from shared.utils.grpc_client import LoadBalancedGRPCClient

client = LoadBalancedGRPCClient('critic-agent', consul_registry)
response = await client.call(StubClass, 'method_name', request)
```

### Features

1. **Round-Robin Selection**: Distributes requests across healthy instances
2. **Health-Based Routing**: Only routes to healthy services
3. **Circuit Breaker**: Prevents cascading failures
   - Threshold: 5 failures
   - Timeout: 60 seconds
   - States: CLOSED → OPEN → HALF_OPEN
4. **Retry Logic**: Exponential backoff (2s → 4s → 8s → 10s max)

## Circuit Breaker States

### CLOSED (Normal Operation)
- Requests flow normally
- Failures are tracked

### OPEN (Failure State)
- Requests fail immediately
- Prevents overwhelming failing service
- Transitions to HALF_OPEN after timeout

### HALF_OPEN (Testing State)
- Allows limited requests to test recovery
- On success → CLOSED
- On failure → OPEN

## Monitoring Integration

### Prometheus Service Discovery

**Location**: `app/monitoring/prometheus/prometheus.yml`

Prometheus now uses Consul service discovery:

```yaml
scrape_configs:
  - job_name: 'aol-core'
    consul_sd_configs:
      - server: 'consul-server:8500'
        services: ['aol-core']
```

### Consul UI

Access Consul UI at: `http://localhost:8500`

Features:
- Service catalog visualization
- Health status monitoring
- Service topology
- Configuration management

## Migration Checklist

### Phase 1: Infrastructure ✅
- [x] Add Consul server to docker-compose.yml
- [x] Create Consul configuration directory
- [x] Configure Consul server with service mesh

### Phase 2: Code Updates ✅
- [x] Create Consul registry module
- [x] Update AOL Core to use Consul
- [x] Create load-balanced gRPC client
- [x] Update Heart-Pulse service
- [x] Update agent services

### Phase 3: Configuration ✅
- [x] Update AOL Core config.yaml
- [x] Update docker-compose.yml environment variables
- [x] Update Prometheus configuration
- [x] Update requirements.txt files

### Phase 4: Testing
- [ ] Test service registration on startup
- [ ] Verify health checks in Consul UI
- [ ] Test load balancing across multiple instances
- [ ] Verify circuit breaker functionality
- [ ] Test automatic service deregistration on shutdown

## Dependencies Added

### Python Packages
- `python-consul==1.1.0` - Consul client library
- `tenacity==8.2.3` - Retry logic
- `grpcio-health-checking==1.60.0` - gRPC health checks

## Environment Variables

### Required
- `CONSUL_HTTP_ADDR` - Consul HTTP API address (default: `consul-server:8500`)
- `CONSUL_GRPC_ADDR` - Consul gRPC API address (default: `consul-server:8502`)

### Removed
- `AOL_CORE_HOST` - No longer needed (discovered via Consul)
- `AOL_CORE_PORT` - No longer needed (discovered via Consul)

## Service Discovery Flow

1. **Service Startup**
   - Service initializes Consul registry
   - Registers itself with Consul (name, address, ports, tags, metadata)
   - Health check endpoint registered

2. **Service Discovery**
   - Client queries Consul for service instances
   - Consul returns healthy instances only
   - Load balancer selects next endpoint (round-robin)

3. **Health Monitoring**
   - Consul performs health checks (HTTP/gRPC)
   - Unhealthy services automatically removed from discovery
   - Services re-registered when healthy

4. **Service Shutdown**
   - Graceful shutdown handler deregisters service
   - Consul removes service from catalog

## Consul Connect (Service Mesh)

Consul Connect provides automatic mTLS between services:

### Configuration

Enable in `consul-config.hcl`:
```hcl
connect {
  enabled = true
}
```

### Benefits

- Automatic certificate management
- Service-to-service authentication
- Encrypted communication
- Certificate rotation

## Troubleshooting

### Service Not Appearing in Consul

1. Check Consul server logs: `docker logs consul-server`
2. Verify service registration code executed
3. Check network connectivity to Consul
4. Verify health check endpoint is accessible

### Load Balancing Not Working

1. Verify multiple service instances registered
2. Check all instances are healthy in Consul UI
3. Verify `LoadBalancedGRPCClient` is being used
4. Check circuit breaker state (should be CLOSED)

### Circuit Breaker Stuck OPEN

1. Check service health in Consul
2. Verify service endpoints are accessible
3. Wait for timeout period (60 seconds)
4. Manually reset by restarting client

## Best Practices

1. **Service Registration**: Always register on startup, deregister on shutdown
2. **Health Checks**: Implement fast, reliable health endpoints
3. **Circuit Breakers**: Configure appropriate thresholds for your workload
4. **Retry Logic**: Use exponential backoff to avoid thundering herd
5. **Monitoring**: Monitor Consul service catalog and circuit breaker states

## Future Enhancements

- [ ] Implement Consul Connect sidecar proxies for mTLS
- [ ] Add service mesh visualization
- [ ] Implement distributed tracing across services
- [ ] Add service-level SLAs and alerting
- [ ] Implement service versioning and canary deployments

## References

- [HashiCorp Consul Documentation](https://www.consul.io/docs)
- [Consul Connect](https://www.consul.io/docs/connect)
- [gRPC Load Balancing](https://grpc.io/blog/grpc-load-balancing/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)

