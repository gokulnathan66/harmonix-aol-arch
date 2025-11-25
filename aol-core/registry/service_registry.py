"""Service registry for AOL Core"""
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

@dataclass
class ServiceInstance:
    """Represents a registered service instance"""
    name: str
    version: str
    host: str
    grpc_port: int
    health_port: int
    metrics_port: int
    manifest: Dict
    status: str  # "healthy", "unhealthy", "starting"
    last_heartbeat: datetime
    service_id: str
    
class ServiceRegistry:
    """Central registry for all services in the AOL mesh"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.services: Dict[str, List[ServiceInstance]] = {}
        self.lock = asyncio.Lock()
    
    async def register_service(self, instance: ServiceInstance) -> bool:
        """Register a new service instance"""
        async with self.lock:
            service_name = instance.name
            
            if service_name not in self.services:
                self.services[service_name] = []
            
            # Check for port conflicts
            if self._has_port_conflict(instance):
                self.logger.error(f"Port conflict detected for service {service_name}")
                return False
            
            # Validate manifest
            if not self._validate_manifest(instance.manifest):
                self.logger.error(f"Invalid manifest for service {service_name}")
                return False
            
            self.services[service_name].append(instance)
            self.logger.info(f"Registered service: {service_name}:{instance.version} on port {instance.grpc_port}")
            return True
    
    async def deregister_service(self, service_name: str, service_id: str):
        """Remove a service instance"""
        async with self.lock:
            if service_name in self.services:
                self.services[service_name] = [
                    s for s in self.services[service_name]
                    if s.service_id != service_id
                ]
                self.logger.info(f"Deregistered service: {service_name} ({service_id})")
    
    async def get_service(self, service_name: str) -> Optional[ServiceInstance]:
        """Get a healthy service instance (load balanced)"""
        async with self.lock:
            instances = self.services.get(service_name, [])
            healthy_instances = [s for s in instances if s.status == "healthy"]
            
            if not healthy_instances:
                return None
            
            # Simple round-robin
            return healthy_instances[0]
    
    async def list_services(self) -> Dict[str, List[ServiceInstance]]:
        """List all registered services"""
        async with self.lock:
            return self.services.copy()
    
    async def update_service_health(self, service_name: str, service_id: str, status: str):
        """Update service health status"""
        async with self.lock:
            if service_name in self.services:
                for service in self.services[service_name]:
                    if service.service_id == service_id:
                        service.status = status
                        service.last_heartbeat = datetime.utcnow()
                        break
    
    def _has_port_conflict(self, instance: ServiceInstance) -> bool:
        """Check if ports are already in use"""
        for service_list in self.services.values():
            for service in service_list:
                if (service.grpc_port == instance.grpc_port or
                    service.health_port == instance.health_port or
                    service.metrics_port == instance.metrics_port):
                    return True
        return False
    
    def _validate_manifest(self, manifest: Dict) -> bool:
        """Validate service manifest structure"""
        required_fields = ['kind', 'apiVersion', 'metadata', 'spec']
        return all(field in manifest for field in required_fields)

