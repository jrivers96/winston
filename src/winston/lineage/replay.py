"""Replay planning for recalculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from winston.lineage.graph import DependencyGraph, ExecutionNode


@dataclass
class ReplayStep:
    """A single step in a replay plan."""
    
    # Step identification
    step_id: str
    order: int
    
    # What to replay
    index_id: str
    business_date: str
    environment: str
    
    # Reference to historical execution
    historical_execution_id: Optional[str] = None
    
    # Required inputs (references to other plan steps or existing artifacts)
    required_inputs: List[str] = field(default_factory=list)
    
    # Reason for inclusion
    reason: str = ""
    
    # Dependencies within the plan (step_ids)
    depends_on: List[str] = field(default_factory=list)
    
    # Planned output references
    planned_state_ref: Optional[str] = None
    planned_output_ref: Optional[str] = None
    
    # Verification requirements
    verification: List[str] = field(default_factory=list)
    
    # Gaps
    gaps: List[str] = field(default_factory=list)


@dataclass
class ReplayPlan:
    """A dry-run recalculation plan.
    
    Plans the steps needed to recalculate from a valid checkpoint
    through to the requested endpoint.
    """
    
    # Plan identification
    plan_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Scope
    scenario: str = "corrected_plan"  # as_executed, counterfactual, corrected_plan
    
    # Checkpoint - where valid state exists
    checkpoint_execution_id: Optional[str] = None
    checkpoint_date: Optional[str] = None
    
    # Endpoint
    endpoint_date: str = ""
    
    # Steps in topological order
    steps: List[ReplayStep] = field(default_factory=list)
    
    # Indices involved
    affected_indices: Set[str] = field(default_factory=set)
    
    # Whether plan is complete
    complete: bool = True
    gaps: List[str] = field(default_factory=list)
    
    # Statistics
    total_steps: int = 0
    
    def add_step(self, step: ReplayStep) -> None:
        """Add a step to the plan."""
        self.steps.append(step)
        self.affected_indices.add(step.index_id)
        self.total_steps = len(self.steps)
    
    def get_step(self, step_id: str) -> Optional[ReplayStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary for serialization."""
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at.isoformat(),
            "scenario": self.scenario,
            "checkpoint_execution_id": self.checkpoint_execution_id,
            "checkpoint_date": self.checkpoint_date,
            "endpoint_date": self.endpoint_date,
            "steps": [
                {
                    "step_id": s.step_id,
                    "order": s.order,
                    "index_id": s.index_id,
                    "business_date": s.business_date,
                    "environment": s.environment,
                    "historical_execution_id": s.historical_execution_id,
                    "required_inputs": s.required_inputs,
                    "reason": s.reason,
                    "depends_on": s.depends_on,
                    "verification": s.verification,
                    "gaps": s.gaps,
                }
                for s in self.steps
            ],
            "affected_indices": list(self.affected_indices),
            "complete": self.complete,
            "gaps": self.gaps,
            "total_steps": self.total_steps,
        }


def create_replay_plan(
    graph: DependencyGraph,
    affected_executions: List[str],
    checkpoint_execution_id: Optional[str] = None,
    endpoint_date: Optional[str] = None,
    scenario: str = "corrected_plan",
) -> ReplayPlan:
    """Create a replay plan for affected executions.
    
    Args:
        graph: The dependency graph
        affected_executions: Executions that need to be replayed
        checkpoint_execution_id: Optional valid checkpoint to start from
        endpoint_date: Optional date to stop at
        scenario: Scenario type
        
    Returns:
        ReplayPlan with ordered steps
    """
    from uuid import uuid4
    
    plan = ReplayPlan(
        plan_id=f"plan_{uuid4().hex[:12]}",
        scenario=scenario,
        checkpoint_execution_id=checkpoint_execution_id,
        endpoint_date=endpoint_date or "",
    )
    
    if checkpoint_execution_id:
        checkpoint_node = graph.get_node(checkpoint_execution_id)
        if checkpoint_node:
            plan.checkpoint_date = checkpoint_node.business_date
    
    # Sort affected executions topologically
    # Build a subgraph of just the affected executions
    affected_set = set(affected_executions)
    
    # Get dependencies within the affected set
    deps: Dict[str, Set[str]] = {eid: set() for eid in affected_executions}
    for eid in affected_executions:
        for edge in graph.get_incoming_edges(eid):
            if edge.source_execution_id in affected_set:
                deps[eid].add(edge.source_execution_id)
    
    # Topological sort of affected executions
    sorted_executions = []
    remaining = set(affected_executions)
    
    while remaining:
        # Find executions with no remaining dependencies
        ready = [
            eid for eid in remaining
            if not (deps[eid] & remaining)
        ]
        
        if not ready:
            # Cycle detected - just pick one to break it
            ready = [next(iter(remaining))]
            plan.gaps.append(f"Possible cycle involving {ready[0]}")
        
        # Sort ready executions by date for determinism
        ready_nodes = [(eid, graph.get_node(eid)) for eid in ready]
        ready_nodes.sort(key=lambda x: (x[1].business_date if x[1] else "", x[0]))
        
        for eid, _ in ready_nodes:
            sorted_executions.append(eid)
            remaining.remove(eid)
    
    # Create steps
    step_ids: Dict[str, str] = {}  # execution_id -> step_id
    
    for order, exec_id in enumerate(sorted_executions):
        node = graph.get_node(exec_id)
        if node is None:
            plan.gaps.append(f"Missing node for {exec_id}")
            continue
        
        step_id = f"step_{order + 1:03d}"
        step_ids[exec_id] = step_id
        
        # Find dependencies within plan
        step_deps = [
            step_ids[dep_eid]
            for dep_eid in deps[exec_id]
            if dep_eid in step_ids
        ]
        
        step = ReplayStep(
            step_id=step_id,
            order=order + 1,
            index_id=node.index_id,
            business_date=node.business_date,
            environment=node.environment,
            historical_execution_id=exec_id,
            reason="Affected by upstream change",
            depends_on=step_deps,
        )
        
        # Add verification requirements
        step.verification.append("Compare output to original")
        
        plan.add_step(step)
    
    # Find the endpoint date
    if plan.steps:
        dates = [s.business_date for s in plan.steps]
        plan.endpoint_date = max(dates)
    
    return plan
