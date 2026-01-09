"""
Event Bus Client - Async Pub-Sub for Inter-Service Coordination

This module provides event-driven communication capabilities for loosely coupled
services in the AOL mesh. Services can publish events without knowing subscribers
and subscribe to events without knowing publishers.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """Represents an event in the pub-sub system"""

    event_id: str
    topic: str
    event_type: str
    source_service: str
    payload: Dict[str, Any]
    timestamp: str
    priority: int = EventPriority.NORMAL.value
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert event to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Event":
        """Create event from dictionary"""
        return cls(**data)

    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict())


@dataclass
class Subscription:
    """Represents a topic subscription"""

    subscription_id: str
    topic: str
    handler: Callable
    filter_fn: Optional[Callable] = None
    active: bool = True


class EventBusClient:
    """
    Event bus client for async pub-sub coordination.

    Uses aol-core as the central event broker to ensure loose coupling
    between services. Services don't communicate directly - all events
    flow through the broker.
    """

    def __init__(
        self,
        service_name: str,
        aol_core_endpoint: str = None,
        max_queue_size: int = 1000,
        process_timeout: int = 30,
    ):
        """
        Initialize event bus client.

        Args:
            service_name: Name of the service using this client
            aol_core_endpoint: AOL-Core endpoint for event routing
            max_queue_size: Maximum events to queue locally
            process_timeout: Timeout for processing events
        """
        import os

        self.service_name = service_name
        self.aol_core_endpoint = aol_core_endpoint or os.getenv(
            "AOL_CORE_ENDPOINT", "http://aol-core:8080"
        )
        self.max_queue_size = max_queue_size
        self.process_timeout = process_timeout

        # Local event queue for buffering
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)

        # Subscriptions registry
        self._subscriptions: Dict[str, List[Subscription]] = {}

        # HTTP session for broker communication
        self._session: Optional[aiohttp.ClientSession] = None

        # Background tasks
        self._processor_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # State
        self._running = False
        self._published_topics: Set[str] = set()
        self._subscribed_topics: Set[str] = set()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.process_timeout)
            )
        return self._session

    async def start(self):
        """Start the event bus client"""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting event bus client for {self.service_name}")

        # Start event processor
        self._processor_task = asyncio.create_task(self._process_events())

        # Register with broker
        await self._register_with_broker()

        logger.info(f"Event bus client started for {self.service_name}")

    async def stop(self):
        """Stop the event bus client"""
        if not self._running:
            return

        self._running = False
        logger.info(f"Stopping event bus client for {self.service_name}")

        # Deregister from broker
        await self._deregister_from_broker()

        # Cancel background tasks
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close HTTP session
        if self._session:
            await self._session.close()
            self._session = None

        logger.info(f"Event bus client stopped for {self.service_name}")

    async def _register_with_broker(self):
        """Register service with event broker"""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.aol_core_endpoint}/api/events/register",
                json={
                    "service_name": self.service_name,
                    "published_topics": list(self._published_topics),
                    "subscribed_topics": list(self._subscribed_topics),
                },
            ) as resp:
                if resp.status == 200:
                    logger.info("Registered with event broker")
                else:
                    logger.warning(f"Failed to register with broker: {resp.status}")
        except Exception as e:
            logger.warning(f"Could not register with event broker: {e}")

    async def _deregister_from_broker(self):
        """Deregister service from event broker"""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.aol_core_endpoint}/api/events/deregister",
                json={"service_name": self.service_name},
            ) as resp:
                if resp.status == 200:
                    logger.info("Deregistered from event broker")
        except Exception as e:
            logger.warning(f"Could not deregister from event broker: {e}")

    async def publish(
        self,
        topic: str,
        event_type: str,
        payload: Dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Publish an event to a topic.

        Args:
            topic: Topic to publish to
            event_type: Type of event (e.g., "TaskCompleted")
            payload: Event payload data
            priority: Event priority level
            correlation_id: Optional correlation ID for tracing
            metadata: Optional metadata

        Returns:
            Event ID
        """
        event = Event(
            event_id=str(uuid.uuid4()),
            topic=topic,
            event_type=event_type,
            source_service=self.service_name,
            payload=payload,
            timestamp=datetime.utcnow().isoformat(),
            priority=priority.value,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )

        # Track published topics
        self._published_topics.add(topic)

        # Send to broker
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.aol_core_endpoint}/api/events/publish", json=event.to_dict()
            ) as resp:
                if resp.status == 200:
                    logger.debug(f"Published event {event.event_id} to {topic}")
                else:
                    # Queue locally for retry
                    await self._event_queue.put(("publish", event))
                    logger.warning("Failed to publish to broker, queued locally")
        except Exception as e:
            # Queue locally for retry
            try:
                self._event_queue.put_nowait(("publish", event))
                logger.warning(f"Could not reach broker, queued locally: {e}")
            except asyncio.QueueFull:
                logger.error(f"Event queue full, dropping event {event.event_id}")

        return event.event_id

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Event], Any],
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> str:
        """
        Subscribe to events on a topic.

        Args:
            topic: Topic to subscribe to
            handler: Async function to handle events
            filter_fn: Optional filter function to filter events

        Returns:
            Subscription ID
        """
        subscription = Subscription(
            subscription_id=str(uuid.uuid4()),
            topic=topic,
            handler=handler,
            filter_fn=filter_fn,
        )

        if topic not in self._subscriptions:
            self._subscriptions[topic] = []

        self._subscriptions[topic].append(subscription)
        self._subscribed_topics.add(topic)

        # Update broker registration
        if self._running:
            await self._register_with_broker()

        logger.info(f"Subscribed to {topic} with ID {subscription.subscription_id}")
        return subscription.subscription_id

    async def unsubscribe(self, subscription_id: str):
        """
        Unsubscribe from a topic.

        Args:
            subscription_id: Subscription ID to remove
        """
        for topic, subs in self._subscriptions.items():
            for sub in subs:
                if sub.subscription_id == subscription_id:
                    subs.remove(sub)
                    logger.info(f"Unsubscribed {subscription_id} from {topic}")

                    # Update subscribed topics
                    if not subs:
                        self._subscribed_topics.discard(topic)
                    return

        logger.warning(f"Subscription {subscription_id} not found")

    async def _process_events(self):
        """Background task to process incoming events and retries"""
        while self._running:
            try:
                # Poll broker for events
                await self._poll_broker()

                # Process retry queue
                await self._process_retry_queue()

                await asyncio.sleep(0.1)  # Small delay to prevent busy loop

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
                await asyncio.sleep(1)

    async def _poll_broker(self):
        """Poll broker for new events"""
        if not self._subscribed_topics:
            return

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.aol_core_endpoint}/api/events/poll",
                json={
                    "service_name": self.service_name,
                    "topics": list(self._subscribed_topics),
                    "max_events": 10,
                },
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    events = data.get("events", [])

                    for event_data in events:
                        event = Event.from_dict(event_data)
                        await self._dispatch_event(event)

        except asyncio.TimeoutError:
            pass  # Normal timeout, no events available
        except Exception as e:
            logger.debug(f"Could not poll broker: {e}")

    async def _dispatch_event(self, event: Event):
        """Dispatch event to registered handlers"""
        topic = event.topic

        if topic not in self._subscriptions:
            return

        for subscription in self._subscriptions[topic]:
            if not subscription.active:
                continue

            # Apply filter if present
            if subscription.filter_fn and not subscription.filter_fn(event):
                continue

            try:
                # Call handler
                result = subscription.handler(event)
                if asyncio.iscoroutine(result):
                    await result

                # Acknowledge event
                await self._ack_event(event.event_id)

            except Exception as e:
                logger.error(
                    f"Error handling event {event.event_id} "
                    f"in subscription {subscription.subscription_id}: {e}"
                )
                # Nack for retry
                await self._nack_event(event.event_id)

    async def _ack_event(self, event_id: str):
        """Acknowledge event processing"""
        try:
            session = await self._get_session()
            await session.post(
                f"{self.aol_core_endpoint}/api/events/ack",
                json={"service_name": self.service_name, "event_id": event_id},
            )
        except Exception as e:
            logger.debug(f"Could not ack event: {e}")

    async def _nack_event(self, event_id: str):
        """Negative acknowledge for retry"""
        try:
            session = await self._get_session()
            await session.post(
                f"{self.aol_core_endpoint}/api/events/nack",
                json={"service_name": self.service_name, "event_id": event_id},
            )
        except Exception as e:
            logger.debug(f"Could not nack event: {e}")

    async def _process_retry_queue(self):
        """Process locally queued events"""
        while not self._event_queue.empty():
            try:
                action, event = self._event_queue.get_nowait()

                if action == "publish":
                    session = await self._get_session()
                    async with session.post(
                        f"{self.aol_core_endpoint}/api/events/publish",
                        json=event.to_dict(),
                    ) as resp:
                        if resp.status != 200:
                            # Re-queue if still failing
                            await self._event_queue.put((action, event))
                            break  # Stop processing, try again later

            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.debug(f"Retry failed: {e}")
                break


