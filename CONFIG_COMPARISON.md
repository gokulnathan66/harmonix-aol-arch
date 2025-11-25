# Configuration Files Guide

This document explains how to configure your AOL service manifest and config files.

## File Structure

| File | Purpose | Data Storage | Use Case |
|------|---------|--------------|----------|
| `manifest.yaml` | Unified template manifest | Configurable | All services (enable/disable data as needed) |
| `config.yaml` | Unified runtime config | Configurable | All services (enable/disable data as needed) |
| `config-with-data.yaml` | Example reference | Enabled | Reference showing enabled data storage |

## Key Differences

### Manifest File

#### `manifest.yaml` (Unified Template)
- **Unified file** - Combines base and data-enabled configurations
- `dataRequirements.enabled: false` - Data storage disabled by default
- Collections defined with examples (customize as needed)
- Clear comments showing how to enable data storage
- `knowledge-db` dependency commented out (uncomment when enabling data)
- Use for all services - enable/disable features as needed

### Config File

#### `config.yaml` (Unified Template)
- **Unified file** - Combines base and data-enabled configurations
- `dataClient.enabled: false` - Data client disabled by default
- `tracingEnabled: false` - Tracing disabled by default (can be enabled)
- Clear comments showing how to enable data storage and tracing
- All other features enabled (pub-sub, resilience, health, etc.)
- Use for all services - enable/disable features as needed

#### `config-with-data.yaml` (Reference Example)
- Example showing data storage and tracing enabled
- Use as reference when enabling these features
- Same structure as unified config

## Feature Matrix

| Feature | Base Config | Data Config | Notes |
|---------|-------------|-------------|-------|
| **Data Storage** | ❌ Disabled | ✅ Enabled | Requires knowledge-db |
| **Pub-Sub** | ✅ Enabled | ✅ Enabled | Event-driven messaging |
| **Circuit Breaker** | ✅ Enabled | ✅ Enabled | Fault tolerance |
| **Retry Logic** | ✅ Enabled | ✅ Enabled | Automatic retries |
| **Health Checks** | ✅ Enabled | ✅ Enabled | Heartbeats & probes |
| **Tracing** | ⚠️ Disabled | ✅ Enabled | OpenTelemetry |
| **Metrics** | ✅ Enabled | ✅ Enabled | Prometheus |
| **Tool Registry** | ✅ Available | ✅ Available | External integrations |
| **LLM Adapters** | ✅ Available | ✅ Available | Model swapping |

## Usage Guide

### For Services WITHOUT Data Storage

1. Use `manifest.yaml` as your manifest (default)
2. Use `config.yaml` as your config
3. Keep `dataRequirements.enabled: false` in manifest
4. Keep `dataClient.enabled: false` in config

**Example:**
```yaml
# manifest.yaml
spec:
  dataRequirements:
    enabled: false  # Already set by default

# config.yaml
dataClient:
  enabled: false  # Already set by default
```

### For Services WITH Data Storage

1. Use `manifest.yaml` and set `dataRequirements.enabled: true`
2. Use `config.yaml` and set `dataClient.enabled: true`
3. Uncomment `knowledge-db` dependency in manifest
4. Customize collections for your needs

**Example:**
```yaml
# manifest.yaml
spec:
  dependencies:
    # Uncomment this:
    - service: "knowledge-db"
      optional: false
  
  dataRequirements:
    enabled: true  # Change from false
    collections:
      - name: "my_data"
        schemaHint:
          timestamp: "datetime"
          value: "number"

# config.yaml
dataClient:
  enabled: true  # Change from false
  aolCoreEndpoint: "aol-core:50051"
```

## Common Configuration Patterns

### Pattern 1: Stateless Service (No Data)
```yaml
# manifest.yaml
dataRequirements:
  enabled: false

# config.yaml
dataClient:
  enabled: false
```
**Use for:** API gateways, proxies, stateless processors

### Pattern 2: Stateful Service (With Data)
```yaml
# manifest.yaml
spec:
  dependencies:
    - service: "knowledge-db"
      optional: false
  
  dataRequirements:
    enabled: true
    collections:
      - name: "state"
        schemaHint: {...}

# config.yaml
dataClient:
  enabled: true
```
**Use for:** Agents, services with memory, data processors

### Pattern 3: Hybrid (Read-Only Data Access)
```yaml
# manifest.yaml
spec:
  dataRequirements:
    enabled: false  # Don't own collections
    accessRequests:
      - collection: "other-service.data"
        permission: "read"

# config.yaml
dataClient:
  enabled: true  # Need client to read
```
**Use for:** Services that read but don't write

## Migration Guide

### Enabling Data Storage

1. **Update manifest.yaml:**
   ```yaml
   spec:
     dependencies:
       # Uncomment knowledge-db dependency:
       - service: "knowledge-db"
         optional: false
     
     dataRequirements:
       enabled: true  # Change from false
       collections:
         - name: "your_collection"
           schemaHint: {...}
   ```

2. **Update config.yaml:**
   ```yaml
   dataClient:
     enabled: true  # Change from false
     aolCoreEndpoint: "aol-core:50051"
   ```

3. **Restart service** - Collections will be initialized on startup

### Enabling Tracing

To enable distributed tracing:

```yaml
# config.yaml
monitoring:
  tracingEnabled: true  # Change from false
  tracing:
    endpoint: "${JAEGER_ENDPOINT}"
    samplingRate: 0.1
```

### Disabling Data Storage

1. **Update manifest.yaml:**
   ```yaml
   spec:
     dataRequirements:
       enabled: false
   ```

2. **Update config.yaml:**
   ```yaml
   dataClient:
     enabled: false
   ```

3. **Remove knowledge-db dependency** (if not needed)

## Best Practices

1. **Start with base configs** - Enable features as needed
2. **Keep manifests declarative** - Describe what, not how
3. **Use consistent naming** - Follow service naming conventions
4. **Validate before deploy** - Use validators to check configs
5. **Document collections** - Add descriptions to schema hints

## Validation

Both configs can be validated:

```bash
# Validate manifest
python3 -c "
from utils.validators import validate_manifest, print_validation_result
result = validate_manifest('manifest.yaml')
print_validation_result(result)
"

# Validate config
python3 -c "
from utils.validators import validate_config, print_validation_result
result = validate_config('config.yaml')
print_validation_result(result)
"
```

## See Also

- [README.md](README.md) - Main documentation
- [Comprehensive Guide](Comprehensive%20Guide%20to%20Essential%20Components%20in%20AOL%20Service%20Configurations%20for%20Multi-Agent%20Collaboration.md) - Full feature guide
- [Data Patterns](docs/data_patterns.md) - Data usage patterns

