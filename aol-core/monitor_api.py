"""Monitoring API for AOL Core dashboard"""

import json
import logging
from typing import Dict, List
from aiohttp import web, WSMsgType
from datetime import datetime

logger = logging.getLogger(__name__)


def setup_monitor_api(app: web.Application, registry, event_store):
    """Setup monitoring API routes"""

    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            return web.Response(
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                }
            )
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    app.middlewares.append(cors_middleware)

    # WebSocket connections
    ws_connections = []

    async def broadcast_event(event_dict):
        """Broadcast event to all WebSocket connections"""
        message = json.dumps({"type": "event", "data": event_dict})
        disconnected = []
        for ws in ws_connections:
            try:
                await ws.send_str(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            ws_connections.remove(ws)

    # Override add_event to broadcast events via WebSocket
    original_add_event = event_store.add_event

    async def new_add_event(event):
        await original_add_event(event)
        try:
            event_dict = event.__dict__.copy()
            event_dict["event_type"] = (
                event_dict["event_type"].value
                if hasattr(event_dict["event_type"], "value")
                else str(event_dict["event_type"])
            )
            event_dict["timestamp"] = (
                event_dict["timestamp"].isoformat()
                if hasattr(event_dict["timestamp"], "isoformat")
                else str(event_dict["timestamp"])
            )
            await broadcast_event(event_dict)
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}", exc_info=True)

    event_store.add_event = new_add_event

    # REST API Routes

    async def get_services(request):
        """GET /api/services - List all registered services"""
        try:
            services = await registry.list_services()
            result = []

            for service_name, instances in services.items():
                for instance in instances:
                    result.append(
                        {
                            "name": instance.name,
                            "version": instance.version,
                            "host": instance.host,
                            "grpc_port": instance.grpc_port,
                            "health_port": instance.health_port,
                            "metrics_port": instance.metrics_port,
                            "status": instance.status,
                            "service_id": instance.service_id,
                            "registered_at": instance.last_heartbeat.isoformat(),
                            "manifest": instance.manifest,
                        }
                    )

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting services: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_service(request):
        """GET /api/services/{name} - Get specific service details"""
        try:
            service_name = request.match_info["name"]
            services = await registry.list_services()

            if service_name not in services:
                return web.json_response({"error": "Service not found"}, status=404)

            instances = services[service_name]
            result = []

            for instance in instances:
                result.append(
                    {
                        "name": instance.name,
                        "version": instance.version,
                        "host": instance.host,
                        "grpc_port": instance.grpc_port,
                        "health_port": instance.health_port,
                        "metrics_port": instance.metrics_port,
                        "status": instance.status,
                        "service_id": instance.service_id,
                        "registered_at": instance.last_heartbeat.isoformat(),
                        "manifest": instance.manifest,
                    }
                )

            return web.json_response(result if len(result) > 1 else result[0])
        except Exception as e:
            logger.error(f"Error getting service: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_registry_stats(request):
        """GET /api/registry/stats - Get registry statistics"""
        try:
            services = await registry.list_services()
            stats = {
                "total_services": sum(
                    len(instances) for instances in services.values()
                ),
                "unique_services": len(services),
                "by_status": {},
                "by_type": {},
            }

            for service_name, instances in services.items():
                for instance in instances:
                    # Count by status
                    status = instance.status
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                    # Count by type
                    service_type = (
                        instance.manifest.get("metadata", {})
                        .get("labels", {})
                        .get("aol.service.type", "unknown")
                    )
                    stats["by_type"][service_type] = (
                        stats["by_type"].get(service_type, 0) + 1
                    )

            return web.json_response(stats)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_events(request):
        """GET /api/events - Get historical events"""
        try:
            event_type = request.query.get("type")
            service_name = request.query.get("service")
            limit = int(request.query.get("limit", 100))

            from event_store import EventType

            filter_type = None
            if event_type:
                try:
                    filter_type = EventType(event_type)
                except ValueError:
                    pass

            events = await event_store.get_events(
                event_type=filter_type, service_name=service_name, limit=limit
            )

            result = [event.to_dict() for event in events]
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_routes(request):
        """GET /api/routes - Get communication flow data"""
        try:
            source_service = request.query.get("source")
            target_service = request.query.get("target")
            limit = int(request.query.get("limit", 100))

            events = await event_store.get_route_events(
                source_service=source_service,
                target_service=target_service,
                limit=limit,
            )

            # Aggregate route data
            route_map = {}
            for event in events:
                key = f"{event.source_service}->{event.target_service}"
                if key not in route_map:
                    route_map[key] = {
                        "source": event.source_service,
                        "target": event.target_service,
                        "count": 0,
                        "success_count": 0,
                        "failure_count": 0,
                        "methods": set(),
                    }

                route_map[key]["count"] += 1
                if event.success:
                    route_map[key]["success_count"] += 1
                else:
                    route_map[key]["failure_count"] += 1

                if event.method:
                    route_map[key]["methods"].add(event.method)

            # Convert sets to lists
            result = []
            for route_data in route_map.values():
                route_data["methods"] = list(route_data["methods"])
                result.append(route_data)

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting routes: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def websocket_handler(request):
        """WebSocket handler for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        ws_connections.append(ws)
        logger.info(
            f"WebSocket client connected. Total connections: {len(ws_connections)}"
        )

        # Send initial state
        try:
            services = await registry.list_services()
            initial_data = {"type": "initial_state", "services": []}

            for service_name, instances in services.items():
                for instance in instances:
                    initial_data["services"].append(
                        {
                            "name": instance.name,
                            "version": instance.version,
                            "host": instance.host,
                            "grpc_port": instance.grpc_port,
                            "status": instance.status,
                            "service_id": instance.service_id,
                        }
                    )

            await ws.send_str(json.dumps(initial_data))
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")

        # Keep connection alive and handle messages
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Handle client messages if needed
                    data = json.loads(msg.data)
                    if data.get("type") == "ping":
                        await ws.send_str(json.dumps({"type": "pong"}))
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if ws in ws_connections:
                ws_connections.remove(ws)
            logger.info(
                f"WebSocket client disconnected. Total connections: {len(ws_connections)}"
            )

        return ws

    # Register routes
    app.router.add_get("/api/services", get_services)
    app.router.add_get("/api/services/{name}", get_service)
    app.router.add_get("/api/registry/stats", get_registry_stats)
    app.router.add_get("/api/events", get_events)
    app.router.add_get("/api/routes", get_routes)
    app.router.add_get("/ws", websocket_handler)
