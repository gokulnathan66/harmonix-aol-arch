Every individual tool/plugin (agent or service) in your **AOL multi-mesh architecture** should provide a consistent set of files and metadata so that the AOL Core can discover, register, and operate with them in plug-and-play fashion, without configuration conflicts. The following files/templates should be present for each plugin/container:

***

### 1. **Manifest/Descriptor File**

**Required:**  
- `manifest.yaml` or `manifest.json`

**Purpose:**  
Contains metadata, config schema, roles, endpoints, and dependencies for your agent/tool.

**Example:**
```yaml
kind: "AOLAgent"
apiVersion: "v1"
metadata:
  name: "text-critic"
  version: "1.0.2"
  labels:
    agent-type: "critic"
spec:
  endpoints:
    grpc: "50052"
    health: "50100"
  configSchema:
    - name: "model"
      type: "string"
      default: "gpt-4o"
    - name: "maxInputTokens"
      type: "int"
      default: 2048
    - name: "temperature"
      type: "float"
      default: 0.2
  dependencies:
    - tool: "vectorstore"
    - tool: "websearch"
```
*AOL validates this before registering the service to avoid configuration mismatches or port conflicts.*

***

### 2. **gRPC/Protobuf Service Definition**

**Required:**  
- `service.proto` (or similar; might be in a shared repository)

**Purpose:**  
Defines the message and service contracts required for AOL-sidecar interoperability and communication.

**Example Snippet:**
```protobuf
service AgentService {
  rpc Process(Request) returns (Response) {}
  rpc ReportHealth(HealthCheck) returns (HealthStatus) {}
  rpc GetConfig(ConfigRequest) returns (ConfigSpec) {}
}
```
*Ensures every plugin/tool speaks the same "language" to AOL and other agents.*

***

### 3. **Sidecar/Entrypoint Script**

**Required:**  
- `sidecar.py` / `sidecar.js` / `sidecar.go` / etc.

**Purpose:**  
Handles protocol wrapping, registration, health checking, config broadcasting, and communication with AOL Core.

*May be generic/shared across plugins with plugin-specific imports/configs.*

***

### 4. **Business Logic File(s)**

**Required:**  
- `agent.py` / `tool.py` / main entrypoint implementing the agent’s core logic, called by the sidecar.

**Purpose:**  
Contains the functional logic for the agent/tool, responding to gRPC calls and registering methods as specified in `manifest.yaml` and `service.proto`.

***

### 5. **Default Configuration File**

**Required (recommended):**  
- `config.yaml` or `config.json`

**Purpose:**  
Defines runtime parameters (values for `configSchema` fields above), allowing AOL to initialize/run in a conflict-free, reproducible way.

**Example:**
```yaml
model: "gpt-4o"
maxInputTokens: 2048
temperature: 0.2
endpoint: "localhost:50052"
```

***

### 6. **Metrics Endpoint / Health Endpoint**

**Required:**  
- `/metrics` endpoint in code or at specified port for Prometheus/scraping
- `/health` endpoint as defined in manifest

**Purpose:**  
Allows AOL to monitor plugin health and gather observability data for dashboards.

***

### 7. **Data Storage Requirements (Optional)**

**Required for services that need persistent storage:**  
- Declare `dataRequirements` section in manifest.yaml
- Use AOL Data Client library to interact with database **via AOL-Core**
- **NEVER connect directly to database** - all operations routed through AOL-Core Data Broker

**Purpose:**  
Enables plug-and-play data storage without hardcoding database connections. Services declare what collections they need; AOL-Core handles routing, permissions, and access control.

**Example manifest.yaml dataRequirements:**
```yaml
spec:
  dataRequirements:
    enabled: true
    
    # Collections this service will create/own
    collections:
      - name: "my_data"
        description: "Stores my service's data"
        schemaHint:  # Optional: helps with indexing
          id: "string"
          timestamp: "datetime"
          value: "number"
        indexes:
          - fields: ["timestamp"]
            type: "ascending"
    
    # Collections from other services this service needs to access
    accessRequests:
      - collection: "other-service.shared_data"
        permission: "read"  # or "write"
        reason: "Need historical context"
```

**Example usage in agent code:**
```python
from shared.utils.data_client import AOLDataClient

class MyAgent:
    def __init__(self):
        # Initialize data client (connects to AOL-Core, not database)
        self.data_client = AOLDataClient(
            aol_core_endpoint="aol-core:50051",
            service_name="my-service"
        )
        
        # Request collections declared in manifest
        await self.data_client.request_collection('my_data')
    
    async def process(self, data):
        # Store data
        doc_id = await self.data_client.insert('my_data', {
            'id': data['id'],
            'timestamp': datetime.utcnow().isoformat(),
            'value': data['value']
        })
        
        # Query data
        results = await self.data_client.query(
            'my_data',
            filters={'value': {'$gt': 100}},
            limit=10
        )
```

**Data Flow:**
```
Service → AOL-Core (Data Broker) → Database Service → Physical DB
         ↑ Permission Check
         ↑ Collection Registry
         ↑ Audit Logging
```

**Key Principles:**
1. **Namespace Isolation:** Collections are namespaced as `{service-name}.{collection-name}`
2. **Permission-Based Sharing:** Services can grant read/write access to their collections
3. **Schema-Agnostic:** Store any JSON structure; database adapts dynamically
4. **AOL-Managed:** AOL-Core tracks ownership, enforces permissions, logs access

***

### Summary Table

| File/Endpoint      | Purpose                                                |
|--------------------|--------------------------------------------------------|
| manifest.yaml/json | Plugin metadata, config schema, ports, dependencies, **dataRequirements** |
| service.proto      | Message/service contracts for gRPC                     |
| sidecar.*          | Protocol adapter, registration, route, health          |
| agent/tool.*       | Main business logic                                    |
| config.yaml/json   | Runtime/default configuration                          |
| /metrics endpoint  | Metrics exposure for monitoring                        |
| /health endpoint   | Health check for AOL registry/management               |
| **dataRequirements** | **Data storage needs declaration (optional)**        |

***

**If every tool/plugin/agent container presents these files/templates, the AOL multi-mesh core can auto-discover, validate configs, register, orchestrate, and monitor the ecosystem reliably and plug-and-play, with no ambiguity or schema conflicts**.[1]

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/76332706/016fe821-13e6-4b36-936d-4a00e4dbb95f/AOL-multi-mesh-config-own.md)