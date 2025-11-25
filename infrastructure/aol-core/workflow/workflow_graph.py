"""LangGraph-Style Workflow Graph Integration for AOL

This module implements graph-based task decomposition and conditional routing
for multi-agent workflows, mapping AOL manifests to workflow graph nodes.

Key Features:
- DAG-based workflow orchestration
- Conditional routing based on agent responses
- Parallel execution support
- Dynamic workflow modification
- Integration with AOL service registry

Based on: "Build multi-agent systems with LangGraph and Amazon Bedrock" (2025)
"""
import asyncio
import uuid
import logging
from typing import Dict, List, Optional, Any, Callable, Set, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict


class NodeType(Enum):
    """Types of nodes in workflow graph"""
    AGENT = "agent"  # AI agent that processes/reasons
    TOOL = "tool"    # External tool/API integration
    ROUTER = "router"  # Conditional routing node
    AGGREGATOR = "aggregator"  # Combines multiple outputs
    CHECKPOINT = "checkpoint"  # Saves state for recovery
    HUMAN = "human"  # Human-in-the-loop node
    START = "start"  # Workflow entry point
    END = "end"      # Workflow exit point


class EdgeType(Enum):
    """Types of edges between nodes"""
    SEQUENTIAL = "sequential"  # A -> B (always)
    CONDITIONAL = "conditional"  # A -> B if condition
    PARALLEL = "parallel"  # A -> [B, C] (simultaneously)
    FALLBACK = "fallback"  # A -> B on error


@dataclass
class WorkflowNode:
    """A node in the workflow graph"""
    node_id: str
    name: str
    node_type: NodeType
    service_name: Optional[str] = None  # AOL service to invoke
    config: Dict = field(default_factory=dict)
    timeout_seconds: float = 30.0
    retry_count: int = 3
    # Execution tracking
    execution_count: int = 0
    success_count: int = 0
    total_latency_ms: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.total_latency_ms / self.execution_count
    
    @property
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count


@dataclass
class WorkflowEdge:
    """An edge connecting two nodes"""
    edge_id: str
    source_node: str
    target_node: str
    edge_type: EdgeType
    condition: Optional[Callable[[Any], bool]] = None
    priority: int = 0
    # Tracking
    traversal_count: int = 0


@dataclass
class WorkflowState:
    """Tracks the state of a workflow execution"""
    workflow_id: str
    execution_id: str
    current_nodes: Set[str]  # Nodes currently executing (parallel support)
    completed_nodes: Set[str]
    node_outputs: Dict[str, Any]
    global_state: Dict[str, Any]
    started_at: datetime
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'workflow_id': self.workflow_id,
            'execution_id': self.execution_id,
            'current_nodes': list(self.current_nodes),
            'completed_nodes': list(self.completed_nodes),
            'started_at': self.started_at.isoformat(),
            'error': self.error
        }


