"""Docker-based service discovery"""

import docker
import asyncio
import logging
from typing import Dict
import yaml
import os
from datetime import datetime
import uuid


class DockerDiscovery:
    """Discovers services from Docker containers"""

    def __init__(self, config, registry):
        self.config = config
        self.registry = registry
        self.logger = logging.getLogger(__name__)
        self.docker_client = None
        self.running = False

        try:
            docker_socket = (
                config.get("spec", {})
                .get("discovery", {})
                .get("dockerSocket", "/var/run/docker.sock")
            )
            # Check if socket file exists
            if not os.path.exists(docker_socket):
                raise FileNotFoundError(f"Docker socket not found at {docker_socket}")

            # Use DockerClient directly with base_url to bypass environment variable issues
            # This avoids the "http+docker" scheme error that can occur with from_env()
            try:
                # Method 1: Try with unix:// prefix
                base_url = f"unix://{docker_socket}"
                self.docker_client = docker.DockerClient(
                    base_url=base_url, version="auto"
                )
                self.docker_client.ping()
                self.logger.info(
                    f"Docker discovery initialized successfully using socket: {docker_socket}"
                )
                except Exception as e1:
                # Method 2: Try without version (let it auto-detect)
                try:
                    self.docker_client = docker.DockerClient(base_url=base_url)
                    self.docker_client.ping()
                    self.logger.info(
                        f"Docker discovery initialized using socket (no version): {docker_socket}"
                    )
                except Exception:
                    # Method 3: Try with APIClient and wrap it
                    try:
                        api_client = docker.APIClient(base_url=base_url)
                        api_client.ping()
                        # Create DockerClient from the working APIClient
                        self.docker_client = docker.DockerClient(base_url=base_url)
                        self.docker_client.ping()
                        self.logger.info(
                            f"Docker discovery initialized via APIClient: {docker_socket}"
                        )
                    except Exception as e3:
                        # All methods failed
                        raise e1 from e3
        except Exception as e:
            self.logger.warning(
                f"Failed to connect to Docker: {e}. Docker discovery will be disabled."
            )
            self.logger.debug(
                f"Docker connection error details: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            self.docker_client = None

    async def watch_containers(self):
        """Watch for container changes"""
        self.running = True
        label_prefix = (
            self.config.get("spec", {})
            .get("discovery", {})
            .get("labelPrefix", "aol.service")
        )
        refresh_interval = (
            self.config.get("spec", {})
            .get("discovery", {})
            .get("refreshInterval", "10s")
        )

        # Parse interval (e.g., "10s" -> 10)
        interval_seconds = int(refresh_interval.rstrip("s"))

        while self.running:
            try:
                await self._discover_services(label_prefix)
            except Exception as e:
                self.logger.error(f"Discovery error: {e}")

            await asyncio.sleep(interval_seconds)

    async def _discover_services(self, label_prefix: str):
        """Discover services from Docker labels"""
        # Fallback to Docker CLI if docker_client is not available
        if not self.docker_client:
            await self._discover_via_cli(label_prefix)
            return

        try:
            containers = self.docker_client.containers.list(
                filters={"status": "running"}
            )

            for container in containers:
                labels = container.labels

                # Check if container is an AOL service
                if f"{label_prefix}" in labels and labels[f"{label_prefix}"] == "true":
                    service_name = labels.get(f"{label_prefix}.name")

                    if service_name:
                        await self._register_from_container(
                            container, service_name, labels
                        )

        except Exception as e:
            self.logger.error(f"Container discovery failed: {e}")
            # Fallback to CLI method
            await self._discover_via_cli(label_prefix)

    async def _discover_via_cli(self, label_prefix: str):
        """Discover services using Docker HTTP API directly via Unix socket"""
        try:
            import json
            import socket
            import urllib.parse

            docker_socket = (
                self.config.get("spec", {})
                .get("discovery", {})
                .get("dockerSocket", "/var/run/docker.sock")
            )

            # Get list of containers using Docker HTTP API
            containers = await self._docker_api_request(
                "GET", "/containers/json?all=false"
            )

            if not containers:
                return

            for container in containers:
                try:
                    container_id = container.get("Id", "")
                    container_name = container.get("Names", [""])[0].lstrip("/")

                    if not container_id:
                        continue

                    # Get container details including labels and ports
                    container_details = await self._docker_api_request(
                        "GET", f"/containers/{container_id}/json"
                    )

                    if not container_details:
                        continue

                    labels = container_details.get("Config", {}).get("Labels", {})
                    ports = container_details.get("NetworkSettings", {}).get(
                        "Ports", {}
                    )

                    # Check if container is an AOL service
                    if (
                        f"{label_prefix}" in labels
                        and labels[f"{label_prefix}"] == "true"
                    ):
                        service_name = labels.get(f"{label_prefix}.name")

                        if service_name:
                            await self._register_from_labels(
                                service_name, labels, ports, container_name
                            )

                except Exception as e:
                    self.logger.debug(
                        f"Error processing container {container.get('Names', ['unknown'])[0]}: {e}"
                    )
                    continue

        except Exception as e:
            self.logger.error(f"HTTP API-based discovery failed: {e}")

    async def _docker_api_request(self, method: str, path: str):
        """Make HTTP request to Docker API via Unix socket using aiohttp"""
        try:
            import aiohttp
            import json

            docker_socket = (
                self.config.get("spec", {})
                .get("discovery", {})
                .get("dockerSocket", "/var/run/docker.sock")
            )

            # Use aiohttp with Unix connector
            connector = aiohttp.UnixConnector(path=docker_socket)
            url = f"http://localhost{path}"

            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.request(method, url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        self.logger.debug(
                            f"Docker API request failed: {response.status} for {path}"
                        )
                        return None

        except ImportError:
            # Fallback to socket-based approach if aiohttp not available
            return await self._docker_api_request_socket(method, path)
        except Exception as e:
            self.logger.debug(f"Docker API request failed for {path}: {e}")
            return None

    async def _docker_api_request_socket(self, method: str, path: str):
        """Fallback: Make HTTP request to Docker API via Unix socket using raw sockets"""
        import json
        import socket
        import asyncio

        docker_socket = (
            self.config.get("spec", {})
            .get("discovery", {})
            .get("dockerSocket", "/var/run/docker.sock")
        )

        # Build HTTP request
        request = (
            f"{method} {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        )

        try:
            # Run socket operations in executor to avoid blocking
            loop = asyncio.get_event_loop()

            def _make_request():
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(docker_socket)
                sock.sendall(request.encode())

                response_data = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                sock.close()
                return response_data

            response_data = await loop.run_in_executor(None, _make_request)

            # Parse HTTP response
            response_str = response_data.decode("utf-8", errors="ignore")
            header_end = response_str.find("\r\n\r\n")
            if header_end == -1:
                return None

            body = response_str[header_end + 4 :]
            headers = response_str[:header_end]

            # Check status code
            status_line = headers.split("\r\n")[0]
            if "200" not in status_line:
                return None

            # Parse JSON body
            if body.strip():
                return json.loads(body)
            return None

        except Exception as e:
            self.logger.debug(f"Docker API socket request failed for {path}: {e}")
            return None

    async def _register_from_labels(
        self, service_name: str, labels: Dict, ports: Dict, container_name: str
    ):
        """Register service from labels and port info"""
        try:
            # Extract port information from labels or ports
            grpc_port = int(labels.get(f"aol.service.grpc_port", "0"))
            health_port = int(labels.get(f"aol.service.health_port", "0"))
            metrics_port = int(labels.get(f"aol.service.metrics_port", "0"))

            # Extract ports from Docker port mappings
            exposed_ports = []
            for container_port, host_mappings in ports.items():
                if host_mappings:
                    host_port = int(host_mappings[0]["HostPort"])
                    exposed_ports.append(host_port)

            # Match ports by known patterns
            if grpc_port == 0:
                for port in exposed_ports:
                    if 50051 <= port <= 50099:
                        grpc_port = port
                        break

            if health_port == 0:
                for port in exposed_ports:
                    if 50201 <= port <= 50299:
                        health_port = port
                        break

            if metrics_port == 0:
                for port in exposed_ports:
                    if (8080 <= port <= 8099) or port == 9090:
                        metrics_port = port
                        break

            # Create manifest from labels
            manifest = {
                "kind": labels.get("aol.service.type", "AOLService"),
                "apiVersion": "v1",
                "metadata": {
                    "name": service_name,
                    "version": labels.get("aol.service.version", "1.0.0"),
                    "labels": {k: v for k, v in labels.items() if k.startswith("aol.")},
                },
                "spec": {
                    "endpoints": {
                        "grpc": grpc_port,
                        "health": health_port,
                        "metrics": metrics_port,
                    }
                },
            }

            from registry.service_registry import ServiceInstance

            instance = ServiceInstance(
                name=service_name,
                version=manifest["metadata"]["version"],
                host=container_name,
                grpc_port=grpc_port,
                health_port=health_port,
                metrics_port=metrics_port,
                manifest=manifest,
                status="starting",
                last_heartbeat=datetime.utcnow(),
                service_id=str(uuid.uuid4()),
            )

            await self.registry.register_service(instance)
            self.logger.info(
                f"Registered service via CLI: {service_name} on port {grpc_port}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to register service {service_name} from labels: {e}"
            )

    async def _register_from_container(
        self, container, service_name: str, labels: Dict
    ):
        """Register a service from container information"""
        try:
            # Extract port information from labels or container ports
            grpc_port = int(labels.get("aol.service.grpc_port", "0"))
            health_port = int(labels.get("aol.service.health_port", "0"))
            metrics_port = int(labels.get("aol.service.metrics_port", "0"))

            # If ports not in labels, try to extract from container exposed ports
            if grpc_port == 0 or health_port == 0 or metrics_port == 0:
                ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
                exposed_ports = []

                # Collect all exposed host ports
                for port_map in ports.values():
                    if port_map:
                        host_port = int(port_map[0]["HostPort"])
                        exposed_ports.append(host_port)

                # Match ports by known patterns
                if grpc_port == 0:
                    # gRPC ports typically in 50051-50099 range
                    for port in exposed_ports:
                        if 50051 <= port <= 50099:
                            grpc_port = port
                            break

                if health_port == 0:
                    # Health ports typically in 50201-50299 range
                    for port in exposed_ports:
                        if 50201 <= port <= 50299:
                            health_port = port
                            break

                if metrics_port == 0:
                    # Metrics ports typically 8080-8099 or 9090
                    for port in exposed_ports:
                        if (8080 <= port <= 8099) or port == 9090:
                            metrics_port = port
                            break

            # Create manifest from labels
            manifest = {
                "kind": labels.get("aol.service.type", "AOLService"),
                "apiVersion": "v1",
                "metadata": {
                    "name": service_name,
                    "version": labels.get("aol.service.version", "1.0.0"),
                    "labels": {k: v for k, v in labels.items() if k.startswith("aol.")},
                },
                "spec": {
                    "endpoints": {
                        "grpc": grpc_port,
                        "health": health_port,
                        "metrics": metrics_port,
                    }
                },
            }

            # Get container IP
            host = container.name  # Use container name as hostname

            from registry.service_registry import ServiceInstance

            instance = ServiceInstance(
                name=service_name,
                version=manifest["metadata"]["version"],
                host=host,
                grpc_port=grpc_port,
                health_port=health_port,
                metrics_port=metrics_port,
                manifest=manifest,
                status="starting",
                last_heartbeat=datetime.utcnow(),
                service_id=str(uuid.uuid4()),
            )

            await self.registry.register_service(instance)

        except Exception as e:
            self.logger.error(f"Failed to register container {container.name}: {e}")

    def stop(self):
        """Stop discovery"""
        self.running = False
