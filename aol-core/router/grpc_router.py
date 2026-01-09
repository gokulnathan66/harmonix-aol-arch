"""gRPC request router"""

import grpc
import logging
from typing import Dict


class GRPCRouter:
    """Routes gRPC requests to appropriate services"""

    def __init__(self, config, registry):
        self.config = config
        self.registry = registry
        self.logger = logging.getLogger(__name__)

    def register_services(self, server):
        """Register AOL Core services with gRPC server"""
        # This method is kept for compatibility but actual registration
        # is done in main.py after server creation
        pass
