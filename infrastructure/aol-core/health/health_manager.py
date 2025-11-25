"""Enhanced Health Manager with Lazy Agent Detection and Auto-Recovery

This module implements advanced health management including:
- Lazy agent detection using Shapley-inspired credit assignment
- Automatic deliberation restarts for performance recovery
- Multi-dimensional health scoring
- Proactive failure mode detection

Based on: "Teaching AI Agents to Work Smarter, Not Harder" (2025)
"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict


class AgentHealthStatus(Enum):
    """Extended health status for multi-agent scenarios"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    LAZY = "lazy"  # Agent contributing less than expected
    DOMINANT = "dominant"  # Agent dominating workflow
    RECOVERING = "recovering"
    STARTING = "starting"


@dataclass
class AgentPerformanceMetrics:
    """Comprehensive agent performance tracking"""
    agent_id: str
    contribution_count: int = 0
    successful_contributions: int = 0
    total_influence_score: float = 0.0
    avg_response_time_ms: float = 0.0
    lazy_detections: int = 0
    recovery_attempts: int = 0
    last_contribution: Optional[datetime] = None
    consecutive_failures: int = 0
    health_status: AgentHealthStatus = AgentHealthStatus.STARTING
    
    @property
    def success_rate(self) -> float:
        if self.contribution_count == 0:
            return 0.0
        return self.successful_contributions / self.contribution_count
    
    @property
    def avg_influence(self) -> float:
        if self.contribution_count == 0:
            return 0.0
        return self.total_influence_score / self.contribution_count


@dataclass
class WorkflowHealth:
    """Health tracking for active workflows"""
    workflow_id: str
    agents: List[str]
    started_at: datetime
    contribution_balance: Dict[str, float] = field(default_factory=dict)
    restart_count: int = 0
    lazy_agents: List[str] = field(default_factory=list)
    dominant_agent: Optional[str] = None
    health_score: float = 1.0


class DeliberationManager:
    """Manages deliberation restarts for multi-agent workflows
    
    Implements noisy-step discards and automatic restarts to recover
    from poor agent dynamics (15-30% performance gains).
    """
    
    def __init__(self, event_store=None):
        self.event_store = event_store
        self.restart_history: Dict[str, List[datetime]] = defaultdict(list)
        self.max_restarts_per_hour = 5
        self.cooldown_seconds = 60
        self.logger = logging.getLogger(__name__)
    
    def can_restart(self, workflow_id: str) -> bool:
        """Check if a workflow can be restarted (rate limiting)"""
        now = datetime.utcnow()
        recent_restarts = [
            r for r in self.restart_history[workflow_id]
            if (now - r).total_seconds() < 3600
        ]
        
        if len(recent_restarts) >= self.max_restarts_per_hour:
            return False
        
        if recent_restarts:
            last_restart = max(recent_restarts)
            if (now - last_restart).total_seconds() < self.cooldown_seconds:
                return False
        
        return True
    
    async def trigger_restart(
        self,
        workflow_id: str,
        reason: str,
        affected_agents: List[str]
    ) -> bool:
        """Trigger a deliberation restart"""
        if not self.can_restart(workflow_id):
            self.logger.warning(
                f"Cannot restart workflow {workflow_id}: rate limit exceeded"
            )
            return False
        
        self.restart_history[workflow_id].append(datetime.utcnow())
        
        if self.event_store:
            await self.event_store.trigger_deliberation_restart(
                workflow_id=workflow_id,
                reason=reason
            )
        
        self.logger.info(
            f"Triggered deliberation restart for workflow {workflow_id}: {reason}"
        )
        
        return True
    
    async def evaluate_restart_condition(
        self,
        workflow_health: WorkflowHealth,
        threshold: float = 0.5
    ) -> Optional[str]:
        """Evaluate if a workflow should be restarted
        
        Returns restart reason if needed, None otherwise
        """
        # Check for dominance (one agent > 70% of contributions)
        if workflow_health.dominant_agent:
            total = sum(workflow_health.contribution_balance.values())
            if total > 0:
                dominance = workflow_health.contribution_balance.get(
                    workflow_health.dominant_agent, 0
                ) / total
                if dominance > 0.7:
                    return f"Agent {workflow_health.dominant_agent} is dominating ({dominance:.1%})"
        
        # Check for too many lazy agents (> 50% of agents)
        if len(workflow_health.lazy_agents) > len(workflow_health.agents) * threshold:
            return f"Too many lazy agents: {len(workflow_health.lazy_agents)}/{len(workflow_health.agents)}"
        
        # Check for low overall health score
        if workflow_health.health_score < 0.3:
            return f"Low workflow health score: {workflow_health.health_score:.2f}"
        
        return None


