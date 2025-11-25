"""Logging Service API - Receives logs from services and forwards to ELK"""
import logging
import json
from datetime import datetime
from aiohttp import web
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LoggingService:
    """Handles log ingestion and forwarding"""
    
    def __init__(self):
        self.log_buffer = []
        self.max_buffer_size = 1000
    
    async def ingest_log(self, log_entry: Dict[str, Any]):
        """Ingest a log entry"""
        # In a production system, this would forward to ELK stack
        # For now, we'll just log it and optionally buffer it
        self.log_buffer.append(log_entry)
        
        # Keep buffer size manageable
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size:]
        
        # Log to stdout (will be picked up by Filebeat)
        logger.info(f"Log ingested: {json.dumps(log_entry)}")
    
    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            'format': 'json',
            'level': 'INFO',
            'endpoint': '/api/logging/log'
        }

def setup_logging_service_api(app: web.Application, logging_service: LoggingService):
    """Setup logging service API endpoints"""
    
    async def ingest_log(request):
        """POST /api/logging/log - Submit structured logs"""
        try:
            log_entry = await request.json()
            
            # Validate log entry
            if not isinstance(log_entry, dict):
                return web.json_response({'error': 'Log entry must be a JSON object'}, status=400)
            
            # Add metadata
            log_entry['ingested_at'] = str(datetime.utcnow())
            log_entry['ingested_by'] = 'aol-core'
            
            await logging_service.ingest_log(log_entry)
            
            return web.json_response({'success': True})
        except Exception as e:
            logger.error(f"Error ingesting log: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_log_config(request):
        """GET /api/logging/config - Get logging configuration"""
        try:
            config = logging_service.get_log_config()
            return web.json_response(config)
        except Exception as e:
            logger.error(f"Error getting log config: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # Register routes
    app.router.add_post('/api/logging/log', ingest_log)
    app.router.add_get('/api/logging/config', get_log_config)

