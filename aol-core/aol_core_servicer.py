"""AOL Core gRPC servicer implementation"""

import grpc
import logging
import uuid
from datetime import datetime
from google.protobuf.timestamp_pb2 import Timestamp

# These will be generated from proto files
# Import will fail until protobuf files are generated
try:
    import aol_service_pb2
    import aol_service_pb2_grpc
except ImportError:
    # Create placeholder classes for development
    class Placeholder:
        pass

    aol_service_pb2 = Placeholder()
    aol_service_pb2_grpc = Placeholder()


class AOLCoreServicer:
    """gRPC service implementation for AOL Core"""

    def __init__(self, registry, event_store=None):
        self.registry = registry
        self.event_store = event_store
        self.logger = logging.getLogger(__name__)

    async def RegisterService(self, request, context):
        """Handle service registration"""
        if not aol_service_pb2:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            return None

        try:
            from registry.service_registry import ServiceInstance

            manifest = {
                "kind": request.manifest.kind,
                "apiVersion": request.manifest.api_version,
                "metadata": {
                    "name": request.manifest.metadata.name,
                    "version": request.manifest.metadata.version,
                    "labels": dict(request.manifest.metadata.labels),
                },
                "spec": {
                    "endpoints": {
                        "grpc": request.manifest.spec.endpoints.grpc,
                        "health": request.manifest.spec.endpoints.health,
                        "metrics": request.manifest.spec.endpoints.metrics,
                    }
                },
            }

            instance = ServiceInstance(
                name=request.manifest.metadata.name,
                version=request.manifest.metadata.version,
                host=request.host,
                grpc_port=request.grpc_port,
                health_port=request.health_port,
                metrics_port=request.metrics_port,
                manifest=manifest,
                status="starting",
                last_heartbeat=datetime.utcnow(),
                service_id=str(uuid.uuid4()),
            )

            success = await self.registry.register_service(instance)

            # Track registration event
            if success and self.event_store:
                from event_store import Event, EventType

                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.SERVICE_REGISTERED,
                    timestamp=datetime.utcnow(),
                    service_name=instance.name,
                    service_id=instance.service_id,
                    metadata={"host": instance.host, "grpc_port": instance.grpc_port},
                )
                await self.event_store.add_event(event)

            return aol_service_pb2.RegisterResponse(
                success=success,
                service_id=instance.service_id if success else "",
                error="" if success else "Registration failed",
            )
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return aol_service_pb2.RegisterResponse(success=False, error=str(e))

    async def DeregisterService(self, request, context):
        """Handle service deregistration"""
        if not aol_service_pb2:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            return None

        try:
            await self.registry.deregister_service(
                request.service_name, request.service_id
            )

            # Track deregistration event
            if self.event_store:
                from event_store import Event, EventType

                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.SERVICE_DEREGISTERED,
                    timestamp=datetime.utcnow(),
                    service_name=request.service_name,
                    service_id=request.service_id,
                )
                await self.event_store.add_event(event)

            return aol_service_pb2.DeregisterResponse(success=True)
        except Exception as e:
            self.logger.error(f"Deregistration error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return aol_service_pb2.DeregisterResponse(success=False)

    async def ListServices(self, request, context):
        """List all registered services"""
        if not aol_service_pb2:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            return None

        try:
            services = await self.registry.list_services()
            service_infos = []

            for service_name, instances in services.items():
                for instance in instances:
                    if request.filter_type:
                        service_type = (
                            instance.manifest.get("metadata", {})
                            .get("labels", {})
                            .get("aol.service.type")
                        )
                        if service_type != request.filter_type:
                            continue

                    timestamp = Timestamp()
                    timestamp.FromDatetime(instance.last_heartbeat)

                    service_infos.append(
                        aol_service_pb2.ServiceInfo(
                            name=instance.name,
                            version=instance.version,
                            host=instance.host,
                            grpc_port=instance.grpc_port,
                            status=instance.status,
                            registered_at=timestamp,
                        )
                    )

            return aol_service_pb2.ListServicesResponse(services=service_infos)
        except Exception as e:
            self.logger.error(f"List services error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return aol_service_pb2.ListServicesResponse()

    async def GetService(self, request, context):
        """Get specific service details"""
        if not aol_service_pb2:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            return None

        try:
            service = await self.registry.get_service(request.service_name)

            if not service:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return aol_service_pb2.GetServiceResponse()

            timestamp = Timestamp()
            timestamp.FromDatetime(service.last_heartbeat)

            return aol_service_pb2.GetServiceResponse(
                service=aol_service_pb2.ServiceInfo(
                    name=service.name,
                    version=service.version,
                    host=service.host,
                    grpc_port=service.grpc_port,
                    status=service.status,
                    registered_at=timestamp,
                )
            )
        except Exception as e:
            self.logger.error(f"Get service error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return aol_service_pb2.GetServiceResponse()

    async def ReportHealth(self, request, context):
        """Handle health reports from services"""
        if not aol_service_pb2:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            return None

        try:
            await self.registry.update_service_health(
                request.service_name,
                request.service_name,  # Using service_name as service_id fallback
                request.status,
            )

            return aol_service_pb2.HealthAck(received=True)
        except Exception as e:
            self.logger.error(f"Health report error: {e}")
            return aol_service_pb2.HealthAck(received=False)

    async def Route(self, request, context):
        """Route a request to target service"""
        if not aol_service_pb2:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            return None

        try:
            # Extract source service from metadata if available
            source_service = None
            if hasattr(context, "invocation_metadata"):
                for key, value in context.invocation_metadata():
                    if key == "source-service":
                        source_service = value
                        break

            service = await self.registry.get_service(request.target_service)
            success = service is not None

            if not service:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                response = aol_service_pb2.RouteResponse(
                    success=False, error=f"Service {request.target_service} not found"
                )
            else:
                # In a real implementation, forward the request to the service
                # For now, return a placeholder response
                response = aol_service_pb2.RouteResponse(
                    success=True, response=b"routed"
                )

            # Track route event
            if self.event_store:
                from event_store import Event, EventType

                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.ROUTE_CALLED,
                    timestamp=datetime.utcnow(),
                    source_service=source_service or "unknown",
                    target_service=request.target_service,
                    method=request.method,
                    success=success,
                )
                await self.event_store.add_event(event)

            return response
        except Exception as e:
            self.logger.error(f"Routing error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return aol_service_pb2.RouteResponse(success=False, error=str(e))
