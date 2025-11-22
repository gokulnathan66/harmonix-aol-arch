# Data Storage Patterns in AOL Multi-Mesh

## Philosophy

Services in the AOL multi-mesh architecture **never connect directly to databases**. All data operations flow through **AOL-Core as a Data Broker**, which provides:

- **Centralized Access Control:** AOL-Core validates permissions before allowing operations
- **Collection Registry:** Tracks which service owns which collections
- **Audit Logging:** Records all data access for compliance and debugging
- **Namespace Isolation:** Prevents collection name conflicts across services
- **Schema Flexibility:** No pre-defined schemas; services store any JSON structure

**Data Flow:**
```
Service → AOL-Core (Data Broker) → Database Service → Physical DB
         ↑
         • Permission Check
         • Collection Registry Lookup
         • Metadata Injection
         • Audit Logging
```

---

## Declaring Data Needs

### In manifest.yaml

Services declare their data requirements in `manifest.yaml`:

```yaml
kind: "AOLAgent"
apiVersion: "v1"
metadata:
  name: "my-service"
  version: "1.0.0"

spec:
  # ... endpoints, configSchema, etc ...
  
  # Data storage requirements
  dataRequirements:
    enabled: true
    
    # Collections this service will own
    collections:
      - name: "events"
        description: "Application event log"
        schemaHint:
          event_id: "string"
          timestamp: "datetime"
          event_type: "string"
          data: "object"
        indexes:
          - fields: ["timestamp"]
            type: "ascending"
          - fields: ["event_type", "timestamp"]
            type: "compound"
      
      - name: "metrics"
        description: "Performance metrics"
        schemaHint:
          metric_name: "string"
          value: "number"
          timestamp: "datetime"
        indexes:
          - fields: ["metric_name", "timestamp"]
            type: "compound"
    
    # Collections from other services this service needs
    accessRequests:
      - collection: "other-service.shared_data"
        permission: "read"
        reason: "Need to correlate with external events"
```

**Schema Hints:**
- Optional but recommended for performance
- Database service uses hints to create appropriate indexes
- Types: `string`, `number`, `boolean`, `datetime`, `object`, `array`

**Indexes:**
- `ascending`: Single field, ascending order
- `descending`: Single field, descending order
- `compound`: Multiple fields together
- `unique`: Enforce uniqueness
-`text`: Full-text search (if supported by DB adapter)

---

## Using the Data Client

### Initialization

```python
from shared.utils.data_client import AOLDataClient

class MyService:
    def __init__(self, config_path='config.yaml'):
        # Load config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # Initialize data client
        self.data_client = AOLDataClient(
            aol_core_endpoint=self.config['spec']['dataClient']['aolCoreEndpoint'],
            service_name=self.config['metadata']['name']
        )
        
    async def initialize_collections(self):
        """Request collections declared in manifest"""
        manifest = self._load_manifest()
        
        for collection_spec in manifest['spec']['dataRequirements']['collections']:
            collection_id = await self.data_client.request_collection(
                name=collection_spec['name'],
                schema_hint=collection_spec.get('schemaHint'),
                indexes=collection_spec.get('indexes')
            )
            logger.info(f"Collection '{collection_spec['name']}' ready: {collection_id}")
```

### Basic Operations

#### Insert

```python
# Insert a single document
doc_id = await self.data_client.insert('events', {
    'event_id': str(uuid.uuid4()),
    'timestamp': datetime.utcnow().isoformat(),
    'event_type': 'user.login',
    'data': {
        'user_id': '12345',
        'ip_address': '192.168.1.1'
    }
})
```

#### Query

```python
# Simple query
results = await self.data_client.query(
    collection='events',
    filters={'event_type': 'user.login'},
    limit=10
)

# Query with operators
results = await self.data_client.query(
    collection='metrics',
    filters={
        'metric_name': 'response_time',
        'value': {'$gt': 100},  # Greater than 100
        'timestamp': {'$gte': '2025-11-22T00:00:00Z'}  # Since midnight
    },
    projection=['metric_name', 'value', 'timestamp'],  # Only these fields
    sort={'timestamp': 'desc'},
    limit=50
)
```

**Filter Operators:**
- `$eq`: Equal (default if not specified)
- `$ne`: Not equal
- `$gt`: Greater than
- `$gte`: Greater than or equal
- `$lt`: Less than
- `$lte`: Less than or equal
- `$in`: Value in array
- `$nin`: Value not in array
- `$regex`: Regular expression match

