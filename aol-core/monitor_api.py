"""Monitoring API for AOL Core dashboard"""

import json
import logging
from aiohttp import web, WSMsgType

logger = logging.getLogger(__name__)


def _create_cors_middleware():
    """Create CORS middleware"""
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
    return cors_middleware


def _serialize_event(event):
    """Serialize event for WebSocket broadcast"""
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
    return event_dict


def _instance_to_dict(instance):
    """Convert service instance to dictionary"""
    return {
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


def _create_broadcast_handler(ws_connections):
    """Create broadcast event handler"""
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
    return broadcast_event


def _setup_event_broadcasting(event_store, broadcast_event):
    """Setup event broadcasting"""
    original_add_event = event_store.add_event

    async def new_add_event(event):
        await original_add_event(event)
        try:
            event_dict = _serialize_event(event)
            await broadcast_event(event_dict)
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}", exc_info=True)

    event_store.add_event = new_add_event


def _create_get_services_handler(registry):
    """Create get services handler"""
    async def get_services(request):
        """GET /api/services - List all registered services"""
        try:
            services = await registry.list_services()
            result = [
                _instance_to_dict(instance)
                for service_name, instances in services.items()
                for instance in instances
            ]
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting services: {e}")
            return web.json_response({"error": str(e)}, status=500)
    return get_services


def _create_get_service_handler(registry):
    """Create get service handler"""
    async def get_service(request):
        """GET /api/services/{name} - Get specific service details"""
        try:
            service_name = request.match_info["name"]
            services = await registry.list_services()

            if service_name not in services:
                return web.json_response({"error": "Service not found"}, status=404)

            result = [_instance_to_dict(inst) for inst in services[service_name]]
            return web.json_response(result if len(result) > 1 else result[0])
        except Exception as e:
            logger.error(f"Error getting service: {e}")
            return web.json_response({"error": str(e)}, status=500)
    return get_service


def _create_get_registry_stats_handler(registry):
    """Create get registry stats handler"""
    async def get_registry_stats(request):
        """GET /api/registry/stats - Get registry statistics"""
        try:
            services = await registry.list_services()
            stats = {
                "total_services": sum(len(instances) for instances in services.values()),
                "unique_services": len(services),
                "by_status": {},
                "by_type": {},
            }

            for service_name, instances in services.items():
                for instance in instances:
                    status = instance.status
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                    service_type = (
                        instance.manifest.get("metadata", {})
                        .get("labels", {})
                        .get("aol.service.type", "unknown")
                    )
                    stats["by_type"][service_type] = stats["by_type"].get(service_type, 0) + 1

            return web.json_response(stats)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return web.json_response({"error": str(e)}, status=500)
    return get_registry_stats


def _create_get_events_handler(event_store):
    """Create get events handler"""
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
    return get_events


def _create_get_routes_handler(event_store):
    """Create get routes handler"""
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

            result = [
                {**route_data, "methods": list(route_data["methods"])}
                for route_data in route_map.values()
            ]
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting routes: {e}")
            return web.json_response({"error": str(e)}, status=500)
    return get_routes


async def _send_initial_state(ws, registry):
    """Send initial state to WebSocket client"""
    try:
        services = await registry.list_services()
        initial_data = {"type": "initial_state", "services": []}

        for service_name, instances in services.items():
            for instance in instances:
                initial_data["services"].append({
                    "name": instance.name,
                    "version": instance.version,
                    "host": instance.host,
                    "grpc_port": instance.grpc_port,
                    "status": instance.status,
                    "service_id": instance.service_id,
                })

        await ws.send_str(json.dumps(initial_data))
    except Exception as e:
        logger.error(f"Error sending initial state: {e}")


async def _handle_websocket_messages(ws):
    """Handle WebSocket messages"""
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "ping":
                    await ws.send_str(json.dumps({"type": "pong"}))
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
                break
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


def _create_websocket_handler(registry, ws_connections):
    """Create WebSocket handler"""
    async def websocket_handler(request):
        """WebSocket handler for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        ws_connections.append(ws)
        logger.info(f"WebSocket client connected. Total connections: {len(ws_connections)}")

        await _send_initial_state(ws, registry)

        await _handle_websocket_messages(ws)

        if ws in ws_connections:
            ws_connections.remove(ws)
        logger.info(f"WebSocket client disconnected. Total connections: {len(ws_connections)}")

        return ws
    return websocket_handler


def setup_monitor_api(app: web.Application, registry, event_store):
    """Setup monitoring API routes"""
    app.middlewares.append(_create_cors_middleware())

    ws_connections = []
    broadcast_event = _create_broadcast_handler(ws_connections)
    _setup_event_broadcasting(event_store, broadcast_event)

    app.router.add_get("/api/services", _create_get_services_handler(registry))
    app.router.add_get("/api/services/{name}", _create_get_service_handler(registry))
    app.router.add_get("/api/registry/stats", _create_get_registry_stats_handler(registry))
    app.router.add_get("/api/events", _create_get_events_handler(event_store))
    app.router.add_get("/api/routes", _create_get_routes_handler(event_store))
    app.router.add_get("/ws", _create_websocket_handler(registry, ws_connections))
