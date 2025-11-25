# Consul server configuration
datacenter = "aol-core-dc1"
data_dir = "/consul/data"
log_level = "INFO"

# Enable service mesh (Consul Connect)
connect {
  enabled = true
}

# UI configuration
ui_config {
  enabled = true
}

# Performance tuning
performance {
  raft_multiplier = 1
}

# Enable script checks
enable_script_checks = true

# TLS configuration (production)
# tls {
#   defaults {
#     verify_incoming = true
#     verify_outgoing = true
#     ca_file = "/consul/config/ca.pem"
#     cert_file = "/consul/config/server.pem"
#     key_file = "/consul/config/server-key.pem"
#   }
# }