#### Update

```python
# Update documents matching filter
updated_count = await self.data_client.update(
    collection='events',
    filters={'event_id': '12345'},
    update_data={
        'processed': True,
        'processed_at': datetime.utcnow().isoformat()
    }
)
```

#### Delete

```python
# Delete documents matching filter
deleted_count = await self.data_client.delete(
    collection='events',
    filters={
        'timestamp': {'$lt': '2025-11-01T00:00:00Z'},  # Older than Nov 1
        'processed': True
    }
)
```

---

## Cross-Service Data Sharing

### Granting Access

```python
# Service A grants read access to Service B
await self.data_client.grant_access(
    collection='events',
    target_service='service-b',
    permission='read'
)

# Grant write access (use with caution)
await self.data_client.grant_access(
    collection='shared_cache',
    target_service='service-c',
    permission='write'
)
```

### Accessing Shared Collections

Service B's manifest declares the access request:

```yaml
dataRequirements:
  accessRequests:
    - collection: "service-a.events"
      permission: "read"
      reason: "Analytics on service-a events"
```

Service B then queries normally:

```python
# Query another service's collection (permission required)
events = await self.data_client.query(
    collection='service-a.events',
    filters={'event_type': 'error'},
    limit=100
)
```

**Permission Model:**
- `read`: Query only
- `write`: Insert, update, delete
- `admin`: Read, write, grant/revoke access

---

## Advanced Patterns

### Time-Series Data

```python
# Store time-series metrics efficiently
async def store_metric(self, name, value):
    await self.data_client.insert('metrics', {
        'metric_name': name,
        'value': value,
        'timestamp': datetime.utcnow().isoformat(),
        'tags': {
            'service': self.config['metadata']['name'],
            'version': self.config['metadata']['version']
        }
    })

# Query recent metrics
async def get_recent_metrics(self, name, hours=24):
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    return await self.data_client.query(
        'metrics',
        filters={
            'metric_name': name,
            'timestamp': {'$gte': since}
        },
        sort={'timestamp': 'asc'}
    )
```

### Event Sourcing

```python
# Append-only event log
async def log_event(self, event_type, data):
    event_id = str(uuid.uuid4())
    
    await self.data_client.insert('events', {
        'event_id': event_id,
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data,
        'metadata': {
            'service': self.config['metadata']['name'],
            'correlation_id': get_correlation_id()
        }
    })
    
    return event_id

# Replay events
async def replay_events(self, since=None):
    filters = {}
    if since:
        filters['timestamp'] = {'$gte': since}
    
    events = await self.data_client.query(
        'events',
        filters=filters,
        sort={'timestamp': 'asc'},
        limit=1000
    )
    
    for event in events:
        await self.process_event(event)
```

### Caching Pattern

```python
async def get_with_cache(self, key):
    # Try cache first
    cached = await self.data_client.query(
        'cache',
        filters={'key': key},
        limit=1
    )
    
    if cached and not self._is_expired(cached[0]):
        return cached[0]['value']
    
    # Cache miss - fetch and store
    value = await self.fetch_expensive_data(key)
    
    await self.data_client.insert('cache', {
        'key': key,
        'value': value,
        'cached_at': datetime.utcnow().isoformat(),
        'ttl': 3600  # seconds
    })
    
    return value
```

---

## Best Practices

### 1. Namespacing

Collections are automatically namespaced as `{service-name}.{collection-name}`. This prevents conflicts and provides clear ownership.

```python
# Internal collection name: 'events'
# Full namespaced name: 'my-service.events'
# No need to specify prefix manually
```

### 2. Indexing

Always declare indexes for frequently queried fields:

```yaml
indexes:
  - fields: ["timestamp"]  # Time-range queries
    type: "ascending"
  - fields: ["user_id", "timestamp"]  # Compound for user-specific queries
    type: "compound"
```

### 3. Schema Evolution

When adding new fields to documents:

```python
# Old documents
{'event_id': '123', 'timestamp': '...'}

# New documents (backward compatible)
{
    'event_id': '456',
    'timestamp': '...',
    'new_field': 'value',  # New field
    'schema_version': 2     # Track version
}

# Handle both in queries
async def process_event(self, event):
    schema_version = event.get('schema_version', 1)
    
    if schema_version >= 2:
        # Process new_field
        pass
```

