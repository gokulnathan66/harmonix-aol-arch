"""Proto Registry API - Serves proto files for all services"""

import logging
from pathlib import Path
from aiohttp import web
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProtoRegistry:
    """Manages proto file storage and retrieval"""

    def __init__(self, proto_storage_path: str = "/tmp/proto-registry"):
        self.proto_storage_path = Path(proto_storage_path)
        self.proto_storage_path.mkdir(parents=True, exist_ok=True)
        self.proto_files: Dict[str, Dict[str, str]] = (
            {}
        )  # {service_name: {filename: content}}

    def register_proto(self, service_name: str, filename: str, content: str):
        """Register a proto file for a service"""
        if service_name not in self.proto_files:
            self.proto_files[service_name] = {}

        self.proto_files[service_name][filename] = content

        # Also save to disk
        service_dir = self.proto_storage_path / service_name
        service_dir.mkdir(parents=True, exist_ok=True)
        (service_dir / filename).write_text(content)

        logger.info(f"Registered proto file {filename} for service {service_name}")

    def get_proto(self, service_name: str, filename: str) -> Optional[str]:
        """Get proto file content"""
        if service_name in self.proto_files:
            return self.proto_files[service_name].get(filename)

        # Try to load from disk
        proto_file = self.proto_storage_path / service_name / filename
        if proto_file.exists():
            return proto_file.read_text()

        return None

    def list_protos(self, service_name: Optional[str] = None) -> Dict:
        """List all proto files"""
        if service_name:
            if service_name in self.proto_files:
                return {service_name: list(self.proto_files[service_name].keys())}
            # Check disk
            service_dir = self.proto_storage_path / service_name
            if service_dir.exists():
                return {service_name: [f.name for f in service_dir.glob("*.proto")]}
            return {}

        # List all services
        result = {}
        for svc_name in self.proto_files.keys():
            result[svc_name] = list(self.proto_files[svc_name].keys())

        # Also check disk for services not in memory
        for service_dir in self.proto_storage_path.iterdir():
            if service_dir.is_dir() and service_dir.name not in result:
                result[service_dir.name] = [f.name for f in service_dir.glob("*.proto")]

        return result


def setup_proto_registry_api(app: web.Application, proto_registry: ProtoRegistry):
    """Setup proto registry API endpoints"""

    async def get_proto(request):
        """GET /api/proto/{service_name}/{filename} - Get proto file"""
        try:
            service_name = request.match_info["service_name"]
            filename = request.match_info["filename"]

            content = proto_registry.get_proto(service_name, filename)

            if not content:
                return web.json_response(
                    {
                        "error": f"Proto file {filename} not found for service {service_name}"
                    },
                    status=404,
                )

            return web.Response(
                text=content,
                content_type="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            logger.error(f"Error getting proto file: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def list_protos(request):
        """GET /api/proto/list - List all proto files"""
        try:
            service_name = request.query.get("service")
            protos = proto_registry.list_protos(service_name=service_name)
            return web.json_response(protos)
        except Exception as e:
            logger.error(f"Error listing protos: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def upload_proto(request):
        """POST /api/proto/{service_name}/{filename} - Upload proto file"""
        try:
            service_name = request.match_info["service_name"]
            filename = request.match_info["filename"]

            if not filename.endswith(".proto"):
                return web.json_response(
                    {"error": "File must have .proto extension"}, status=400
                )

            content = await request.text()
            proto_registry.register_proto(service_name, filename, content)

            return web.json_response(
                {"success": True, "service_name": service_name, "filename": filename}
            )
        except Exception as e:
            logger.error(f"Error uploading proto file: {e}")
            return web.json_response({"error": str(e)}, status=500)

    # Register routes
    app.router.add_get("/api/proto/list", list_protos)
    app.router.add_get("/api/proto/{service_name}/{filename}", get_proto)
    app.router.add_post("/api/proto/{service_name}/{filename}", upload_proto)