class WorkflowGraph:
    """DAG-based workflow orchestration for multi-agent systems
    
    Implements LangGraph-style patterns for AOL:
    - Node-based task decomposition
    - Conditional routing
    - Parallel execution
    - State management
    """
    
    def __init__(
        self,
        workflow_id: str,
        name: str,
        description: str = ""
    ):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: Dict[str, WorkflowEdge] = {}
        self.adjacency: Dict[str, List[str]] = defaultdict(list)  # node -> edges
        self.reverse_adjacency: Dict[str, List[str]] = defaultdict(list)
        self.logger = logging.getLogger(__name__)
        
        # Add implicit start and end nodes
        self.add_node(WorkflowNode(
            node_id="__start__",
            name="Start",
            node_type=NodeType.START
        ))
        self.add_node(WorkflowNode(
            node_id="__end__",
            name="End",
            node_type=NodeType.END
        ))
    
    def add_node(self, node: WorkflowNode):
        """Add a node to the workflow"""
        self.nodes[node.node_id] = node
    
    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: EdgeType = EdgeType.SEQUENTIAL,
        condition: Optional[Callable[[Any], bool]] = None,
        priority: int = 0
    ) -> str:
        """Add an edge between nodes"""
        edge_id = f"{source}_to_{target}"
        edge = WorkflowEdge(
            edge_id=edge_id,
            source_node=source,
            target_node=target,
            edge_type=edge_type,
            condition=condition,
            priority=priority
        )
        self.edges[edge_id] = edge
        self.adjacency[source].append(edge_id)
        self.reverse_adjacency[target].append(edge_id)
        return edge_id
    
    def set_entry_point(self, node_id: str):
        """Set the entry point (first node after start)"""
        self.add_edge("__start__", node_id)
    
    def set_exit_point(self, node_id: str):
        """Set the exit point (last node before end)"""
        self.add_edge(node_id, "__end__")
    
    def get_next_nodes(
        self,
        current_node: str,
        context: Any = None
    ) -> List[str]:
        """Get the next nodes to execute based on edges and conditions"""
        next_nodes = []
        edge_ids = self.adjacency.get(current_node, [])
        
        # Sort by priority (higher first)
        sorted_edges = sorted(
            [self.edges[eid] for eid in edge_ids],
            key=lambda e: e.priority,
            reverse=True
        )
        
        for edge in sorted_edges:
            if edge.edge_type == EdgeType.SEQUENTIAL:
                next_nodes.append(edge.target_node)
                edge.traversal_count += 1
                break  # Only one sequential path
            
            elif edge.edge_type == EdgeType.CONDITIONAL:
                if edge.condition and edge.condition(context):
                    next_nodes.append(edge.target_node)
                    edge.traversal_count += 1
                    break  # First matching condition wins
            
            elif edge.edge_type == EdgeType.PARALLEL:
                next_nodes.append(edge.target_node)
                edge.traversal_count += 1
                # Continue to collect all parallel targets
            
            elif edge.edge_type == EdgeType.FALLBACK:
                # Fallback edges are handled during error recovery
                continue
        
        return next_nodes
    
    def get_parallel_targets(self, source_node: str) -> List[str]:
        """Get all parallel execution targets from a node"""
        targets = []
        for edge_id in self.adjacency.get(source_node, []):
            edge = self.edges[edge_id]
            if edge.edge_type == EdgeType.PARALLEL:
                targets.append(edge.target_node)
        return targets
    
    def validate(self) -> List[str]:
        """Validate the workflow graph
        
        Returns list of validation errors (empty if valid)
        """
        errors = []
        
        # Check that start has outgoing edges
        if not self.adjacency.get("__start__"):
            errors.append("Workflow has no entry point")
        
        # Check that all nodes (except end) have outgoing edges
        for node_id in self.nodes:
            if node_id == "__end__":
                continue
            if not self.adjacency.get(node_id):
                errors.append(f"Node {node_id} has no outgoing edges")
        
        # Check for cycles (not allowed in DAG)
        if self._has_cycle():
            errors.append("Workflow contains cycles (not a valid DAG)")
        
        # Check that all edge targets exist
        for edge in self.edges.values():
            if edge.target_node not in self.nodes:
                errors.append(f"Edge {edge.edge_id} targets non-existent node")
            if edge.source_node not in self.nodes:
                errors.append(f"Edge {edge.edge_id} originates from non-existent node")
        
        return errors
    
    def _has_cycle(self) -> bool:
        """Check if graph has cycles using DFS"""
        visited = set()
        rec_stack = set()
        
        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for edge_id in self.adjacency.get(node, []):
                target = self.edges[edge_id].target_node
                if target not in visited:
                    if dfs(target):
                        return True
                elif target in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in self.nodes:
            if node not in visited:
                if dfs(node):
                    return True
        
        return False
    
    def to_dict(self) -> Dict:
        """Serialize workflow to dictionary"""
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'description': self.description,
            'nodes': [
                {
                    'node_id': n.node_id,
                    'name': n.name,
                    'type': n.node_type.value,
                    'service_name': n.service_name,
                    'config': n.config
                }
                for n in self.nodes.values()
            ],
            'edges': [
                {
                    'edge_id': e.edge_id,
                    'source': e.source_node,
                    'target': e.target_node,
                    'type': e.edge_type.value,
                    'priority': e.priority
                }
                for e in self.edges.values()
            ]
        }
    
    @classmethod
    def from_manifest(cls, manifest: Dict) -> 'WorkflowGraph':
        """Create workflow from AOL manifest
        
        Maps manifest collections and accessRequests to workflow nodes
        """
        metadata = manifest.get('metadata', {})
        spec = manifest.get('spec', {})
        
        workflow = cls(
            workflow_id=str(uuid.uuid4()),
            name=metadata.get('name', 'unnamed-workflow'),
            description=spec.get('description', '')
        )
        
        # Create nodes from collections (owned data = processing nodes)
        collections = spec.get('dataRequirements', {}).get('collections', [])
        for collection in collections:
            node = WorkflowNode(
                node_id=collection.get('name'),
                name=collection.get('name'),
                node_type=NodeType.AGENT,
                service_name=metadata.get('name'),
                config=collection.get('schemaHint', {})
            )
            workflow.add_node(node)
        
        # Create edges from accessRequests (dependencies)
        access_requests = spec.get('dataRequirements', {}).get('accessRequests', [])
        for access in access_requests:
            # Parse collection reference (service.collection)
            ref = access.get('collection', '')
            parts = ref.split('.')
            if len(parts) >= 2:
                source_service = parts[0]
                source_collection = parts[1]
                
                # Create edge from accessed collection to local processing
                for collection in collections:
                    workflow.add_edge(
                        source=source_collection,
                        target=collection.get('name'),
                        edge_type=EdgeType.SEQUENTIAL
                    )
        
        return workflow


