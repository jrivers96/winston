"""Unit tests for lineage module."""

import pytest

from winston.lineage.graph import (
    DependencyGraph,
    ExecutionNode,
    DependencyEdge,
    EdgeType,
)
from winston.lineage.traversal import (
    backward_traverse,
    forward_traverse,
    find_impact,
    TraversalBudget,
)
from winston.lineage.replay import create_replay_plan
from winston.evaluation.fixtures import create_demo_graph, create_execution_id


class TestDependencyGraph:
    """Test DependencyGraph functionality."""
    
    def test_add_node(self):
        """Test adding nodes to graph."""
        graph = DependencyGraph()
        
        node = ExecutionNode(
            execution_id="exec_1",
            index_id="DEMO",
            business_date="D1",
            environment="synthetic",
        )
        graph.add_node(node)
        
        assert graph.get_node("exec_1") == node
    
    def test_add_edge(self):
        """Test adding edges to graph."""
        graph = DependencyGraph()
        
        # Add nodes
        graph.add_node(ExecutionNode(
            execution_id="exec_1",
            index_id="DEMO",
            business_date="D1",
            environment="synthetic",
        ))
        graph.add_node(ExecutionNode(
            execution_id="exec_2",
            index_id="DEMO",
            business_date="D2",
            environment="synthetic",
        ))
        
        # Add edge
        edge = DependencyEdge(
            source_execution_id="exec_1",
            target_execution_id="exec_2",
            edge_type=EdgeType.PARENT_STATE,
        )
        graph.add_edge(edge)
        
        assert len(graph.get_incoming_edges("exec_2")) == 1
        assert len(graph.get_outgoing_edges("exec_1")) == 1
    
    def test_get_predecessors(self):
        """Test getting predecessor nodes."""
        graph = create_demo_graph("original")
        
        # D2 should have D1 as predecessor
        d2_id = create_execution_id("DEMO", "D2", "original")
        preds = graph.get_predecessors(d2_id)
        
        assert len(preds) == 1
        assert preds[0].business_date == "D1"
    
    def test_get_successors(self):
        """Test getting successor nodes."""
        graph = create_demo_graph("original")
        
        # D2 should have D3 as successor
        d2_id = create_execution_id("DEMO", "D2", "original")
        succs = graph.get_successors(d2_id)
        
        assert len(succs) == 1
        assert succs[0].business_date == "D3"
    
    def test_find_by_index_date(self):
        """Test finding node by index and date."""
        graph = create_demo_graph("original")
        
        node = graph.find_by_index_date("DEMO", "D3")
        
        assert node is not None
        assert node.index_id == "DEMO"
        assert node.business_date == "D3"
    
    def test_topological_sort(self):
        """Test topological sort of graph."""
        graph = create_demo_graph("original")
        
        # Get just DEMO nodes
        demo_nodes = [n for n in graph.nodes if n.startswith("DEMO_D")]
        
        sorted_ids = graph.topological_sort()
        
        # D1 should come before D2, etc.
        d1_idx = sorted_ids.index(create_execution_id("DEMO", "D1", "original"))
        d2_idx = sorted_ids.index(create_execution_id("DEMO", "D2", "original"))
        d3_idx = sorted_ids.index(create_execution_id("DEMO", "D3", "original"))
        
        assert d1_idx < d2_idx < d3_idx


