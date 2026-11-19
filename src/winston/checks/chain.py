"""Chain-related checks for calculation lineage."""

from __future__ import annotations

from typing import Any, Dict, Optional

from winston.checks.base import Check, CheckResult, CheckSeverity, CheckStatus
from winston.lineage.graph import DependencyGraph, ExecutionNode


class ParentConsumedCheck(Check):
    """Check that the correct parent state was consumed."""
    
    @property
    def check_id(self) -> str:
        return "parent_consumed"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Verify that the execution consumed the expected parent state"
    
    def run(self, context: Dict[str, Any]) -> CheckResult:
        """Run the parent consumed check.
        
        Context should contain:
        - graph: DependencyGraph
        - execution_id: str
        - expected_parent_id: str (optional)
        """
        graph: Optional[DependencyGraph] = context.get("graph")
        execution_id: Optional[str] = context.get("execution_id")
        expected_parent_id: Optional[str] = context.get("expected_parent_id")
        
        if graph is None or execution_id is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Missing required context: graph and execution_id",
                severity=CheckSeverity.WARNING,
            )
        
        node = graph.get_node(execution_id)
        if node is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                f"Execution not found: {execution_id}",
                execution_id=execution_id,
            )
        
        # Get incoming parent edges
        incoming = graph.get_incoming_edges(execution_id)
        parent_edges = [e for e in incoming if e.edge_type.value == "parent_state"]
        
        if not parent_edges:
            # No parent - could be D1
            if expected_parent_id is not None:
                return self._create_result(
                    CheckStatus.FAIL,
                    f"Expected parent {expected_parent_id} but no parent edge found",
                    execution_id=execution_id,
                    expected=expected_parent_id,
                    observed="no parent",
                    severity=CheckSeverity.ERROR,
                )
            return self._create_result(
                CheckStatus.PASS,
                "No parent expected, none found (initial date)",
                execution_id=execution_id,
                index_id=node.index_id,
                business_date=node.business_date,
            )
        
        actual_parent_id = parent_edges[0].source_execution_id
        
        if expected_parent_id is not None and actual_parent_id != expected_parent_id:
            return self._create_result(
                CheckStatus.FAIL,
                f"Wrong parent consumed: expected {expected_parent_id}, got {actual_parent_id}",
                execution_id=execution_id,
                expected=expected_parent_id,
                observed=actual_parent_id,
                severity=CheckSeverity.ERROR,
            )
        
        return self._create_result(
            CheckStatus.PASS,
            f"Correct parent consumed: {actual_parent_id}",
            execution_id=execution_id,
            index_id=node.index_id,
            business_date=node.business_date,
            observed=actual_parent_id,
        )


class StateContinuityCheck(Check):
    """Check state continuity across the chain."""
    
    @property
    def check_id(self) -> str:
        return "state_continuity"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Verify state continuity from parent to child"
    
    def run(self, context: Dict[str, Any]) -> CheckResult:
        """Run the state continuity check.
        
        Context should contain:
        - graph: DependencyGraph
        - execution_id: str
        - expected_parent_state: dict (optional)
        """
        graph: Optional[DependencyGraph] = context.get("graph")
        execution_id: Optional[str] = context.get("execution_id")
        expected_parent_state: Optional[Dict] = context.get("expected_parent_state")
        
        if graph is None or execution_id is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Missing required context",
                severity=CheckSeverity.WARNING,
            )
        
        node = graph.get_node(execution_id)
        if node is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                f"Execution not found: {execution_id}",
            )
        
        # Get parent
        predecessors = graph.get_predecessors(execution_id)
        if not predecessors:
            return self._create_result(
                CheckStatus.PASS,
                "No predecessor (initial date)",
                execution_id=execution_id,
                index_id=node.index_id,
                business_date=node.business_date,
            )
        
        parent = predecessors[0]
        parent_state = parent.state_content
        
        if parent_state is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Parent state content not available",
                execution_id=execution_id,
                severity=CheckSeverity.WARNING,
            )
        
        if expected_parent_state is not None:
            # Compare expected vs actual parent state
            if parent_state != expected_parent_state:
                return self._create_result(
                    CheckStatus.FAIL,
                    "Parent state does not match expected",
                    execution_id=execution_id,
                    expected=str(expected_parent_state),
                    observed=str(parent_state),
                    severity=CheckSeverity.ERROR,
                )
        
        return self._create_result(
            CheckStatus.PASS,
            f"State continuity verified from {parent.execution_id}",
            execution_id=execution_id,
            index_id=node.index_id,
            business_date=node.business_date,
            observed=str(parent_state),
        )


class MissingExecutionCheck(Check):
    """Check for missing expected executions."""
    
    @property
    def check_id(self) -> str:
        return "missing_execution"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Check for missing expected executions in the schedule"
    
    def run(self, context: Dict[str, Any]) -> CheckResult:
        """Run the missing execution check.
        
        Context should contain:
        - graph: DependencyGraph
        - index_id: str
        - expected_dates: list[str]
        """
        graph: Optional[DependencyGraph] = context.get("graph")
        index_id: Optional[str] = context.get("index_id")
        expected_dates: Optional[list] = context.get("expected_dates")
        
        if graph is None or index_id is None or expected_dates is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Missing required context: graph, index_id, expected_dates",
                severity=CheckSeverity.WARNING,
            )
        
        # Find all executions for this index
        nodes = graph.get_all_by_index(index_id)
        found_dates = {n.business_date for n in nodes}
        
        missing = set(expected_dates) - found_dates
        
        if missing:
            return self._create_result(
                CheckStatus.FAIL,
                f"Missing executions for dates: {sorted(missing)}",
                index_id=index_id,
                expected=str(sorted(expected_dates)),
                observed=str(sorted(found_dates)),
                severity=CheckSeverity.ERROR,
            )
        
        return self._create_result(
            CheckStatus.PASS,
            f"All expected dates have executions: {sorted(expected_dates)}",
            index_id=index_id,
        )
