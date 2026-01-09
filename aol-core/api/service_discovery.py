"""Service Discovery API - Exposes Consul service discovery through aol-core"""

import logging
from aiohttp import web
from registry.consul_registry import ConsulServiceRegistry

logger = logging.getLogger(__name__)


def _instance_to_discovery_dict(instance):
    """Convert instance to discovery dictionary"""
    return {
        "id": instance.id,
        "name": instance.name,
        "address": instance.address,
        "port": instance.port,
        "health_port": instance.health_port,
        "metrics_port": instance.metrics_port,
        "tags": instance.tags,
        "meta": instance.meta,
        "status": "healthy" if instance.status == "passing" else instance.status,
    }


def _create_discover_service_handler(consul_registry):
    """Create discover service handler"""
    async def discover_service(request):
        """GET /api/discovery/{service_name} - Discover service instances"""
        try:
            service_name = request.match_info["service_name"]
            healthy_only = request.query.get("healthy_only", "true").lower() == "true"

            instances = consul_registry.discover_service(
                service_name, healthy_only=healthy_only
            )

            result = [_instance_to_discovery_dict(inst) for inst in instances]
            return web.json_response({
                "service_name": service_name,
                "instances": result,
                "count": len(result),
            })
        except Exception as e:
            logger.error(f"Error discovering service: {e}")
            return web.json_response({"error": str(e)}, status=500)
    return discover_service


def _create_list_services_handler(consul_registry):
    """Create list services handler"""
    async def list_services(request):
        """GET /api/discovery - List all registered services"""
        try:
            services = consul_registry.list_services()

            result = {
                service_name: {
                    "instances": [
                        {
                            "id": inst.id,
                            "address": inst.address,
                            "port": inst.port,
                            "health_port": inst.health_port,
                            "status": inst.status,
                        }
                        for inst in instances
                    ],
                    "count": len(instances),
                }
                for service_name, instances in services.items()
            }

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error listing services: {e}")
            return web.json_response({"error": str(e)}, status=500)
    return list_services


def _create_get_service_health_handler(consul_registry):
    """Create get service health handler"""
    async def get_service_health(request):
        """GET /api/discovery/{service_name}/health - Get service health status"""
        try:
            service_name = request.match_info["service_name"]

            instances = consul_registry.discover_service(
                service_name, healthy_only=False
            )

            if not instances:
                return web.json_response({"error": "Service not found"}, status=404)

            health_status = [
                {
                    "id": inst.id,
                    "status": inst.status,
                    "address": inst.address,
                    "port": inst.port,
                }
                for inst in instances
            ]

            return web.json_response({
                "service_name": service_name,
                "health_status": health_status
            })
        except Exception as e:
            logger.error(f"Error getting service health: {e}")
            return web.json_response({"error": str(e)}, status=500)
    return get_service_health


def setup_service_discovery_api(
    app: web.Application, consul_registry: ConsulServiceRegistry
):
    """Setup service discovery API endpoints"""
    app.router.add_get("/api/discovery", _create_list_services_handler(consul_registry))
    app.router.add_get("/api/discovery/{service_name}", _create_discover_service_handler(consul_registry))
    app.router.add_get("/api/discovery/{service_name}/health", _create_get_service_health_handler(consul_registry))
