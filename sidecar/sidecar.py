"""Sidecar for AOL service"""
import logging

class Sidecar:
    """Protocol adapter sidecar for AOL services
    
    Supports all service types: agents, tools, plugins, and general services
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def register_with_aol(self):
        """Register this service with AOL Core"""
        service_name = self.config.get('metadata', {}).get('name') or self.config.get('spec', {}).get('name') or self.config.get('name', 'aol-service')
        service_kind = self.config.get('kind', 'AOLService')
        self.logger.info(f"Registering {service_name} (kind: {service_kind}) with AOL Core")

