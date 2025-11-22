# Logging Configuration

This document describes the logging architecture for AOL applications, specifically focusing on how to achieve centralized logging with the ELK stack (Elasticsearch, Logstash, Kibana) while maintaining local Docker logs for development convenience.

## Architecture

The recommended approach uses a "Sidecar" or "Log Shipper" pattern:

1.  **Services** (e.g., your agents, core) write logs to `stdout`/`stderr`.
2.  **Docker** captures these logs and stores them in local JSON files (default behavior).
3.  **Filebeat** (a lightweight shipper) mounts the Docker log directory, reads the new log lines, and ships them to **Logstash**.
4.  **Logstash** processes, filters, and enriches the logs before sending them to **Elasticsearch**.
5.  **Kibana** visualizes the logs.

This setup allows you to use `docker logs <container>` for immediate debugging while also having long-term, searchable logs in Kibana.

## Implementation Steps

### 1. Filebeat Configuration

Create a `filebeat.yml` configuration file (e.g., in `monitoring/elk/filebeat/`):

```yaml
filebeat.inputs:
- type: container
  paths:
    - /var/lib/docker/containers/*/*.log

processors:
  - add_docker_metadata:
      host: "unix:///var/run/docker.sock"

output.logstash:
  hosts: ["logstash:5044"]
```

### 2. Docker Compose Service

Add the `filebeat` service to your `docker-compose.yml`. It requires root privileges to read Docker logs.

```yaml
  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    container_name: filebeat
    hostname: filebeat
    user: root
    volumes:
      - ./monitoring/elk/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - your-network-name
    depends_on:
      - logstash
    restart: unless-stopped
```

### 3. Logstash Configuration

Ensure your `logstash.conf` has a `beats` input configured:

```ruby
input {
  beats {
    port => 5044
  }
  # ... other inputs
}
```

## Structured Logging

For best results, your Python services should log in JSON format. This allows Logstash and Elasticsearch to parse fields like `level`, `timestamp`, `service`, and `trace_id` automatically.

Use the `shared.utils.logging` module provided in the template:

```python
from shared.utils.logging import setup_logging

logger = setup_logging({
    'spec': {
        'logging': {
            'level': 'INFO',
            'format': 'json'
        }
    }
})

logger.info("Processing started", extra={'request_id': '123'})
```
