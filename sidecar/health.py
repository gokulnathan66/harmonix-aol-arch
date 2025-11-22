"""Health reporter for AOL agent"""
import logging

class HealthReporter:
    """Reports health status to AOL Core"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def report_health(self, status: str):
        """Report health status"""
        self.logger.debug(f"Reporting health: {status}")