class LocalEventBus:
    """
    Local in-memory event bus for testing and single-instance deployments.

    Use this when you don't need distributed pub-sub (e.g., development/testing).
    """

    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000

    async def publish(
        self,
        topic: str,
        event_type: str,
        payload: Dict[str, Any],
        source_service: str = "local",
        **kwargs,
    ) -> str:
        """Publish event locally"""
        event = Event(
            event_id=str(uuid.uuid4()),
            topic=topic,
            event_type=event_type,
            source_service=source_service,
            payload=payload,
            timestamp=datetime.utcnow().isoformat(),
            **kwargs,
        )

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Dispatch to subscribers
        await self._dispatch(event)

        return event.event_id

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Event], Any],
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> str:
        """Subscribe to local events"""
        subscription = Subscription(
            subscription_id=str(uuid.uuid4()),
            topic=topic,
            handler=handler,
            filter_fn=filter_fn,
        )

        if topic not in self._subscriptions:
            self._subscriptions[topic] = []

        self._subscriptions[topic].append(subscription)
        return subscription.subscription_id

    async def _dispatch(self, event: Event):
        """Dispatch event to handlers"""
        if event.topic not in self._subscriptions:
            return

        for sub in self._subscriptions[event.topic]:
            if sub.filter_fn and not sub.filter_fn(event):
                continue

            try:
                result = sub.handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Handler error: {e}")

    def get_history(self, topic: Optional[str] = None, limit: int = 100) -> List[Event]:
        """Get event history"""
        events = self._event_history
        if topic:
            events = [e for e in events if e.topic == topic]
        return events[-limit:]
