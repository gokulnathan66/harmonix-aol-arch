"""Structured logging setup"""
import logging
import json
import sys
import os

def setup_logging(config):
    """Setup structured logging"""
    log_config = config.get('spec', {}).get('logging', {}) if isinstance(config, dict) else config.get('monitoring', {}).get('logLevel', 'INFO')
    level = log_config if isinstance(log_config, str) else log_config.get('level', 'INFO')
    format_type = 'json'  # Default to JSON
    
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level))
    
    handler = logging.StreamHandler(sys.stdout)
    
    if format_type == 'json':
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    logger.addHandler(handler)
    
    return logging.getLogger(__name__)

class JsonFormatter(logging.Formatter):
    """JSON log formatter"""
    def format(self, record):
        import socket
        
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service_name': os.getenv('SERVICE_NAME', socket.gethostname()),
        }
        
        # Add any extra fields from the log record
        if hasattr(record, 'service_name'):
            log_entry['service_name'] = record.service_name
        if hasattr(record, 'service_type'):
            log_entry['service_type'] = record.service_type
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

