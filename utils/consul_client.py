"""Service Discovery Client - Queries aol-core for service discovery"""
import aiohttp
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class AOLServiceDiscoveryClient:
    """Client that queries aol-core for service discovery instead of Consul directly"""
    
    def __init__(self, aol_core_endpoint: str = None):
        """
        Initialize service discovery client
        
        Args:
            aol_core_endpoint: aol-core HTTP endpoint (e.g., "http://aol-core:8080")
                             If None, will use environment variable AOL_CORE_ENDPOINT
        """
        import os
        self.aol_core_endpoint = aol_core_endpoint or os.getenv('AOL_CORE_ENDPOINT', 'http://aol-core:8080')
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def discover_service(self, service_name: str, healthy_only: bool = True) -> List[Dict]:
        """
        Discover service instances via aol-core
        
        Args:
            service_name: Name of the service to discover
            healthy_only: Only return healthy instances
        
        Returns:
            List of service instance dictionaries
        """
        session = await self._get_session()
        
        try:
            url = f"{self.aol_core_endpoint}/api/discovery/{service_name}"
            if healthy_only:
                url += "?healthy_only=true"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('instances', [])
                elif resp.status == 404:
                    logger.warning(f"Service {service_name} not found")
                    return []
                else:
                    error = await resp.text()
                    logger.error(f"Error discovering service {service_name}: {error}")
                    return []
        except Exception as e:
            logger.error(f"Error querying aol-core for service discovery: {e}")
            return []
    
    async def list_services(self) -> Dict[str, List[Dict]]:
        """List all registered services"""
        session = await self._get_session()
        
        try:
            url = f"{self.aol_core_endpoint}/api/discovery"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Error listing services: {resp.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error querying aol-core for service list: {e}")
            return {}
    
    async def get_service_health(self, service_name: str) -> Dict:
        """Get health status for a service"""
        session = await self._get_session()
        
        try:
            url = f"{self.aol_core_endpoint}/api/discovery/{service_name}/health"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {'error': f'HTTP {resp.status}'}
        except Exception as e:
            logger.error(f"Error getting service health: {e}")
            return {'error': str(e)}

