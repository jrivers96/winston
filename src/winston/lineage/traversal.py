"""Graph traversal for backward diagnosis and forward impact."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable

from winston.lineage.graph import DependencyGraph, ExecutionNode, DependencyEdge


@dataclass
class TraversalResult:
    """Result of a graph traversal."""
    
    # Nodes visited in traversal order
    visited: List[str] = field(default_factory=list)
    
    # Edges traversed
    edges: List[DependencyEdge] = field(default_factory=list)
    
    # Stopping points
    checkpoints: List[str] = field(default_factory=list)
    
    # Nodes at the frontier (not explored due to budget or missing data)
    frontier: List[str] = field(default_factory=list)
    
    # Whether traversal completed or was truncated
    complete: bool = True
    truncation_reason: Optional[str] = None
    
    # Statistics
    nodes_visited: int = 0
    edges_traversed: int = 0


@dataclass
class TraversalBudget:
    """Budget limits for graph traversal."""
    
    max_nodes: int = 1000
    max_edges: int = 5000
    max_depth: int = 100
    
    # Current usage
    nodes_used: int = 0
    edges_used: int = 0
    
    def can_continue(self) -> bool:
        """Check if we can continue traversal."""
        return (
            self.nodes_used < self.max_nodes
            and self.edges_used < self.max_edges
        )
    
    def use_node(self) -> bool:
        """Record using a node. Returns False if over budget."""
        self.nodes_used += 1
        return self.nodes_used <= self.max_nodes
    
    def use_edge(self) -> bool:
        """Record using an edge. Returns False if over budget."""
        self.edges_used += 1
        return self.edges_used <= self.max_edges


def backward_traverse(
    graph: DependencyGraph,
    start_execution_id: str,
    budget: Optional[TraversalBudget] = None,
    stop_condition: Optional[Callable[[ExecutionNode], bool]] = None,
) -> TraversalResult:
    """Traverse backward through dependencies to find ancestors.
    
    Args:
        graph: The dependency graph
        start_execution_id: Execution to start from
        budget: Optional budget limits
        stop_condition: Optional function that returns True to stop at a node
        
    Returns:
        TraversalResult with visited nodes and edges
    """
    if budget is None:
        budget = TraversalBudget()
    
    result = TraversalResult()
    visited: Set[str] = set()
    queue = [start_execution_id]
    
    while queue and budget.can_continue():
        current_id = queue.pop(0)
        
        if current_id in visited:
            continue
        
        visited.add(current_id)
        result.visited.append(current_id)
        result.nodes_visited += 1
        
        if not budget.use_node():
            result.complete = False
            result.truncation_reason = "node_budget_exceeded"
            result.frontier.extend(queue)
            break
        
        node = graph.get_node(current_id)
        if node is None:
            result.frontier.append(current_id)
            continue
        
        # Check stop condition
        if stop_condition and stop_condition(node):
            result.checkpoints.append(current_id)
            continue
        
        # Get incoming edges (dependencies)
        for edge in graph.get_incoming_edges(current_id):
            result.edges.append(edge)
            result.edges_traversed += 1
            
            if not budget.use_edge():
                result.complete = False
                result.truncation_reason = "edge_budget_exceeded"
                break
            
            if edge.source_execution_id not in visited:
                queue.append(edge.source_execution_id)
    
    if queue:
        result.frontier.extend(queue)
        if result.complete and not budget.can_continue():
            result.complete = False
            result.truncation_reason = result.truncation_reason or "node_budget_exceeded"
    
    return result


def forward_traverse(
    graph: DependencyGraph,
    start_execution_id: str,
    budget: Optional[TraversalBudget] = None,
    stop_condition: Optional[Callable[[ExecutionNode], bool]] = None,
) -> TraversalResult:
    """Traverse forward through dependents to find descendants.
    
    Args:
        graph: The dependency graph
        start_execution_id: Execution to start from
        budget: Optional budget limits
        stop_condition: Optional function that returns True to stop at a node
        
    Returns:
        TraversalResult with visited nodes and edges
    """
    if budget is None:
        budget = TraversalBudget()
    
    result = TraversalResult()
    visited: Set[str] = set()
    queue = [start_execution_id]
    
    while queue and budget.can_continue():
        current_id = queue.pop(0)
        
        if current_id in visited:
            continue
        
        visited.add(current_id)
        result.visited.append(current_id)
        result.nodes_visited += 1
        
        if not budget.use_node():
            result.complete = False
            result.truncation_reason = "node_budget_exceeded"
            result.frontier.extend(queue)
            break
        
        node = graph.get_node(current_id)
        if node is None:
            result.frontier.append(current_id)
            continue
        
        # Check stop condition
        if stop_condition and stop_condition(node):
            result.checkpoints.append(current_id)
            continue
        
        # Get outgoing edges (dependents)
        for edge in graph.get_outgoing_edges(current_id):
            result.edges.append(edge)
            result.edges_traversed += 1
            
            if not budget.use_edge():
                result.complete = False
                result.truncation_reason = "edge_budget_exceeded"
                break
            
            if edge.target_execution_id not in visited:
                queue.append(edge.target_execution_id)
    
    if queue:
        result.frontier.extend(queue)
        if result.complete and not budget.can_continue():
            result.complete = False
            result.truncation_reason = result.truncation_reason or "node_budget_exceeded"
    
    return result


@dataclass
class ImpactResult:
    """Result of impact analysis."""
    
    # The change that triggered the analysis
    change_execution_id: str
    change_field: Optional[str] = None
    
    # Directly affected executions
    directly_affected: List[str] = field(default_factory=list)
    
    # Transitively affected executions
    transitively_affected: List[str] = field(default_factory=list)
    
    # Affected indices
    affected_indices: Set[str] = field(default_factory=set)
    
    # Affected date range
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    
    # Traversal metadata
    traversal: Optional[TraversalResult] = None
    
    # Whether impact is complete or truncated
    complete: bool = True
    
    @property
    def all_affected(self) -> List[str]:
        """All affected executions."""
        return self.directly_affected + self.transitively_affected


def find_impact(
    graph: DependencyGraph,
    change_execution_id: str,
    change_field: Optional[str] = None,
    budget: Optional[TraversalBudget] = None,
) -> ImpactResult:
    """Find all executions affected by a change.
    
    Args:
        graph: The dependency graph
        change_execution_id: Execution where change occurred
        change_field: Optional specific field that changed (e.g., "state.carry")
        budget: Optional budget limits
        
    Returns:
        ImpactResult with affected executions
    """
    result = ImpactResult(
        change_execution_id=change_execution_id,
        change_field=change_field,
    )
    
    # Forward traverse to find all dependents
    traversal = forward_traverse(graph, change_execution_id, budget)
    result.traversal = traversal
    result.complete = traversal.complete
    
    # Categorize affected nodes
    change_node = graph.get_node(change_execution_id)
    
    for exec_id in traversal.visited:
        if exec_id == change_execution_id:
            continue
        
        node = graph.get_node(exec_id)
        if node is None:
            continue
        
        result.affected_indices.add(node.index_id)
        
        # Check if directly connected
        is_direct = any(
            e.source_execution_id == change_execution_id
            for e in graph.get_incoming_edges(exec_id)
        )
        
        if is_direct:
            result.directly_affected.append(exec_id)
        else:
            result.transitively_affected.append(exec_id)
        
        # Track date range
        if result.earliest_date is None or node.business_date < result.earliest_date:
            result.earliest_date = node.business_date
        if result.latest_date is None or node.business_date > result.latest_date:
            result.latest_date = node.business_date
    
    return result