class TestTraversal:
    """Test graph traversal functions."""
    
    def test_backward_traverse_from_d5(self):
        """Test backward traversal from D5 reaches D1."""
        graph = create_demo_graph("original")
        d5_id = create_execution_id("DEMO", "D5", "original")
        
        result = backward_traverse(graph, d5_id)
        
        # Should visit D5, D4, D3, D2, D1
        assert len(result.visited) == 5
        assert d5_id in result.visited
        assert create_execution_id("DEMO", "D1", "original") in result.visited
        assert result.complete
    
    def test_forward_traverse_from_d1(self):
        """Test forward traversal from D1 reaches D5."""
        graph = create_demo_graph("original")
        d1_id = create_execution_id("DEMO", "D1", "original")
        
        result = forward_traverse(graph, d1_id)
        
        # Should visit D1, D2, D3, D4, D5
        assert len(result.visited) == 5
        assert d1_id in result.visited
        assert create_execution_id("DEMO", "D5", "original") in result.visited
    
    def test_traverse_with_budget(self):
        """Test that budget limits traversal."""
        graph = create_demo_graph("original")
        d1_id = create_execution_id("DEMO", "D1", "original")
        
        budget = TraversalBudget(max_nodes=3)
        result = forward_traverse(graph, d1_id, budget)
        
        assert len(result.visited) <= 3
        assert not result.complete
        assert result.truncation_reason == "node_budget_exceeded"
    
    def test_cross_index_dependency(self):
        """Test that DEMO_DEPENDENT is reachable from DEMO D3."""
        graph = create_demo_graph("original")
        d3_id = create_execution_id("DEMO", "D3", "original")
        
        result = forward_traverse(graph, d3_id)
        
        dep_id = create_execution_id("DEMO_DEPENDENT", "D3", "original")
        assert dep_id in result.visited


class TestImpact:
    """Test impact analysis."""
    
    def test_impact_from_d2_correction(self):
        """Test that D2 change impacts D3-D5 and dependent."""
        graph = create_demo_graph("original")
        d2_id = create_execution_id("DEMO", "D2", "original")
        
        impact = find_impact(graph, d2_id, change_field="state.carry")
        
        # Should affect D3, D4, D5, and DEMO_DEPENDENT D3
        assert len(impact.all_affected) >= 4
        
        # D3-D5 should be in affected
        for date in ["D3", "D4", "D5"]:
            exec_id = create_execution_id("DEMO", date, "original")
            assert exec_id in impact.all_affected
        
        # DEMO_DEPENDENT should be affected
        dep_id = create_execution_id("DEMO_DEPENDENT", "D3", "original")
        assert dep_id in impact.all_affected
    
    def test_unrelated_index_not_impacted(self):
        """Test that DEMO_UNRELATED is not impacted by DEMO changes."""
        graph = create_demo_graph("original")
        d2_id = create_execution_id("DEMO", "D2", "original")
        
        impact = find_impact(graph, d2_id)
        
        # DEMO_UNRELATED nodes should NOT be in affected
        for date in ["D1", "D2", "D3", "D4", "D5"]:
            unrelated_id = create_execution_id("DEMO_UNRELATED", date, "original")
            assert unrelated_id not in impact.all_affected
    
    def test_impact_indices(self):
        """Test affected_indices tracking."""
        graph = create_demo_graph("original")
        d2_id = create_execution_id("DEMO", "D2", "original")
        
        impact = find_impact(graph, d2_id)
        
        assert "DEMO" in impact.affected_indices
        assert "DEMO_DEPENDENT" in impact.affected_indices
        assert "DEMO_UNRELATED" not in impact.affected_indices


class TestReplayPlan:
    """Test replay plan generation."""
    
    def test_create_replay_plan(self):
        """Test creating a replay plan for affected executions."""
        graph = create_demo_graph("original")
        
        # Affected executions from D2 change
        affected = [
            create_execution_id("DEMO", "D3", "original"),
            create_execution_id("DEMO", "D4", "original"),
            create_execution_id("DEMO", "D5", "original"),
            create_execution_id("DEMO_DEPENDENT", "D3", "original"),
        ]
        
        checkpoint = create_execution_id("DEMO", "D2", "original")
        
        plan = create_replay_plan(
            graph,
            affected,
            checkpoint_execution_id=checkpoint,
        )
        
        assert plan.total_steps == 4
        assert "DEMO" in plan.affected_indices
        assert "DEMO_DEPENDENT" in plan.affected_indices
    
    def test_replay_plan_ordering(self):
        """Test that replay plan steps are in dependency order."""
        graph = create_demo_graph("original")
        
        affected = [
            create_execution_id("DEMO", "D3", "original"),
            create_execution_id("DEMO", "D4", "original"),
            create_execution_id("DEMO", "D5", "original"),
        ]
        
        plan = create_replay_plan(graph, affected)
        
        # Steps should be in D3, D4, D5 order
        dates = [s.business_date for s in plan.steps]
        assert dates == ["D3", "D4", "D5"]
