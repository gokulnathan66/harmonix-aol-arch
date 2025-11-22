"""AOL Sidecar Template - Health checking and metrics"""
import asyncio
import logging
from aiohttp import web
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

class AOLSidecar:
    """Sidecar for health checks and metrics"""
    
    def __init__(self, health_port=50200):
        self.health_port = health_port
        self.app = web.Application()
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/metrics', self.metrics_handler)
    
    async def health_handler(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'service': 'sidecar'
        })
    
    async def metrics_handler(self, request):
        """Prometheus metrics endpoint"""
        return web.Response(
            body=generate_latest(),
            content_type=CONTENT_TYPE_LATEST
        )
    
    async def start(self):
        """Start sidecar server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.health_port)
        await site.start()
        logger.info(f"Sidecar started on port {self.health_port}")
        
        # Keep running
        await asyncio.Event().wait()

if __name__ == '__main__':
    sidecar = AOLSidecar()
    asyncio.run(sidecar.start())

