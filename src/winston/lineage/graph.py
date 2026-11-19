"""Dependency graph for calculation lineage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum


class EdgeType(str, Enum):
    """Type of dependency edge."""
    
    PARENT_STATE = "parent_state"      # Previous day's state consumed
    INPUT_DATA = "input_data"          # Input dataset consumed
    CROSS_INDEX = "cross_index"        # Dependency on another index
    LOOKBACK = "lookback"              # Direct lookback to earlier date


@dataclass
class DependencyEdge:
    """An edge in the calculation dependency graph."""
    
    source_execution_id: str
    target_execution_id: str
    edge_type: EdgeType
    
    # What was consumed
    artifact_id: Optional[str] = None
    field_path: Optional[str] = None  # e.g., "state.carry" for specific field
    
    # Provenance
    evidence_category: str = "observed"  # observed, declared, inferred
    evidence_ref: Optional[str] = None
    
    # Timestamps
    observed_at: Optional[datetime] = None
    
    def __hash__(self) -> int:
        return hash((self.source_execution_id, self.target_execution_id, self.edge_type))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DependencyEdge):
            return False
        return (
            self.source_execution_id == other.source_execution_id
            and self.target_execution_id == other.target_execution_id
            and self.edge_type == other.edge_type
        )


@dataclass
class ExecutionNode:
    """A node in the dependency graph representing an execution."""
    
    execution_id: str
    index_id: str
    business_date: str
    environment: str
    
    # State
    status: str = "succeeded"
    
    # Artifacts
    state_artifact_id: Optional[str] = None
    output_artifact_id: Optional[str] = None
    
    # State content (for inline small states)
    state_content: Optional[Dict[str, Any]] = None
    
    # Selection
    is_selected: bool = True
    selection_policy: Optional[str] = None


@dataclass 
class DependencyGraph:
    """Graph of calculation dependencies.
    
    The calculation DAG must be acyclic for concrete lineage.
    """
    
    nodes: Dict[str, ExecutionNode] = field(default_factory=dict)
    edges: List[DependencyEdge] = field(default_factory=list)
    
    # Index by source and target for fast lookup
    _outgoing: Dict[str, List[DependencyEdge]] = field(default_factory=dict)
    _incoming: Dict[str, List[DependencyEdge]] = field(default_factory=dict)
    
    def add_node(self, node: ExecutionNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.execution_id] = node
        if node.execution_id not in self._outgoing:
            self._outgoing[node.execution_id] = []
        if node.execution_id not in self._incoming:
            self._incoming[node.execution_id] = []
    
    def add_edge(self, edge: DependencyEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)
        
        if edge.source_execution_id not in self._outgoing:
            self._outgoing[edge.source_execution_id] = []
        self._outgoing[edge.source_execution_id].append(edge)
        
        if edge.target_execution_id not in self._incoming:
            self._incoming[edge.target_execution_id] = []
        self._incoming[edge.target_execution_id].append(edge)
    
    def get_node(self, execution_id: str) -> Optional[ExecutionNode]:
        """Get a node by execution ID."""
        return self.nodes.get(execution_id)
    
    def get_predecessors(self, execution_id: str) -> List[ExecutionNode]:
        """Get nodes that this execution depends on (incoming edges)."""
        edges = self._incoming.get(execution_id, [])
        return [
            self.nodes[e.source_execution_id]
            for e in edges
            if e.source_execution_id in self.nodes
        ]
    
    def get_successors(self, execution_id: str) -> List[ExecutionNode]:
        """Get nodes that depend on this execution (outgoing edges)."""
        edges = self._outgoing.get(execution_id, [])
        return [
            self.nodes[e.target_execution_id]
            for e in edges
            if e.target_execution_id in self.nodes
        ]
    
    def get_incoming_edges(self, execution_id: str) -> List[DependencyEdge]:
        """Get edges pointing to this execution."""
        return self._incoming.get(execution_id, [])
    
    def get_outgoing_edges(self, execution_id: str) -> List[DependencyEdge]:
        """Get edges from this execution."""
        return self._outgoing.get(execution_id, [])
    
    def find_by_index_date(
        self, 
        index_id: str, 
        business_date: str,
        environment: Optional[str] = None,
    ) -> Optional[ExecutionNode]:
        """Find a node by index ID and business date."""
        for node in self.nodes.values():
            if node.index_id == index_id and node.business_date == business_date:
                if environment is None or node.environment == environment:
                    return node
        return None
    
    def get_all_by_index(self, index_id: str) -> List[ExecutionNode]:
        """Get all nodes for an index."""
        return [n for n in self.nodes.values() if n.index_id == index_id]
    
    def topological_sort(self) -> List[str]:
        """Return execution IDs in topological order (dependencies first).
        
        Raises:
            ValueError: If the graph contains cycles
        """
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        
        for edge in self.edges:
            if edge.target_execution_id in in_degree:
                in_degree[edge.target_execution_id] += 1
        
        # Start with nodes that have no incoming edges
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []
        
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            
            for edge in self._outgoing.get(node_id, []):
                target = edge.target_execution_id
                if target in in_degree:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)
        
        if len(result) != len(self.nodes):
            raise ValueError("Graph contains cycles - not a valid calculation DAG")
        
        return result
    
    def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the graph.
        
        Returns:
            List of cycles, where each cycle is a list of execution IDs
        """
        cycles = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        def dfs(node_id: str, path: List[str]) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            for edge in self._outgoing.get(node_id, []):
                target = edge.target_execution_id
                if target not in visited:
                    dfs(target, path)
                elif target in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(target)
                    cycles.append(path[cycle_start:] + [target])
            
            path.pop()
            rec_stack.remove(node_id)
        
        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id, [])
        
        return cycles