class WorkflowExecutor:
    """Executes workflow graphs with async support"""
    
    def __init__(
        self,
        service_invoker: Optional[Callable] = None,
        event_store: Optional[Any] = None
    ):
        self.service_invoker = service_invoker
        self.event_store = event_store
        self.active_executions: Dict[str, WorkflowState] = {}
        self.logger = logging.getLogger(__name__)
    
    async def execute(
        self,
        workflow: WorkflowGraph,
        initial_input: Any = None,
        timeout_seconds: float = 300.0
    ) -> Dict:
        """Execute a workflow from start to end"""
        execution_id = str(uuid.uuid4())
        
        # Validate workflow
        errors = workflow.validate()
        if errors:
            return {
                'success': False,
                'execution_id': execution_id,
                'errors': errors
            }
        
        # Initialize state
        state = WorkflowState(
            workflow_id=workflow.workflow_id,
            execution_id=execution_id,
            current_nodes={"__start__"},
            completed_nodes=set(),
            node_outputs={"__start__": initial_input},
            global_state={'input': initial_input},
            started_at=datetime.utcnow()
        )
        self.active_executions[execution_id] = state
        
        # Emit workflow started event
        if self.event_store:
            await self.event_store.start_workflow(
                workflow_id=workflow.workflow_id,
                workflow_type=workflow.name,
                agents=[
                    n.service_name for n in workflow.nodes.values()
                    if n.service_name
                ],
                metadata={'execution_id': execution_id}
            )
        
        try:
            # Execute workflow
            result = await asyncio.wait_for(
                self._execute_from_node(workflow, state, "__start__"),
                timeout=timeout_seconds
            )
            
            # Mark workflow complete
            if self.event_store:
                await self.event_store.complete_workflow(
                    workflow_id=workflow.workflow_id,
                    success=True,
                    result={'output': result}
                )
            
            return {
                'success': True,
                'execution_id': execution_id,
                'result': result,
                'completed_nodes': list(state.completed_nodes),
                'duration_seconds': (datetime.utcnow() - state.started_at).total_seconds()
            }
            
        except asyncio.TimeoutError:
            state.error = "Workflow execution timeout"
            if self.event_store:
                await self.event_store.complete_workflow(
                    workflow_id=workflow.workflow_id,
                    success=False,
                    result={'error': state.error}
                )
            return {
                'success': False,
                'execution_id': execution_id,
                'error': state.error
            }
        except Exception as e:
            state.error = str(e)
            if self.event_store:
                await self.event_store.complete_workflow(
                    workflow_id=workflow.workflow_id,
                    success=False,
                    result={'error': state.error}
                )
            return {
                'success': False,
                'execution_id': execution_id,
                'error': state.error
            }
        finally:
            self.active_executions.pop(execution_id, None)
    
    async def _execute_from_node(
        self,
        workflow: WorkflowGraph,
        state: WorkflowState,
        node_id: str
    ) -> Any:
        """Execute workflow starting from a specific node"""
        node = workflow.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        
        # Mark as current
        state.current_nodes.add(node_id)
        
        # Execute node (unless start/end)
        if node.node_type not in [NodeType.START, NodeType.END]:
            result = await self._execute_node(workflow, state, node)
            state.node_outputs[node_id] = result
        else:
            result = state.node_outputs.get(node_id)
        
        # Mark as completed
        state.completed_nodes.add(node_id)
        state.current_nodes.discard(node_id)
        
        # Check for end
        if node.node_type == NodeType.END:
            return state.global_state
        
        # Get next nodes
        context = {
            'current_output': result,
            'state': state.global_state,
            'node_outputs': state.node_outputs
        }
        next_nodes = workflow.get_next_nodes(node_id, context)
        
        if not next_nodes:
            return result
        
        # Check for parallel execution
        parallel_targets = workflow.get_parallel_targets(node_id)
        
        if len(parallel_targets) > 1:
            # Execute in parallel
            tasks = [
                self._execute_from_node(workflow, state, next_node)
                for next_node in parallel_targets
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Aggregate results
            state.global_state['parallel_results'] = results
            
            # Find aggregator or continue to end
            # For now, return first successful result
            for r in results:
                if not isinstance(r, Exception):
                    return r
            raise results[0] if results else ValueError("No parallel results")
        
        else:
            # Sequential execution
            return await self._execute_from_node(
                workflow, state, next_nodes[0]
            )
    
    async def _execute_node(
        self,
        workflow: WorkflowGraph,
        state: WorkflowState,
        node: WorkflowNode
    ) -> Any:
        """Execute a single node"""
        start_time = datetime.utcnow()
        
        try:
            node.execution_count += 1
            
            # Get input for this node
            input_data = self._get_node_input(workflow, state, node)
            
            if node.node_type == NodeType.AGENT and self.service_invoker:
                # Invoke AOL service
                result = await self.service_invoker(
                    service_name=node.service_name,
                    method="Process",
                    input_data=input_data,
                    timeout=node.timeout_seconds
                )
            
            elif node.node_type == NodeType.ROUTER:
                # Router just passes through, routing logic is in edges
                result = input_data
            
            elif node.node_type == NodeType.AGGREGATOR:
                # Aggregate inputs from multiple sources
                result = self._aggregate_inputs(workflow, state, node)
            
            elif node.node_type == NodeType.CHECKPOINT:
                # Save state checkpoint
                state.global_state[f"checkpoint_{node.node_id}"] = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'state': dict(state.global_state)
                }
                result = input_data
            
            else:
                # Default: pass through
                result = input_data
            
            # Update metrics
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            node.total_latency_ms += latency_ms
            node.success_count += 1
            
            # Record contribution
            if self.event_store and node.service_name:
                await self.event_store.record_contribution(
                    agent_id=node.service_name,
                    workflow_id=workflow.workflow_id,
                    turn_number=node.execution_count,
                    action_type=node.node_type.value,
                    latency_ms=latency_ms,
                    success=True
                )
            
            return result
            
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            node.total_latency_ms += latency_ms
            
            # Record failed contribution
            if self.event_store and node.service_name:
                await self.event_store.record_contribution(
                    agent_id=node.service_name,
                    workflow_id=workflow.workflow_id,
                    turn_number=node.execution_count,
                    action_type=node.node_type.value,
                    latency_ms=latency_ms,
                    success=False
                )
            
            # Check for fallback edges
            fallback_target = self._get_fallback_target(workflow, node.node_id)
            if fallback_target:
                self.logger.warning(
                    f"Node {node.node_id} failed, using fallback to {fallback_target}"
                )
                return await self._execute_from_node(workflow, state, fallback_target)
            
            raise
    
    def _get_node_input(
        self,
        workflow: WorkflowGraph,
        state: WorkflowState,
        node: WorkflowNode
    ) -> Any:
        """Get input data for a node from predecessor outputs"""
        # Get all predecessor nodes
        predecessors = []
        for edge_id in workflow.reverse_adjacency.get(node.node_id, []):
            edge = workflow.edges[edge_id]
            if edge.source_node in state.completed_nodes:
                predecessors.append(edge.source_node)
        
        if not predecessors:
            return state.global_state.get('input')
        
        if len(predecessors) == 1:
            return state.node_outputs.get(predecessors[0])
        
        # Multiple predecessors - combine outputs
        return {
            pred: state.node_outputs.get(pred)
            for pred in predecessors
        }
    
    def _aggregate_inputs(
        self,
        workflow: WorkflowGraph,
        state: WorkflowState,
        node: WorkflowNode
    ) -> Any:
        """Aggregate inputs from multiple predecessor nodes"""
        aggregation_method = node.config.get('aggregation', 'merge')
        inputs = self._get_node_input(workflow, state, node)
        
        if not isinstance(inputs, dict):
            return inputs
        
        if aggregation_method == 'merge':
            # Merge all dictionaries
            result = {}
            for key, value in inputs.items():
                if isinstance(value, dict):
                    result.update(value)
                else:
                    result[key] = value
            return result
        
        elif aggregation_method == 'list':
            # Return as list
            return list(inputs.values())
        
        elif aggregation_method == 'first':
            # Return first non-None value
            for value in inputs.values():
                if value is not None:
                    return value
            return None
        
        return inputs
    
    def _get_fallback_target(
        self,
        workflow: WorkflowGraph,
        node_id: str
    ) -> Optional[str]:
        """Get fallback target for a node if defined"""
        for edge_id in workflow.adjacency.get(node_id, []):
            edge = workflow.edges[edge_id]
            if edge.edge_type == EdgeType.FALLBACK:
                return edge.target_node
        return None


