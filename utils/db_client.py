"""
Database Client - Uses aol-core to discover database service
"""

import aiohttp
import json
import logging
from typing import List, Dict, Any, Optional
from utils.consul_client import AOLServiceDiscoveryClient

logger = logging.getLogger(__name__)


class DataClientError(Exception):
    """Base exception for data client errors"""

    pass


class PermissionDeniedError(DataClientError):
    """Raised when permission is denied"""

    pass


class CollectionNotFoundError(DataClientError):
    """Raised when collection is not found"""

    pass


class DatabaseClient:
    """Client for services to interact with database via aol-core discovery"""

    def __init__(self, aol_core_endpoint: str = None, service_name: str = None):
        """
        Initialize database client

        Args:
            aol_core_endpoint: AOL-Core endpoint (format: "http://host:port")
            service_name: Name of the service using this client
        """
        import os

        self.aol_core_endpoint = aol_core_endpoint or os.getenv(
            "AOL_CORE_ENDPOINT", "http://aol-core:8080"
        )
        self.service_name = service_name or os.getenv("SERVICE_NAME", "aol-agent")
        self.discovery_client = AOLServiceDiscoveryClient(self.aol_core_endpoint)

        self.session: Optional[aiohttp.ClientSession] = None
        self._requested_collections: set = set()
        self._db_endpoint: Optional[str] = None

    async def _get_db_endpoint(self) -> str:
        """Discover database service endpoint via aol-core"""
        if self._db_endpoint:
            return self._db_endpoint

        instances = await self.discovery_client.discover_service(
            "knowledge-db", healthy_only=True
        )

        if not instances:
            raise DataClientError("No healthy knowledge-db instances found")

        # Use first healthy instance
        instance = instances[0]
        self._db_endpoint = (
            f"http://{instance['address']}:{instance.get('health_port', 8084)}"
        )
        return self._db_endpoint

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close HTTP session and discovery client"""
        if self.session:
            await self.session.close()
            self.session = None
        await self.discovery_client.close()

    async def request_collection(
        self,
        name: str,
        schema_hint: Optional[Dict[str, str]] = None,
        indexes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Request a new collection (or get existing)"""
        full_name = f"{self.service_name}.{name}"

        if full_name in self._requested_collections:
            logger.debug(f"Collection '{full_name}' already requested")
            return full_name

        db_endpoint = await self._get_db_endpoint()
        session = await self._get_session()

        try:
            async with session.post(
                f"{db_endpoint}/api/collections",
                json={
                    "name": full_name,
                    "owner_service": self.service_name,
                    "schema_hint": schema_hint,
                    "indexes": indexes,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self._requested_collections.add(full_name)
                    logger.info(f"Requested collection '{full_name}'")
                    return result.get("collection_id", full_name)
                else:
                    error = await resp.text()
                    raise DataClientError(f"Failed to request collection: {error}")
        except aiohttp.ClientError as e:
            raise DataClientError(f"Network error requesting collection: {e}")

    async def insert(
        self,
        collection: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert a document"""
        full_name = f"{self.service_name}.{collection}"
        db_endpoint = await self._get_db_endpoint()
        session = await self._get_session()

        try:
            async with session.post(
                f"{db_endpoint}/api/collections/{full_name}/insert",
                json={"data": data, "metadata": metadata},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["document_id"]
                elif resp.status == 404:
                    raise CollectionNotFoundError(f"Collection '{full_name}' not found")
                else:
                    error = await resp.text()
                    raise DataClientError(f"Insert failed: {error}")
        except aiohttp.ClientError as e:
            raise DataClientError(f"Network error during insert: {e}")

    async def query(
        self,
        collection: str,
        filters: Optional[Dict[str, Any]] = None,
        projection: Optional[List[str]] = None,
        limit: int = 100,
        skip: int = 0,
        sort: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Query documents"""
        if "." not in collection:
            full_name = f"{self.service_name}.{collection}"
        else:
            full_name = collection

        db_endpoint = await self._get_db_endpoint()
        session = await self._get_session()

        try:
            async with session.post(
                f"{db_endpoint}/api/collections/{full_name}/query",
                json={
                    "filters": filters or {},
                    "projection": projection,
                    "limit": limit,
                    "skip": skip,
                    "sort": sort,
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("documents", [])
                elif resp.status == 404:
                    raise CollectionNotFoundError(f"Collection '{full_name}' not found")
                elif resp.status == 403:
                    raise PermissionDeniedError(
                        f"No permission to access '{full_name}'"
                    )
                else:
                    error = await resp.text()
                    raise DataClientError(f"Query failed: {error}")
        except aiohttp.ClientError as e:
            raise DataClientError(f"Network error during query: {e}")
