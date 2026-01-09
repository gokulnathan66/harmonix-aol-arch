"""Health check manager"""

import asyncio
import aiohttp
import logging


class HealthManager:
    """Manages health checks for registered services"""

    def __init__(self, config, registry, event_store=None):
        self.config = config
        self.registry = registry
        self.event_store = event_store
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.interval = 30  # seconds
        self.previous_statuses = {}  # Track previous statuses for change detection

    async def run_health_checks(self):
        """Run periodic health checks"""
        self.running = True
        interval = (
            self.config.get("spec", {})
            .get("registry", {})
            .get("healthCheckInterval", "30s")
        )
        self.interval = int(interval.rstrip("s"))

        while self.running:
            try:
                await self._check_all_services()
            except Exception as e:
                self.logger.error(f"Health check error: {e}")

            await asyncio.sleep(self.interval)

    async def _check_all_services(self):
        """Check health of all registered services"""
        services = await self.registry.list_services()

        for service_name, instances in services.items():
            for instance in instances:
                await self._check_service_health(instance)

    async def _check_service_health(self, instance):
        """Check health of a single service"""
        try:
            health_url = f"http://{instance.host}:{instance.health_port}/health"
            old_status = self.previous_statuses.get(
                instance.service_id, instance.status
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_url, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        new_status = "healthy"
                    else:
                        new_status = "unhealthy"
            await self.registry.update_service_health(
                instance.name, instance.service_id, new_status
            )

            # Track health change event
            if old_status != new_status and self.event_store:
                from event_store import Event, EventType
                from datetime import datetime

                event = Event(
                    event_id=f"{instance.service_id}-{datetime.utcnow().isoformat()}",
                    event_type=EventType.HEALTH_CHANGED,
                    timestamp=datetime.utcnow(),
                    service_name=instance.name,
                    service_id=instance.service_id,
                    old_status=old_status,
                    new_status=new_status,
                )
                await self.event_store.add_event(event)

            self.previous_statuses[instance.service_id] = new_status

        except Exception as e:
            self.logger.debug(f"Health check failed for {instance.name}: {e}")
            old_status = self.previous_statuses.get(
                instance.service_id, instance.status
            )
            new_status = "unhealthy"

            await self.registry.update_service_health(
                instance.name, instance.service_id, new_status
            )

            # Track health change event
            if old_status != new_status and self.event_store:
                from event_store import Event, EventType
                from datetime import datetime

                event = Event(
                    event_id=f"{instance.service_id}-{datetime.utcnow().isoformat()}",
                    event_type=EventType.HEALTH_CHANGED,
                    timestamp=datetime.utcnow(),
                    service_name=instance.name,
                    service_id=instance.service_id,
                    old_status=old_status,
                    new_status=new_status,
                )
                await self.event_store.add_event(event)

            self.previous_statuses[instance.service_id] = new_status

    def stop(self):
        """Stop health checking"""
        self.running = False
