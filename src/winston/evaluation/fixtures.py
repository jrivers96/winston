"""Synthetic fixtures for testing.

Golden values from the spec:

Original (all x=1, q=0):
    D1: 101, D2: 102, D3: 103, D4: 104, D5: 105

After D2 q correction (q: 0 -> 5):
    D1: 101, D2: 102 (level unchanged, carry=5)
    D3: 108 (102 + 1 + 5)
    D4: 109
    D5: 110

Dependent index (2x D3):
    Original: 206
    Corrected: 216
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from winston.evaluation.calculator import (
    CalculatorInputs,
    CalculatorState,
    SyntheticCalculator,
    DependentCalculator,
)
from winston.lineage.graph import (
    DependencyGraph,
    ExecutionNode,
    DependencyEdge,
    EdgeType,
)


# Golden values as specified
GOLDEN_VALUES = {
    "original": {
        "DEMO": {
            "D1": {"level": 101, "carry": 0},
            "D2": {"level": 102, "carry": 0},
            "D3": {"level": 103, "carry": 0},
            "D4": {"level": 104, "carry": 0},
            "D5": {"level": 105, "carry": 0},
        },
        "DEMO_DEPENDENT": {
            "D3": {"level": 206},
        },
        "DEMO_UNRELATED": {
            "D1": {"level": 500},
            "D2": {"level": 500},
            "D3": {"level": 500},
            "D4": {"level": 500},
            "D5": {"level": 500},
        },
    },
    "corrected": {
        "DEMO": {
            "D1": {"level": 101, "carry": 0},
            "D2": {"level": 102, "carry": 5},  # Level unchanged, carry changes
            "D3": {"level": 108, "carry": 0},  # 102 + 1 + 5 = 108
            "D4": {"level": 109, "carry": 0},
            "D5": {"level": 110, "carry": 0},
        },
        "DEMO_DEPENDENT": {
            "D3": {"level": 216},  # 2 * 108
        },
    },
    # State reset fixture
    "state_reset_original": {
        "DEMO": {
            "D1": {"level": 101, "carry": 0},
            "D2": {"level": 102, "carry": 0},
            "D3": {"level": 103, "carry": 0},
            "D4": {"level": 200, "carry": 0},  # Reset
            "D5": {"level": 201, "carry": 0},  # 200 + 1 + q[D2]=0
        },
    },
    "state_reset_corrected": {
        "DEMO": {
            "D1": {"level": 101, "carry": 0},
            "D2": {"level": 102, "carry": 5},
            "D3": {"level": 108, "carry": 0},
            "D4": {"level": 200, "carry": 0},  # Reset unchanged
            "D5": {"level": 206, "carry": 0},  # 200 + 1 + q[D2]=5
        },
    },
}


def load_fixture(name: str) -> Dict[str, Any]:
    """Load a named fixture.
    
    Args:
        name: Fixture name (original, corrected, state_reset_original, etc.)
        
    Returns:
        Fixture data
    """
    if name not in GOLDEN_VALUES:
        raise ValueError(f"Unknown fixture: {name}")
    return GOLDEN_VALUES[name]


def create_execution_id(index_id: str, date: str, scenario: str = "original") -> str:
    """Create a deterministic execution ID."""
    return f"{index_id}_{date}_{scenario}"


def create_demo_graph(scenario: str = "original") -> DependencyGraph:
    """Create the DEMO dependency graph for testing.
    
    Creates nodes and edges for:
    - DEMO index D1-D5 (chain)
    - DEMO_DEPENDENT index D3 (depends on DEMO D3)
    - DEMO_UNRELATED index D1-D5 (independent)
    
    Args:
        scenario: "original" or "corrected"
        
    Returns:
        Populated DependencyGraph
    """
    graph = DependencyGraph()
    golden = GOLDEN_VALUES.get(scenario, GOLDEN_VALUES["original"])
    
    # Date labels
    dates = ["D1", "D2", "D3", "D4", "D5"]
    
    # Create DEMO index nodes
    for date in dates:
        exec_id = create_execution_id("DEMO", date, scenario)
        state = golden.get("DEMO", {}).get(date, {})
        
        node = ExecutionNode(
            execution_id=exec_id,
            index_id="DEMO",
            business_date=date,
            environment="synthetic",
            status="succeeded",
            state_content=state,
        )
        graph.add_node(node)
    
    # Create DEMO index edges (chain dependencies)
    for i, date in enumerate(dates[1:], 1):
        edge = DependencyEdge(
            source_execution_id=create_execution_id("DEMO", dates[i-1], scenario),
            target_execution_id=create_execution_id("DEMO", date, scenario),
            edge_type=EdgeType.PARENT_STATE,
            evidence_category="observed",
        )
        graph.add_edge(edge)
    
    # Create DEMO_DEPENDENT node (depends on DEMO D3)
    if "DEMO_DEPENDENT" in golden:
        dep_state = golden["DEMO_DEPENDENT"].get("D3", {})
        dep_node = ExecutionNode(
            execution_id=create_execution_id("DEMO_DEPENDENT", "D3", scenario),
            index_id="DEMO_DEPENDENT",
            business_date="D3",
            environment="synthetic",
            status="succeeded",
            state_content=dep_state,
        )
        graph.add_node(dep_node)
        
        # Edge from DEMO D3 to DEMO_DEPENDENT D3
        dep_edge = DependencyEdge(
            source_execution_id=create_execution_id("DEMO", "D3", scenario),
            target_execution_id=create_execution_id("DEMO_DEPENDENT", "D3", scenario),
            edge_type=EdgeType.CROSS_INDEX,
            evidence_category="observed",
        )
        graph.add_edge(dep_edge)
    
    # Create DEMO_UNRELATED nodes (no dependencies to DEMO)
    if "DEMO_UNRELATED" in golden:
        for date in dates:
            state = golden["DEMO_UNRELATED"].get(date, {"level": 500})
            node = ExecutionNode(
                execution_id=create_execution_id("DEMO_UNRELATED", date, scenario),
                index_id="DEMO_UNRELATED",
                business_date=date,
                environment="synthetic",
                status="succeeded",
                state_content=state,
            )
            graph.add_node(node)
        
        # Chain edges for unrelated index
        for i, date in enumerate(dates[1:], 1):
            edge = DependencyEdge(
                source_execution_id=create_execution_id("DEMO_UNRELATED", dates[i-1], scenario),
                target_execution_id=create_execution_id("DEMO_UNRELATED", date, scenario),
                edge_type=EdgeType.PARENT_STATE,
                evidence_category="observed",
            )
            graph.add_edge(edge)
    
    return graph


def verify_golden_values() -> Dict[str, bool]:
    """Verify that the calculator produces the golden values.
    
    Returns:
        Dict mapping test name to pass/fail
    """
    calc = SyntheticCalculator()
    dep_calc = DependentCalculator(multiplier=2)
    results = {}
    
    # Test original sequence
    original_inputs = [CalculatorInputs(x=1, q=0) for _ in range(5)]
    original_states = calc.calculate_chain(original_inputs)
    
    expected_original = [101, 102, 103, 104, 105]
    actual_original = [s.level for s in original_states]
    results["original_levels"] = actual_original == expected_original
    
    # Test corrected sequence (D2 q=5)
    corrected_inputs = [
        CalculatorInputs(x=1, q=0),  # D1
        CalculatorInputs(x=1, q=5),  # D2 - corrected
        CalculatorInputs(x=1, q=0),  # D3
        CalculatorInputs(x=1, q=0),  # D4
        CalculatorInputs(x=1, q=0),  # D5
    ]
    corrected_states = calc.calculate_chain(corrected_inputs)
    
    expected_corrected = [101, 102, 108, 109, 110]
    actual_corrected = [s.level for s in corrected_states]
    results["corrected_levels"] = actual_corrected == expected_corrected
    
    # Test D2 carry value
    results["d2_carry_corrected"] = corrected_states[1].carry == 5
    
    # Test dependent index
    original_d3 = original_states[2].level  # 103
    corrected_d3 = corrected_states[2].level  # 108
    
    results["dependent_original"] = dep_calc.calculate(original_d3) == 206
    results["dependent_corrected"] = dep_calc.calculate(corrected_d3) == 216
    
    return results
