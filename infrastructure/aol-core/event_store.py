"""Event store for tracking AOL Core events"""
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import json

class EventType(Enum):
    SERVICE_REGISTERED = "service_registered"
    SERVICE_DEREGISTERED = "service_deregistered"
    HEALTH_CHANGED = "health_changed"
    ROUTE_CALLED = "route_called"
    SERVICE_DISCOVERED = "service_discovered"

@dataclass
class Event:
    """Represents a system event"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    service_name: Optional[str] = None
    service_id: Optional[str] = None
    source_service: Optional[str] = None
    target_service: Optional[str] = None
    method: Optional[str] = None
    success: Optional[bool] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    metadata: Optional[Dict] = None
    
    def to_dict(self):
        """Convert event to dictionary"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

class EventStore:
    """Stores and manages system events"""
    
    def __init__(self, max_events: int = 1000):
        self.max_events = max_events
        self.events: List[Event] = []
        self.lock = asyncio.Lock()
        self.subscribers: List[asyncio.Queue] = []
    
    async def add_event(self, event: Event):
        """Add an event to the store"""
        async with self.lock:
            self.events.append(event)
            
            # Keep only last max_events
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events:]
            
            # Notify subscribers
            for queue in self.subscribers:
                try:
                    await queue.put(event)
                except Exception:
                    # Remove dead subscribers
                    self.subscribers.remove(queue)
    
    async def get_events(
        self,
        event_type: Optional[EventType] = None,
        service_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get events with optional filtering"""
        async with self.lock:
            filtered = self.events
            
            if event_type:
                filtered = [e for e in filtered if e.event_type == event_type]
            
            if service_name:
                filtered = [
                    e for e in filtered
                    if e.service_name == service_name or
                       e.source_service == service_name or
                       e.target_service == service_name
                ]
            
            return filtered[-limit:]
    
    async def get_route_events(
        self,
        source_service: Optional[str] = None,
        target_service: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get route call events"""
        async with self.lock:
            route_events = [
                e for e in self.events
                if e.event_type == EventType.ROUTE_CALLED
            ]
            
            if source_service:
                route_events = [e for e in route_events if e.source_service == source_service]
            
            if target_service:
                route_events = [e for e in route_events if e.target_service == target_service]
            
            return route_events[-limit:]
    
    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to new events"""
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue
    
    async def get_stats(self) -> Dict:
        """Get event statistics"""
        async with self.lock:
            stats = {
                'total_events': len(self.events),
                'by_type': {},
                'recent_events': len([e for e in self.events if 
                    (datetime.utcnow() - e.timestamp).total_seconds() < 3600])
            }
            
            for event_type in EventType:
                stats['by_type'][event_type.value] = len([
                    e for e in self.events if e.event_type == event_type
                ])
            
            return stats

