"""Consul-based service discovery and registration"""

import consul
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
import socket
import os

logger = logging.getLogger(__name__)


@dataclass
class ServiceInstance:
    """Service instance metadata"""

    id: str
    name: str
    address: str
    port: int
    health_port: int
    metrics_port: int
    tags: List[str]
    meta: Dict[str, str]
    check: Optional[Dict] = None


class ConsulServiceRegistry:
    """Consul-based service discovery and registration"""

    def __init__(self, consul_host=None, consul_port=8500):
        # Get Consul connection from environment or use defaults
        host = (
            consul_host or os.getenv("CONSUL_HTTP_ADDR", "consul-server").split(":")[0]
        )
        port = consul_port

        # Parse port from CONSUL_HTTP_ADDR if present
        consul_addr = os.getenv("CONSUL_HTTP_ADDR", "")
        if ":" in consul_addr:
            parts = consul_addr.split(":")
            if len(parts) == 2:
                host = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    pass

        self.consul = consul.Consul(host=host, port=port)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized Consul registry at {host}:{port}")

    def register_service(self, instance: ServiceInstance) -> bool:
        """Register service with Consul"""
        try:
            # Define health check
            health_check = instance.check or {
                "http": f"http://{instance.address}:{instance.health_port}/health",
                "interval": "10s",
                "timeout": "5s",
                "deregister_critical_service_after": "30s",
            }

            # Register with Consul
            success = self.consul.agent.service.register(
                name=instance.name,
                service_id=instance.id,
                address=instance.address,
                port=instance.port,
                tags=instance.tags,
                check=health_check,
            )

            if success:
                self.logger.info(
                    f"Registered service: {instance.name} ({instance.id}) at {instance.address}:{instance.port}"
                )
            return success

        except Exception as e:
            self.logger.error(f"Failed to register service {instance.name}: {e}")
            return False

    def deregister_service(self, service_id: str) -> bool:
        """Deregister service from Consul"""
        try:
            self.consul.agent.service.deregister(service_id)
            self.logger.info(f"Deregistered service: {service_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to deregister {service_id}: {e}")
            return False

    def discover_service(
        self, service_name: str, healthy_only=True
    ) -> List[ServiceInstance]:
        """Discover service instances from Consul"""
        try:
            index, services = self.consul.health.service(
                service_name, passing=healthy_only
            )

            instances = []
            for service in services:
                s = service["Service"]
                instances.append(
                    ServiceInstance(
                        id=s["ID"],
                        name=s["Service"],
                        address=s["Address"] or s.get("Address", ""),
                        port=s["Port"],
                        health_port=int(s.get("Meta", {}).get("health_port", 0)),
                        metrics_port=int(s.get("Meta", {}).get("metrics_port", 0)),
                        tags=s.get("Tags", []),
                        meta=s.get("Meta", {}),
                    )
                )

            self.logger.info(f"Discovered {len(instances)} instances of {service_name}")
            return instances

        except Exception as e:
            self.logger.error(f"Service discovery failed for {service_name}: {e}")
            return []

    def get_service_config(self, key: str) -> Optional[str]:
        """Get configuration from Consul KV store"""
        try:
            index, data = self.consul.kv.get(key)
            if data:
                return data["Value"].decode("utf-8")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get config {key}: {e}")
            return None

    def set_service_config(self, key: str, value: str) -> bool:
        """Set configuration in Consul KV store"""
        try:
            return self.consul.kv.put(key, value)
        except Exception as e:
            self.logger.error(f"Failed to set config {key}: {e}")
            return False

    def watch_service(self, service_name: str, callback):
        """Watch for service changes (blocking call)"""
        index = None
        while True:
            try:
                index, services = self.consul.health.service(
                    service_name, index=index, wait="30s"
                )
                callback(services)
            except Exception as e:
                self.logger.error(f"Watch error for {service_name}: {e}")