class LazyAgentDetector:
    """Detects and flags lazy or underperforming agents
    
    Uses Shapley-inspired credit assignment to identify agents
    that contribute less than their fair share.
    """
    
    def __init__(
        self,
        lazy_threshold: float = 0.1,  # < 10% contribution = lazy
        dominance_threshold: float = 0.5,  # > 50% contribution = dominant
        window_size: int = 100  # Consider last N contributions
    ):
        self.lazy_threshold = lazy_threshold
        self.dominance_threshold = dominance_threshold
        self.window_size = window_size
        self.agent_history: Dict[str, List[float]] = defaultdict(list)
        self.logger = logging.getLogger(__name__)
    
    def record_contribution(
        self,
        agent_id: str,
        influence_score: float
    ):
        """Record an agent's contribution"""
        history = self.agent_history[agent_id]
        history.append(influence_score)
        
        # Keep only recent history
        if len(history) > self.window_size:
            self.agent_history[agent_id] = history[-self.window_size:]
    
    def analyze_agent(self, agent_id: str) -> AgentHealthStatus:
        """Analyze agent status based on contribution history"""
        history = self.agent_history.get(agent_id, [])
        
        if not history:
            return AgentHealthStatus.STARTING
        
        avg_contribution = sum(history) / len(history)
        
        # Get average across all agents for comparison
        all_avgs = []
        for aid, h in self.agent_history.items():
            if h:
                all_avgs.append(sum(h) / len(h))
        
        if not all_avgs:
            return AgentHealthStatus.HEALTHY
        
        global_avg = sum(all_avgs) / len(all_avgs)
        
        # Determine status
        if global_avg > 0:
            relative_contribution = avg_contribution / global_avg
            
            if relative_contribution < self.lazy_threshold:
                return AgentHealthStatus.LAZY
            elif relative_contribution > (1.0 / self.lazy_threshold):
                return AgentHealthStatus.DOMINANT
            elif relative_contribution < 0.5:
                return AgentHealthStatus.DEGRADED
        
        return AgentHealthStatus.HEALTHY
    
    def get_lazy_agents(self, agents: List[str]) -> List[str]:
        """Get list of currently lazy agents"""
        return [
            agent_id for agent_id in agents
            if self.analyze_agent(agent_id) == AgentHealthStatus.LAZY
        ]
    
    def get_dominant_agent(self, agents: List[str]) -> Optional[str]:
        """Get the dominant agent if any"""
        for agent_id in agents:
            if self.analyze_agent(agent_id) == AgentHealthStatus.DOMINANT:
                return agent_id
        return None