### 4. Error Handling

```python
from shared.utils.data_client import DataClientError, PermissionDeniedError

try:
    await self.data_client.insert('events', {...})
except PermissionDeniedError:
    logger.error("No permission to write to collection")
except DataClientError as e:
    logger.error(f"Database operation failed: {e}")
```

### 5. Bulk Operations

```python
# Batch inserts for efficiency
async def bulk_insert(self, events):
    tasks = [
        self.data_client.insert('events', event)
        for event in events
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### 6. Pagination

```python
async def get_all_events(self, filters, page_size=100):
    skip = 0
    all_events = []
    
    while True:
        events = await self.data_client.query(
            'events',
            filters=filters,
            limit=page_size,
            skip=skip,
            sort={'timestamp': 'asc'}
        )
        
        if not events:
            break
        
        all_events.extend(events)
        skip += page_size
    
    return all_events
```

---

## Security Considerations

### 1. Never Store Secrets

```python
# BAD: Storing sensitive data
await self.data_client.insert('config', {
    'api_key': 'secret123',  # DON'T DO THIS
    'password': 'pass456'
})

# GOOD: Reference secrets from environment
await self.data_client.insert('config', {
    'api_key_ref': 'env:API_KEY',  # Reference only
    'password_ref': 'vault:db/password'
})
```

### 2. Validate Input

```python
async def store_user_input(self, user_data):
    # Validate before storing
    if not self.validate_schema(user_data):
        raise ValueError("Invalid data schema")
    
    # Sanitize
    sanitized = self.sanitize(user_data)
    
    await self.data_client.insert('user_data', sanitized)
```

### 3. Audit Logging

All operations are automatically logged by AOL-Core Data Broker:

```json
{
  "timestamp": "2025-11-22T12:00:00Z",
  "service": "my-service",
  "operation": "query",
  "collection": "my-service.events",
  "filters": {"event_type": "error"},
  "result_count": 42
}
```

---

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock
from shared.utils.data_client import AOLDataClient

@pytest.fixture
async def data_client():
    client = AOLDataClient("aol-core:50051", "test-service")
    client._stub = AsyncMock()  # Mock gRPC stub
    return client

@pytest.mark.asyncio
async def test_insert(data_client):
    # Mock response
    data_client._stub.StoreData.return_value = AsyncMock(
        success=True,
        document_id="doc123"
    )
    
    doc_id = await data_client.insert('test_collection', {'key': 'value'})
    assert doc_id == "doc123"
```

### Integration Tests

```python
@pytest.mark.integration
async def test_full_data_flow():
    # Start services in docker-compose
    client = AOLDataClient("localhost:50051", "test-service")
    
    # Request collection
    await client.request_collection('test_data')
    
    # Insert
    doc_id = await client.insert('test_data', {'test': True})
    assert doc_id
    
    # Query
    results = await client.query('test_data', filters={'test': True})
    assert len(results) == 1
    assert results[0]['test'] is True
```

---

## Troubleshooting

### Collection Not Found

**Error:** `Collection 'my-collection' not found`

**Solution:** Request collection first:
```python
await self.data_client.request_collection('my-collection')
```

### Permission Denied

**Error:** `Permission denied for collection 'other-service.data'`

**Solution:** Either:
1. Request access in manifest.yaml `accessRequests`
2. Ask the owning service to grant you access
3. Use your own collection instead

### Slow Queries

**Problem:** Queries taking >1 second

**Solutions:**
1. Add indexes for queried fields in manifest.yaml
2. Use projection to limit returned fields
3. Add pagination with `limit` parameter
4. Consider caching frequently accessed data

---

## Migration from Direct Database Access

If migrating from direct database connections:

### Before (Direct Connection)
```python
import asyncpg

conn = await asyncpg.connect('postgresql://...')
await conn.execute('INSERT INTO events (...) VALUES (...)')
results = await conn.fetch('SELECT * FROM events WHERE ...')
```

### After (AOL Data Client)
```python
from shared.utils.data_client import AOLDataClient

client = AOLDataClient('aol-core:50051', 'my-service')
await client.request_collection('events')
await client.insert('events', {...})
results = await client.query('events', filters={...})
```

**Benefits:**
- No connection string management
- Automatic permission enforcement
- Centralized audit logging
- Service can switch databases without code changes
