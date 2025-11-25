"""Enhanced Event Store for AOL Core with Async Pub-Sub and Shapley Credit Assignment"""
import asyncio
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
import math
from collections import defaultdict


class EventType(Enum):
    SERVICE_REGISTERED = "service_registered"
    SERVICE_DEREGISTERED = "service_deregistered"
    HEALTH_CHANGED = "health_changed"
    ROUTE_CALLED = "route_called"
    SERVICE_DISCOVERED = "service_discovered"
    # New event types for multi-agent orchestration
    AGENT_CONTRIBUTION = "agent_contribution"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    DELIBERATION_STARTED = "deliberation_started"
    DELIBERATION_RESTARTED = "deliberation_restarted"
    AGENT_LAZY_DETECTED = "agent_lazy_detected"


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
    # New fields for credit assignment
    contribution_score: Optional[float] = None
    workflow_id: Optional[str] = None
    
    def to_dict(self):
        """Convert event to dictionary"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class AgentContribution:
    """Tracks individual agent contributions in a workflow"""
    agent_id: str
    workflow_id: str
    turn_number: int
    action_type: str  # 'reasoning', 'decision', 'verification', 'delegation'
    latency_ms: float
    success: bool
    influence_score: float = 0.0  # Shapley-inspired causal influence
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ShapleyCalculator:
    """Calculates Shapley-inspired credit assignment for multi-agent workflows
    
    Based on: "Teaching AI Agents to Work Smarter, Not Harder" (2025)
    This implements a simplified Shapley value calculation for real-time
    credit assignment in multi-agent deliberations.
    """
    
    def __init__(self):
        self.coalition_values: Dict[str, Dict[frozenset, float]] = {}
    
    def calculate_marginal_contribution(
        self,
        agent_id: str,
        workflow_id: str,
        all_agents: List[str],
        value_function: Callable[[frozenset], float]
    ) -> float:
        """Calculate the marginal contribution of an agent
        
        Uses simplified Shapley calculation:
        φᵢ = Σ |S|!(n-|S|-1)!/n! × [v(S∪{i}) - v(S)]
        """
        n = len(all_agents)
        if n == 0:
            return 0.0
        
        shapley_value = 0.0
        agents_set = set(all_agents)
        
        # Calculate over all possible coalitions without agent_i
        other_agents = agents_set - {agent_id}
        
        # Iterate through all subsets of other agents
        for r in range(len(other_agents) + 1):
            from itertools import combinations
            for coalition in combinations(other_agents, r):
                S = frozenset(coalition)
                S_with_i = S | {agent_id}
                
                # Weighting factor: |S|!(n-|S|-1)!/n!
                weight = (math.factorial(len(S)) * 
                         math.factorial(n - len(S) - 1)) / math.factorial(n)
                
                # Marginal contribution
                v_with = value_function(S_with_i)
                v_without = value_function(S)
                
                shapley_value += weight * (v_with - v_without)
        
        return shapley_value
    
    def detect_lazy_agent(
        self,
        contributions: List[AgentContribution],
        threshold: float = 0.1
    ) -> List[str]:
        """Detect agents that contribute less than threshold of total value
        
        Returns list of agent IDs that may be "lazy" (dominating or underperforming)
        """
        if not contributions:
            return []
        
        # Group by agent
        agent_scores: Dict[str, float] = defaultdict(float)
        for contrib in contributions:
            agent_scores[contrib.agent_id] += contrib.influence_score
        
        total_score = sum(agent_scores.values())
        if total_score == 0:
            return list(agent_scores.keys())  # All agents have zero contribution
        
        # Find agents below threshold
        lazy_agents = []
        for agent_id, score in agent_scores.items():
            relative_contribution = score / total_score
            if relative_contribution < threshold:
                lazy_agents.append(agent_id)
        
        return lazy_agents


class PubSubChannel:
    """Async pub-sub channel for event-driven orchestration"""
    
    def __init__(self, name: str):
        self.name = name
        self.subscribers: Dict[str, asyncio.Queue] = {}
        self.lock = asyncio.Lock()
    
    async def subscribe(self, subscriber_id: str) -> asyncio.Queue:
        """Subscribe to channel and receive events"""
        async with self.lock:
            if subscriber_id not in self.subscribers:
                self.subscribers[subscriber_id] = asyncio.Queue(maxsize=1000)
            return self.subscribers[subscriber_id]
    
    async def unsubscribe(self, subscriber_id: str):
        """Unsubscribe from channel"""
        async with self.lock:
            self.subscribers.pop(subscriber_id, None)
    
    async def publish(self, event: Any):
        """Publish event to all subscribers"""
        async with self.lock:
            dead_subscribers = []
            for sub_id, queue in self.subscribers.items():
                try:
                    # Non-blocking put with timeout
                    await asyncio.wait_for(
                        queue.put(event),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Subscriber is slow, mark for removal
                    dead_subscribers.append(sub_id)
                except Exception:
                    dead_subscribers.append(sub_id)
            
            # Clean up dead subscribers
            for sub_id in dead_subscribers:
                self.subscribers.pop(sub_id, None)


class EventBus:
    """Central event bus for async event-driven orchestration
    
    Implements pub-sub patterns for reducing synchronous bottlenecks
    as recommended in the AOL enhancement roadmap.
    """
    
    def __init__(self):
        self.channels: Dict[str, PubSubChannel] = {}
        self.lock = asyncio.Lock()
        self.event_handlers: Dict[EventType, List[Callable]] = defaultdict(list)
    
    async def get_or_create_channel(self, channel_name: str) -> PubSubChannel:
        """Get or create a pub-sub channel"""
        async with self.lock:
            if channel_name not in self.channels:
                self.channels[channel_name] = PubSubChannel(channel_name)
            return self.channels[channel_name]
    
    async def publish(self, channel_name: str, event: Any):
        """Publish event to a specific channel"""
        channel = await self.get_or_create_channel(channel_name)
        await channel.publish(event)
    
    async def subscribe(self, channel_name: str, subscriber_id: str) -> asyncio.Queue:
        """Subscribe to a channel"""
        channel = await self.get_or_create_channel(channel_name)
        return await channel.subscribe(subscriber_id)
    
    def register_handler(self, event_type: EventType, handler: Callable):
        """Register a handler for a specific event type"""
        self.event_handlers[event_type].append(handler)
    
    async def dispatch(self, event: Event):
        """Dispatch event to all registered handlers"""
        handlers = self.event_handlers.get(event.event_type, [])
        tasks = [asyncio.create_task(handler(event)) for handler in handlers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class EventStore:
    """Enhanced event store with async pub-sub and credit assignment"""
    
    def __init__(self, max_events: int = 1000):
        self.max_events = max_events
        self.events: List[Event] = []
        self.lock = asyncio.Lock()
        self.subscribers: List[asyncio.Queue] = []
        
        # New: Event bus for async orchestration
        self.event_bus = EventBus()
        
        # New: Shapley calculator for credit assignment
        self.shapley_calculator = ShapleyCalculator()
        
        # New: Contribution tracking per workflow
        self.workflow_contributions: Dict[str, List[AgentContribution]] = defaultdict(list)
        
        # New: Workflow state tracking
        self.active_workflows: Dict[str, Dict] = {}
        
        # New: Agent performance metrics
        self.agent_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'total_contributions': 0,
                'successful_contributions': 0,
                'total_influence': 0.0,
                'lazy_flags': 0,
                'restart_triggers': 0
            }
        )
    
    async def add_event(self, event: Event):
        """Add an event to the store with pub-sub dispatch"""
        async with self.lock:
            self.events.append(event)
            
            # Keep only last max_events
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events:]
            
            # Notify legacy subscribers
            for queue in self.subscribers:
                try:
                    await queue.put(event)
                except Exception:
                    self.subscribers.remove(queue)
        
        # Dispatch to event bus (async, non-blocking)
        await self.event_bus.dispatch(event)
        
        # Publish to relevant channels
        if event.service_name:
            await self.event_bus.publish(f"service:{event.service_name}", event)
        if event.workflow_id:
            await self.event_bus.publish(f"workflow:{event.workflow_id}", event)
        
        # Always publish to global channel
        await self.event_bus.publish("global", event)
    
    async def record_contribution(
        self,
        agent_id: str,
        workflow_id: str,
        turn_number: int,
        action_type: str,
        latency_ms: float,
        success: bool,
        value_function: Optional[Callable] = None
    ) -> AgentContribution:
        """Record an agent's contribution to a workflow with credit assignment"""
        contribution = AgentContribution(
            agent_id=agent_id,
            workflow_id=workflow_id,
            turn_number=turn_number,
            action_type=action_type,
            latency_ms=latency_ms,
            success=success
        )
        
        # Calculate influence score if value function provided
        if value_function:
            all_agents = list(set(
                c.agent_id for c in self.workflow_contributions[workflow_id]
            ) | {agent_id})
            
            contribution.influence_score = self.shapley_calculator.calculate_marginal_contribution(
                agent_id=agent_id,
                workflow_id=workflow_id,
                all_agents=all_agents,
                value_function=value_function
            )
        else:
            # Default influence based on success and action type
            base_score = 1.0 if success else 0.0
            type_weights = {
                'reasoning': 1.2,
                'decision': 1.5,
                'verification': 1.0,
                'delegation': 0.8
            }
            contribution.influence_score = base_score * type_weights.get(action_type, 1.0)
        
        # Store contribution
        self.workflow_contributions[workflow_id].append(contribution)
        
        # Update agent metrics
        metrics = self.agent_metrics[agent_id]
        metrics['total_contributions'] += 1
        if success:
            metrics['successful_contributions'] += 1
        metrics['total_influence'] += contribution.influence_score
        
        # Create and store event
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.AGENT_CONTRIBUTION,
            timestamp=datetime.utcnow(),
            service_name=agent_id,
            workflow_id=workflow_id,
            contribution_score=contribution.influence_score,
            success=success,
            metadata={
                'turn_number': turn_number,
                'action_type': action_type,
                'latency_ms': latency_ms
            }
        )
        await self.add_event(event)
        
        return contribution
    
    async def check_lazy_agents(
        self,
        workflow_id: str,
        threshold: float = 0.1
    ) -> List[str]:
        """Check for lazy agents in a workflow and emit events"""
        contributions = self.workflow_contributions.get(workflow_id, [])
        lazy_agents = self.shapley_calculator.detect_lazy_agent(contributions, threshold)
        
        for agent_id in lazy_agents:
            self.agent_metrics[agent_id]['lazy_flags'] += 1
            
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.AGENT_LAZY_DETECTED,
                timestamp=datetime.utcnow(),
                service_name=agent_id,
                workflow_id=workflow_id,
                metadata={
                    'threshold': threshold,
                    'lazy_count': self.agent_metrics[agent_id]['lazy_flags']
                }
            )
            await self.add_event(event)
        
        return lazy_agents
    
    async def trigger_deliberation_restart(
        self,
        workflow_id: str,
        reason: str
    ):
        """Trigger a deliberation restart for noisy-step recovery"""
        workflow = self.active_workflows.get(workflow_id, {})
        
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.DELIBERATION_RESTARTED,
            timestamp=datetime.utcnow(),
            workflow_id=workflow_id,
            metadata={
                'reason': reason,
                'previous_state': workflow.get('state', 'unknown'),
                'contributions_discarded': len(self.workflow_contributions.get(workflow_id, []))
            }
        )
        await self.add_event(event)
        
        # Clear contributions for restart
        self.workflow_contributions[workflow_id] = []
        
        # Update workflow state
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id]['state'] = 'restarted'
            self.active_workflows[workflow_id]['restart_count'] = \
                self.active_workflows[workflow_id].get('restart_count', 0) + 1
    
    async def start_workflow(
        self,
        workflow_id: str,
        workflow_type: str,
        agents: List[str],
        metadata: Optional[Dict] = None
    ):
        """Start tracking a new workflow"""
        self.active_workflows[workflow_id] = {
            'type': workflow_type,
            'agents': agents,
            'state': 'running',
            'started_at': datetime.utcnow(),
            'restart_count': 0,
            'metadata': metadata or {}
        }
        
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.WORKFLOW_STARTED,
            timestamp=datetime.utcnow(),
            workflow_id=workflow_id,
            metadata={
                'workflow_type': workflow_type,
                'agents': agents,
                **(metadata or {})
            }
        )
        await self.add_event(event)
    
    async def complete_workflow(
        self,
        workflow_id: str,
        success: bool,
        result: Optional[Dict] = None
    ):
        """Complete a workflow with final credit assignment"""
        workflow = self.active_workflows.get(workflow_id, {})
        contributions = self.workflow_contributions.get(workflow_id, [])
        
        # Calculate final credit distribution
        final_credits = {}
        for contrib in contributions:
            if contrib.agent_id not in final_credits:
                final_credits[contrib.agent_id] = 0.0
            final_credits[contrib.agent_id] += contrib.influence_score
        
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.WORKFLOW_COMPLETED if success else EventType.WORKFLOW_FAILED,
            timestamp=datetime.utcnow(),
            workflow_id=workflow_id,
            success=success,
            metadata={
                'duration_seconds': (datetime.utcnow() - workflow.get('started_at', datetime.utcnow())).total_seconds(),
                'total_contributions': len(contributions),
                'restart_count': workflow.get('restart_count', 0),
                'final_credits': final_credits,
                'result': result
            }
        )
        await self.add_event(event)
        
        # Update workflow state
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id]['state'] = 'completed' if success else 'failed'
    
    async def get_events(
        self,
        event_type: Optional[EventType] = None,
        service_name: Optional[str] = None,
        workflow_id: Optional[str] = None,
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
            
            if workflow_id:
                filtered = [e for e in filtered if e.workflow_id == workflow_id]
            
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
        """Subscribe to new events (legacy support)"""
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue
    
    async def get_stats(self) -> Dict:
        """Get comprehensive event statistics"""
        async with self.lock:
            stats = {
                'total_events': len(self.events),
                'by_type': {},
                'recent_events': len([e for e in self.events if 
                    (datetime.utcnow() - e.timestamp).total_seconds() < 3600]),
                # New: Workflow stats
                'active_workflows': len([w for w in self.active_workflows.values() 
                                        if w.get('state') == 'running']),
                'completed_workflows': len([w for w in self.active_workflows.values() 
                                           if w.get('state') == 'completed']),
                'failed_workflows': len([w for w in self.active_workflows.values() 
                                        if w.get('state') == 'failed']),
                # New: Agent stats
                'agent_count': len(self.agent_metrics),
                'total_contributions': sum(
                    m['total_contributions'] for m in self.agent_metrics.values()
                ),
                'lazy_agent_flags': sum(
                    m['lazy_flags'] for m in self.agent_metrics.values()
                )
            }
            
            for event_type in EventType:
                stats['by_type'][event_type.value] = len([
                    e for e in self.events if e.event_type == event_type
                ])
            
            return stats
    
    async def get_agent_report(self, agent_id: str) -> Dict:
        """Get detailed performance report for an agent"""
        metrics = self.agent_metrics.get(agent_id, {})
        
        return {
            'agent_id': agent_id,
            'total_contributions': metrics.get('total_contributions', 0),
            'successful_contributions': metrics.get('successful_contributions', 0),
            'success_rate': (
                metrics.get('successful_contributions', 0) / 
                max(metrics.get('total_contributions', 1), 1)
            ),
            'total_influence': metrics.get('total_influence', 0.0),
            'lazy_flags': metrics.get('lazy_flags', 0),
            'restart_triggers': metrics.get('restart_triggers', 0),
            'average_influence_per_contribution': (
                metrics.get('total_influence', 0.0) / 
                max(metrics.get('total_contributions', 1), 1)
            )
        }
    
    async def get_workflow_report(self, workflow_id: str) -> Dict:
        """Get detailed report for a workflow"""
        workflow = self.active_workflows.get(workflow_id, {})
        contributions = self.workflow_contributions.get(workflow_id, [])
        
        # Calculate per-agent stats
        agent_stats = defaultdict(lambda: {'contributions': 0, 'influence': 0.0, 'successes': 0})
        for contrib in contributions:
            agent_stats[contrib.agent_id]['contributions'] += 1
            agent_stats[contrib.agent_id]['influence'] += contrib.influence_score
            if contrib.success:
                agent_stats[contrib.agent_id]['successes'] += 1
        
        return {
            'workflow_id': workflow_id,
            'type': workflow.get('type'),
            'state': workflow.get('state'),
            'agents': workflow.get('agents', []),
            'started_at': workflow.get('started_at', datetime.utcnow()).isoformat(),
            'restart_count': workflow.get('restart_count', 0),
            'total_contributions': len(contributions),
            'agent_stats': dict(agent_stats)
        }
