# AOL Template - Best Practices Guide

## Recent Updates (2025-11-22)

### ✅ Enhanced Data Client Implementation

The template now includes production-ready data storage patterns based on real-world implementations:

#### Improvements Made

1. **Better Error Handling**
   - Graceful degradation when database unavailable
   - Continue agent operation even if storage fails
   - Detailed error logging with context

2. **Flexible Configuration**
   - Supports both flat and nested config structures
   - Automatic service name detection
   - Sensible defaults for all settings

3. **Robust Collection Initialization**
   - Validates manifest before processing
   - Tracks initialization success/failure
   - Provides clear feedback with checkmarks (✓/✗)
   - Summary statistics on completion

4. **Production-Ready Settings**
   - Retry configuration added
   - Timeout controls
   - Connection pooling preparation
   - Schema validation hooks

5. **Better Context Handling**
   - Inline timestamp calculation for clarity
   - Graceful fallback to empty context
   - Debug logging for troubleshooting

## Usage Patterns

### Basic Data Storage

```python
# In your Think() method
if self.data_client:
    try:
        # Query historical context
        recent_thoughts = await self.data_client.query(
            'thoughts',
            filters={'timestamp': {'$gte': recent_time}},
            limit=5
        )
        
        # Store new thought
        doc_id = await self.data_client.insert('thoughts', {
            'thought_id': f"{pulse_id}-{service_name}",
            'timestamp': datetime.utcnow().isoformat(),
            'data': your_data
        })
    except Exception as e:
        self.logger.warning(f"Storage operation failed: {e}")
        # Agent continues working
```

### Cross-Service Data Access

```yaml
# In manifest-with-data.yaml
accessRequests:
  - collection: "other-service.shared_data"
    permission: "read"
    reason: "Need for correlation analysis"
```

```python
# In your agent code
critic_thoughts = await self.data_client.query(
    'critic-agent.thoughts',  # Cross-service access
    filters={'pulse_id': pulse_id}
)
```

## Configuration Best Practices

### Development vs Production

**Development**:
```yaml
dataClient:
  enabled: true
  timeout: 10
  retryAttempts: 1
  cacheEnabled: false  # Easier debugging
```

**Production**:
```yaml
dataClient:
  enabled: true
  timeout: 30
  retryAttempts: 3
  retryDelay: 1
  cacheEnabled: true
  cacheTTL: 300
  batchSize: 100
```

### Monitoring

Always enable monitoring to track data operations:

```yaml
monitoring:
  logLevel: "INFO"  # Use DEBUG for troubleshooting
  tracingEnabled: true
  metricsEnabled: true
```

### Collection Design

**Good Schema Hints**:
```yaml
collections:
  - name: "thoughts"
    schemaHint:
      thought_id: "string"      # Unique identifier
      timestamp: "datetime"      # Always include timestamps
      data: "text"              # Actual content
      confidence: "number"       # Metadata fields
    indexes:
      - fields: ["timestamp"]   # Index frequently queried fields
        type: "descending"
      - fields: ["thought_id"]
        type: "ascending"
        unique: true             # Enforce uniqueness where needed
```

## Template Files Reference

| File | Purpose | When to Use |
|------|---------|-------------|
| `config.yaml` | Basic runtime configuration | Services without data storage |
| `config-with-data.yaml` | Data-enabled configuration | Services that need persistence |
| `manifest.yaml` | Basic service declaration | Services without data storage |
| `manifest-with-data.yaml` | Full service + data declaration | Services with collections |
| `agent.py` | Enhanced agent template | All new agents/services |
| `sidecar.py` | Service sidecar | Health checks, metrics |

## Verification Checklist

After creating a new service from this template:

- [ ] Renamed all `example-agent` references to your service name
- [ ] Updated ports in both manifest and config
- [ ] Defined collections in manifest (if using data storage)
- [ ] Configured `dataClient` in config.yaml
- [ ] Implemented business logic in `Think()` method
- [ ] Added service to docker-compose.yml
- [ ] Tested health endpoint
- [ ] Verified Consul registration
- [ ] Checked collection creation in database
- [ ] Tested data persistence
- [ ] Verified logging and tracing

## Common Issues

### Data Client Not Initializing

**Symptom**: Logs show "Data client disabled"

**Causes**:
1. `dataClient.enabled` is false or missing
2. Config structure doesn't match template
3. Missing `shared.utils.data_client` module

**Fix**: Check config.yaml and ensure structure matches template

### Collections Not Created

**Symptom**: Agent starts but no collections in database

**Causes**:
1. `dataRequirements.enabled` is false in manifest
2. manifest.yaml not in same directory as agent.py
3. Database service not running

**Fix**: Verify manifest location and database connectivity

### Storage Failures

**Symptom**: "Failed to store thought" errors

**Impact**: ✅ Agent continues working (graceful degradation)

**Causes**:
1. Database service unavailable
2. Collection not initialized
3. Schema validation failure (if enabled)

**Fix**: Check database logs and collection initialization

## Next Steps

1. Review the [implementation walkthrough](file:///Users/gokulnathanb/.gemini/antigravity/brain/daa06f3d-a972-4dbb-912d-4a1b5c45a9d2/walkthrough.md) for real examples
2. See [template improvements](file:///Users/gokulnathanb/.gemini/antigravity/brain/daa06f3d-a972-4dbb-912d-4a1b5c45a9d2/template_improvements.md) for advanced features
3. Check `examples/` directory for code samples
4. Review `data_patterns.md` for design patterns
