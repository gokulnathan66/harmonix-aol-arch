# Enhanced Consul server configuration for AOL
# Based on: Consul 1.22 security and telemetry improvements (2025)

datacenter = "heart-pulse-dc1"
data_dir = "/consul/data"
log_level = "INFO"

# Enable service mesh (Consul Connect) with mTLS
connect {
  enabled = true
  
  # CA configuration for automatic mTLS
  ca_config {
    # Use built-in CA for development
    # For production, use external CA like Vault
  }
  
  # Proxy defaults for service mesh
  proxy_defaults {
    # Enable transparent proxy for automatic traffic interception
    config {
      protocol = "grpc"
    }
  }
}

# UI configuration with metrics integration
ui_config {
  enabled = true
  
  # Enable built-in metrics dashboard
  metrics_provider = "prometheus"
  metrics_proxy {
    base_url = "http://prometheus:9090"
  }
}

# Performance tuning for multi-agent workloads
performance {
  raft_multiplier = 1
  # Increase for high-throughput agent scenarios
  leave_drain_time = "5s"
  rpc_hold_timeout = "7s"
}

# Enable script and HTTP checks
enable_script_checks = true
enable_local_script_checks = true

# Telemetry configuration for observability
telemetry {
  # Prometheus metrics endpoint
  prometheus_retention_time = "60s"
  
  # StatsD for real-time metrics (optional)
  # statsd_address = "statsd:8125"
  
  # Enable detailed metrics
  disable_hostname = true
  
  # Metrics prefix for AOL
  metrics_prefix = "aol.consul"
}

# HTTP API configuration
ports {
  http = 8500
  grpc = 8502
  grpc_tls = 8503
}

# Client address binding
client_addr = "0.0.0.0"

# Enable gRPC for Connect proxies
# Critical for AI model traffic security
addresses {
  grpc = "0.0.0.0"
}

# Service mesh proxy configuration
# Secures AI model traffic at scale (Red Hat, 2025)
proxy {
  # Allow proxies to bind to all interfaces
  allow_managed_api_registration = true
  
  # Defaults for sidecar proxies
  defaults {
    # Enable access logs for debugging
    access_logs {
      enabled = true
      path = "/consul/logs/access.log"
    }
  }
}

# ACL configuration (enable in production)
acl {
  enabled = false  # Set to true in production
  default_policy = "allow"  # Set to "deny" in production
  enable_token_persistence = true
}

# Autopilot for cluster management
autopilot {
  cleanup_dead_servers = true
  last_contact_threshold = "200ms"
  max_trailing_logs = 250
  server_stabilization_time = "10s"
}

# Rate limiting for API protection
limits {
  http_max_conns_per_client = 200
  rpc_rate = 4096
  rpc_max_burst = 4096
}

# =============================================================================
# TLS Configuration (Production)
# Enable mTLS for secure AI model traffic following Red Hat's 2025 security playbook
# =============================================================================
# tls {
#   defaults {
#     verify_incoming = true
#     verify_outgoing = true
#     verify_server_hostname = true
#     ca_file = "/consul/config/ca.pem"
#     cert_file = "/consul/config/server.pem"
#     key_file = "/consul/config/server-key.pem"
#   }
#   
#   # Internal RPC TLS
#   internal_rpc {
#     verify_incoming = true
#     verify_server_hostname = true
#   }
#   
#   # gRPC TLS for service mesh
#   grpc {
#     verify_incoming = true
#     ca_file = "/consul/config/ca.pem"
#     cert_file = "/consul/config/server.pem"
#     key_file = "/consul/config/server-key.pem"
#   }
# }

# =============================================================================
# Service Intentions (Zero-Trust Security)
# Define which services can communicate
# =============================================================================
# Example intention (apply via CLI or API):
# consul intention create -allow aol-core '*'
# consul intention create -allow agent-* aol-core
# consul intention create -deny '*' '*'  # Default deny

# =============================================================================
# Health Check Improvements
# =============================================================================
# Customize health check intervals for AI agents
# check_update_interval = "5s"

# =============================================================================
# Multi-Datacenter Configuration (Future)
# For distributed multi-agent deployments
# =============================================================================
# primary_datacenter = "heart-pulse-dc1"
# 
# # Federate with other datacenters
# retry_join_wan = ["consul-dc2.example.com:8302"]