class WorkflowBuilder:
    """Fluent builder for constructing workflows"""
    
    def __init__(self, name: str, description: str = ""):
        self.workflow = WorkflowGraph(
            workflow_id=str(uuid.uuid4()),
            name=name,
            description=description
        )
        self._last_node: Optional[str] = None
    
    def add_agent(
        self,
        name: str,
        service_name: str,
        config: Optional[Dict] = None
    ) -> 'WorkflowBuilder':
        """Add an agent node"""
        node = WorkflowNode(
            node_id=name,
            name=name,
            node_type=NodeType.AGENT,
            service_name=service_name,
            config=config or {}
        )
        self.workflow.add_node(node)
        
        if self._last_node:
            self.workflow.add_edge(self._last_node, name)
        else:
            self.workflow.set_entry_point(name)
        
        self._last_node = name
        return self
    
    def add_router(
        self,
        name: str,
        routes: Dict[str, Callable[[Any], bool]]
    ) -> 'WorkflowBuilder':
        """Add a conditional router node"""
        node = WorkflowNode(
            node_id=name,
            name=name,
            node_type=NodeType.ROUTER
        )
        self.workflow.add_node(node)
        
        if self._last_node:
            self.workflow.add_edge(self._last_node, name)
        
        # Add conditional edges for each route
        for target, condition in routes.items():
            self.workflow.add_edge(
                name, target,
                edge_type=EdgeType.CONDITIONAL,
                condition=condition
            )
        
        self._last_node = None  # Router breaks the chain
        return self
    
    def add_parallel(
        self,
        name: str,
        targets: List[str]
    ) -> 'WorkflowBuilder':
        """Add parallel execution branches"""
        # Add parallel edges from last node to all targets
        source = self._last_node or "__start__"
        for target in targets:
            self.workflow.add_edge(
                source, target,
                edge_type=EdgeType.PARALLEL
            )
        
        self._last_node = None  # Parallel breaks the chain
        return self
    
    def add_aggregator(
        self,
        name: str,
        aggregation: str = "merge"
    ) -> 'WorkflowBuilder':
        """Add an aggregator node"""
        node = WorkflowNode(
            node_id=name,
            name=name,
            node_type=NodeType.AGGREGATOR,
            config={'aggregation': aggregation}
        )
        self.workflow.add_node(node)
        self._last_node = name
        return self
    
    def connect(self, source: str, target: str) -> 'WorkflowBuilder':
        """Manually connect two nodes"""
        self.workflow.add_edge(source, target)
        return self
    
    def set_fallback(self, source: str, fallback: str) -> 'WorkflowBuilder':
        """Set a fallback route for a node"""
        self.workflow.add_edge(
            source, fallback,
            edge_type=EdgeType.FALLBACK
        )
        return self
    
    def build(self) -> WorkflowGraph:
        """Build and return the workflow"""
        if self._last_node:
            self.workflow.set_exit_point(self._last_node)
        return self.workflow