class HealthManager:
    """Enhanced health manager with lazy agent detection and auto-recovery"""
    
    def __init__(self, config, registry, event_store=None):
        self.config = config
        self.registry = registry
        self.event_store = event_store
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.interval = 30  # seconds
        self.previous_statuses: Dict[str, str] = {}
        
        # New: Agent performance tracking
        self.agent_metrics: Dict[str, AgentPerformanceMetrics] = {}
        
        # New: Workflow health tracking
        self.workflow_health: Dict[str, WorkflowHealth] = {}
        
        # New: Lazy agent detection
        self.lazy_detector = LazyAgentDetector()
        
        # New: Deliberation management
        self.deliberation_manager = DeliberationManager(event_store)
        
        # Configuration
        self.auto_recovery_enabled = config.get('spec', {}).get(
            'healthManagement', {}
        ).get('autoRecoveryEnabled', True)
        
        self.lazy_detection_enabled = config.get('spec', {}).get(
            'healthManagement', {}
        ).get('lazyDetectionEnabled', True)
    
    async def run_health_checks(self):
        """Run periodic health checks with enhanced monitoring"""
        self.running = True
        interval = self.config.get('spec', {}).get('registry', {}).get(
            'healthCheckInterval', '30s'
        )
        self.interval = int(interval.rstrip('s'))
        
        while self.running:
            try:
                # Standard service health checks
                await self._check_all_services()
                
                # New: Multi-agent health analysis
                if self.lazy_detection_enabled:
                    await self._analyze_agent_health()
                
                # New: Workflow health checks
                await self._check_workflow_health()
                
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
        """Check health of a single service with enhanced metrics"""
        try:
            health_url = f"http://{instance.host}:{instance.health_port}/health"
            old_status = self.previous_statuses.get(instance.service_id, instance.status)
            
            start_time = datetime.utcnow()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    response_time_ms = (
                        datetime.utcnow() - start_time
                    ).total_seconds() * 1000
                    
                    if response.status == 200:
                        new_status = "healthy"
                        # Try to get extended health info
                        try:
                            health_data = await response.json()
                            # Update agent metrics if this is an agent service
                            if health_data.get('kind') in ['AOLAgent', 'AOLService']:
                                await self._update_agent_metrics(
                                    instance.service_id,
                                    response_time_ms,
                                    True,
                                    health_data
                                )
                        except Exception:
                            pass
                    else:
                        new_status = "unhealthy"
                        await self._update_agent_metrics(
                            instance.service_id,
                            response_time_ms,
                            False,
                            {}
                        )
            
            await self.registry.update_service_health(
                instance.name,
                instance.service_id,
                new_status
            )
            
            # Track health change event
            if old_status != new_status and self.event_store:
                from event_store import Event, EventType
                event = Event(
                    event_id=f"{instance.service_id}-{datetime.utcnow().isoformat()}",
                    event_type=EventType.HEALTH_CHANGED,
                    timestamp=datetime.utcnow(),
                    service_name=instance.name,
                    service_id=instance.service_id,
                    old_status=old_status,
                    new_status=new_status,
                    metadata={'response_time_ms': response_time_ms}
                )
                await self.event_store.add_event(event)
            
            self.previous_statuses[instance.service_id] = new_status
            
        except Exception as e:
            self.logger.debug(f"Health check failed for {instance.name}: {e}")
            old_status = self.previous_statuses.get(instance.service_id, instance.status)
            new_status = "unhealthy"
            
            await self.registry.update_service_health(
                instance.name,
                instance.service_id,
                new_status
            )
            
            await self._update_agent_metrics(
                instance.service_id,
                0,
                False,
                {}
            )
            
            # Track health change event
            if old_status != new_status and self.event_store:
                from event_store import Event, EventType
                event = Event(
                    event_id=f"{instance.service_id}-{datetime.utcnow().isoformat()}",
                    event_type=EventType.HEALTH_CHANGED,
                    timestamp=datetime.utcnow(),
                    service_name=instance.name,
                    service_id=instance.service_id,
                    old_status=old_status,
                    new_status=new_status
                )
                await self.event_store.add_event(event)
            
            self.previous_statuses[instance.service_id] = new_status
    
    async def _update_agent_metrics(
        self,
        agent_id: str,
        response_time_ms: float,
        success: bool,
        health_data: Dict
    ):
        """Update agent performance metrics"""
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AgentPerformanceMetrics(agent_id=agent_id)
        
        metrics = self.agent_metrics[agent_id]
        
        # Update metrics
        metrics.contribution_count += 1
        if success:
            metrics.successful_contributions += 1
            metrics.consecutive_failures = 0
        else:
            metrics.consecutive_failures += 1
        
        # Running average of response time
        if metrics.avg_response_time_ms == 0:
            metrics.avg_response_time_ms = response_time_ms
        else:
            metrics.avg_response_time_ms = (
                metrics.avg_response_time_ms * 0.9 + response_time_ms * 0.1
            )
        
        metrics.last_contribution = datetime.utcnow()
        
        # Update influence from event store if available
        if self.event_store:
            try:
                report = await self.event_store.get_agent_report(agent_id)
                metrics.total_influence_score = report.get('total_influence', 0)
                metrics.lazy_detections = report.get('lazy_flags', 0)
            except Exception:
                pass
    
    async def _analyze_agent_health(self):
        """Analyze health of all agents for lazy detection"""
        for agent_id, metrics in self.agent_metrics.items():
            # Record contribution for lazy detection
            influence = metrics.avg_influence if metrics.contribution_count > 0 else 0
            self.lazy_detector.record_contribution(agent_id, influence)
            
            # Analyze and update status
            status = self.lazy_detector.analyze_agent(agent_id)
            old_status = metrics.health_status
            metrics.health_status = status
            
            # Emit event on status change
            if old_status != status and self.event_store:
                if status == AgentHealthStatus.LAZY:
                    metrics.lazy_detections += 1
                    from event_store import Event, EventType
                    event = Event(
                        event_id=f"lazy-{agent_id}-{datetime.utcnow().isoformat()}",
                        event_type=EventType.AGENT_LAZY_DETECTED,
                        timestamp=datetime.utcnow(),
                        service_name=agent_id,
                        metadata={
                            'lazy_count': metrics.lazy_detections,
                            'avg_influence': metrics.avg_influence,
                            'success_rate': metrics.success_rate
                        }
                    )
                    await self.event_store.add_event(event)
    
    async def _check_workflow_health(self):
        """Check health of active workflows and trigger recoveries"""
        if not self.event_store:
            return
        
        for workflow_id, health in self.workflow_health.items():
            # Update contribution balance from event store
            try:
                report = await self.event_store.get_workflow_report(workflow_id)
                agent_stats = report.get('agent_stats', {})
                
                for agent_id, stats in agent_stats.items():
                    health.contribution_balance[agent_id] = stats.get('influence', 0)
            except Exception:
                continue
            
            # Detect lazy and dominant agents
            health.lazy_agents = self.lazy_detector.get_lazy_agents(health.agents)
            health.dominant_agent = self.lazy_detector.get_dominant_agent(health.agents)
            
            # Calculate overall health score
            if health.agents:
                healthy_agents = len([
                    a for a in health.agents
                    if self.agent_metrics.get(a, AgentPerformanceMetrics(a)).health_status
                    in [AgentHealthStatus.HEALTHY, AgentHealthStatus.STARTING]
                ])
                health.health_score = healthy_agents / len(health.agents)
            
            # Check for auto-recovery conditions
            if self.auto_recovery_enabled:
                restart_reason = await self.deliberation_manager.evaluate_restart_condition(
                    health
                )
                
                if restart_reason:
                    success = await self.deliberation_manager.trigger_restart(
                        workflow_id=workflow_id,
                        reason=restart_reason,
                        affected_agents=health.lazy_agents or [health.dominant_agent] if health.dominant_agent else []
                    )
                    
                    if success:
                        health.restart_count += 1
    
    async def register_workflow(
        self,
        workflow_id: str,
        agents: List[str]
    ):
        """Register a workflow for health tracking"""
        self.workflow_health[workflow_id] = WorkflowHealth(
            workflow_id=workflow_id,
            agents=agents,
            started_at=datetime.utcnow()
        )
    
    async def unregister_workflow(self, workflow_id: str):
        """Unregister a workflow from health tracking"""
        self.workflow_health.pop(workflow_id, None)
    
    async def record_agent_contribution(
        self,
        agent_id: str,
        workflow_id: str,
        influence_score: float,
        success: bool
    ):
        """Record an agent's contribution to a workflow"""
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AgentPerformanceMetrics(agent_id=agent_id)
        
        metrics = self.agent_metrics[agent_id]
        metrics.contribution_count += 1
        metrics.total_influence_score += influence_score
        metrics.last_contribution = datetime.utcnow()
        
        if success:
            metrics.successful_contributions += 1
        
        # Update lazy detector
        self.lazy_detector.record_contribution(agent_id, influence_score)
        
        # Update workflow health
        if workflow_id in self.workflow_health:
            health = self.workflow_health[workflow_id]
            if agent_id not in health.contribution_balance:
                health.contribution_balance[agent_id] = 0
            health.contribution_balance[agent_id] += influence_score
        
        # Record in event store
        if self.event_store:
            await self.event_store.record_contribution(
                agent_id=agent_id,
                workflow_id=workflow_id,
                turn_number=metrics.contribution_count,
                action_type='contribution',
                latency_ms=metrics.avg_response_time_ms,
                success=success
            )
    
    async def get_agent_health_report(self, agent_id: str) -> Dict:
        """Get comprehensive health report for an agent"""
        metrics = self.agent_metrics.get(
            agent_id,
            AgentPerformanceMetrics(agent_id=agent_id)
        )
        
        return {
            'agent_id': agent_id,
            'health_status': metrics.health_status.value,
            'contribution_count': metrics.contribution_count,
            'success_rate': metrics.success_rate,
            'avg_influence': metrics.avg_influence,
            'avg_response_time_ms': metrics.avg_response_time_ms,
            'lazy_detections': metrics.lazy_detections,
            'consecutive_failures': metrics.consecutive_failures,
            'last_contribution': metrics.last_contribution.isoformat() if metrics.last_contribution else None
        }
    
    async def get_workflow_health_report(self, workflow_id: str) -> Dict:
        """Get comprehensive health report for a workflow"""
        health = self.workflow_health.get(workflow_id)
        
        if not health:
            return {'error': 'Workflow not found'}
        
        return {
            'workflow_id': workflow_id,
            'agents': health.agents,
            'health_score': health.health_score,
            'contribution_balance': health.contribution_balance,
            'lazy_agents': health.lazy_agents,
            'dominant_agent': health.dominant_agent,
            'restart_count': health.restart_count,
            'started_at': health.started_at.isoformat()
        }
    
    async def get_overall_health_stats(self) -> Dict:
        """Get overall system health statistics"""
        total_agents = len(self.agent_metrics)
        healthy_count = sum(
            1 for m in self.agent_metrics.values()
            if m.health_status == AgentHealthStatus.HEALTHY
        )
        lazy_count = sum(
            1 for m in self.agent_metrics.values()
            if m.health_status == AgentHealthStatus.LAZY
        )
        dominant_count = sum(
            1 for m in self.agent_metrics.values()
            if m.health_status == AgentHealthStatus.DOMINANT
        )
        
        return {
            'total_agents': total_agents,
            'healthy_agents': healthy_count,
            'lazy_agents': lazy_count,
            'dominant_agents': dominant_count,
            'active_workflows': len(self.workflow_health),
            'total_restarts': sum(
                h.restart_count for h in self.workflow_health.values()
            ),
            'system_health_score': healthy_count / max(total_agents, 1)
        }
    
    def stop(self):
        """Stop health checking"""
        self.running = False
