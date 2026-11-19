"""Supercalc-shaped synthetic fixtures for continual testing.

Artificial products only — no production table or metric names.
Arithmetic mirrors the DEMO golden chain so Winston lineage behavior
is verified against Supercalc-like graph shapes (stress, hedge arm, unrelated trust).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from winston.evaluation.calculator import (
    CalculatorInputs,
    DependentCalculator,
    SyntheticCalculator,
)
from winston.lineage.graph import (
    DependencyEdge,
    DependencyGraph,
    EdgeType,
    ExecutionNode,
)
from winston.lineage.replay import ReplayPlan, create_replay_plan
from winston.lineage.traversal import ImpactResult, find_impact


SUPERCALC_DATES = ["S1", "S2", "S3", "S4", "S5"]

SUPERCALC_GOLDEN = {
    "original": {
        "STRESS": {
            "S1": {"level": 101, "carry": 0},
            "S2": {"level": 102, "carry": 0},
            "S3": {"level": 103, "carry": 0},
            "S4": {"level": 104, "carry": 0},
            "S5": {"level": 105, "carry": 0},
        },
        "HEDGE_ARM": {
            "S3": {"level": 206},
        },
        "TRUST_UNRELATED": {
            "S1": {"level": 42},
            "S2": {"level": 42},
            "S3": {"level": 42},
            "S4": {"level": 42},
            "S5": {"level": 42},
        },
    },
    "corrected": {
        "STRESS": {
            "S1": {"level": 101, "carry": 0},
            "S2": {"level": 102, "carry": 5},
            "S3": {"level": 108, "carry": 0},
            "S4": {"level": 109, "carry": 0},
            "S5": {"level": 110, "carry": 0},
        },
        "HEDGE_ARM": {
            "S3": {"level": 216},
        },
        "TRUST_UNRELATED": {
            "S1": {"level": 42},
            "S2": {"level": 42},
            "S3": {"level": 42},
            "S4": {"level": 42},
            "S5": {"level": 42},
        },
    },
}


def create_execution_id(
    index_id: str,
    date: str,
    scenario: str = "original",
) -> str:
    """Create a deterministic Supercalc fixture execution ID."""
    return f"{index_id}_{date}_{scenario}"


def create_supercalc_graph(scenario: str = "original") -> DependencyGraph:
    """Build STRESS → HEDGE_ARM graph with TRUST_UNRELATED independent branch."""
    graph = DependencyGraph()
    golden = SUPERCALC_GOLDEN.get(scenario, SUPERCALC_GOLDEN["original"])

    for date in SUPERCALC_DATES:
        state = golden.get("STRESS", {}).get(date, {})
        graph.add_node(
            ExecutionNode(
                execution_id=create_execution_id("STRESS", date, scenario),
                index_id="STRESS",
                business_date=date,
                environment="synthetic",
                status="succeeded",
                state_content=state,
            )
        )

    for i, date in enumerate(SUPERCALC_DATES[1:], 1):
        graph.add_edge(
            DependencyEdge(
                source_execution_id=create_execution_id(
                    "STRESS", SUPERCALC_DATES[i - 1], scenario
                ),
                target_execution_id=create_execution_id("STRESS", date, scenario),
                edge_type=EdgeType.PARENT_STATE,
                evidence_category="observed",
            )
        )

    hedge_state = golden.get("HEDGE_ARM", {}).get("S3", {})
    graph.add_node(
        ExecutionNode(
            execution_id=create_execution_id("HEDGE_ARM", "S3", scenario),
            index_id="HEDGE_ARM",
            business_date="S3",
            environment="synthetic",
            status="succeeded",
            state_content=hedge_state,
        )
    )
    graph.add_edge(
        DependencyEdge(
            source_execution_id=create_execution_id("STRESS", "S3", scenario),
            target_execution_id=create_execution_id("HEDGE_ARM", "S3", scenario),
            edge_type=EdgeType.CROSS_INDEX,
            evidence_category="observed",
        )
    )

    for date in SUPERCALC_DATES:
        state = golden.get("TRUST_UNRELATED", {}).get(date, {"level": 42})
        graph.add_node(
            ExecutionNode(
                execution_id=create_execution_id("TRUST_UNRELATED", date, scenario),
                index_id="TRUST_UNRELATED",
                business_date=date,
                environment="synthetic",
                status="succeeded",
                state_content=state,
            )
        )

    for i, date in enumerate(SUPERCALC_DATES[1:], 1):
        graph.add_edge(
            DependencyEdge(
                source_execution_id=create_execution_id(
                    "TRUST_UNRELATED", SUPERCALC_DATES[i - 1], scenario
                ),
                target_execution_id=create_execution_id(
                    "TRUST_UNRELATED", date, scenario
                ),
                edge_type=EdgeType.PARENT_STATE,
                evidence_category="observed",
            )
        )

    return graph


def verify_supercalc_golden_values() -> Dict[str, bool]:
    """Verify calculator output matches Supercalc synthetic golden values."""
    calc = SyntheticCalculator()
    hedge = DependentCalculator(multiplier=2)
    results: Dict[str, bool] = {}

    original = calc.calculate_chain([CalculatorInputs(x=1, q=0) for _ in range(5)])
    results["stress_original_levels"] = [s.level for s in original] == [
        101,
        102,
        103,
        104,
        105,
    ]

    corrected = calc.calculate_chain(
        [
            CalculatorInputs(x=1, q=0),
            CalculatorInputs(x=1, q=5),
            CalculatorInputs(x=1, q=0),
            CalculatorInputs(x=1, q=0),
            CalculatorInputs(x=1, q=0),
        ]
    )
    results["stress_corrected_levels"] = [s.level for s in corrected] == [
        101,
        102,
        108,
        109,
        110,
    ]
    results["s2_level_unchanged"] = (
        original[1].level == corrected[1].level == 102
        and corrected[1].carry == 5
    )
    results["hedge_original"] = hedge.calculate(original[2].level) == 206
    results["hedge_corrected"] = hedge.calculate(corrected[2].level) == 216
    results["trust_unrelated_constant"] = all(
        SUPERCALC_GOLDEN["corrected"]["TRUST_UNRELATED"][d]["level"] == 42
        for d in SUPERCALC_DATES
    )
    return results


def analyze_supercalc_late_correction() -> Dict[str, Any]:
    """Run the supercalc-late-correction offline case end-to-end.

    Returns a structured report suitable for CLI JSON output and tests.
    """
    graph = create_supercalc_graph("original")
    origin_id = create_execution_id("STRESS", "S2", "original")
    impact = find_impact(graph, origin_id, change_field="state.carry")

    affected_indices: Set[str] = set(impact.affected_indices)
    affected_dates = sorted(
        {
            graph.get_node(eid).business_date
            for eid in impact.all_affected
            if graph.get_node(eid) is not None
        }
    )

    unrelated_hit = [
        eid
        for eid in impact.all_affected
        if eid.startswith("TRUST_UNRELATED_")
    ]

    plan = create_replay_plan(
        graph,
        impact.all_affected,
        checkpoint_execution_id=origin_id,
        endpoint_date="S5",
        scenario="corrected_plan",
    )

    original_levels = {
        d: SUPERCALC_GOLDEN["original"]["STRESS"][d]["level"] for d in SUPERCALC_DATES
    }
    corrected_levels = {
        d: SUPERCALC_GOLDEN["corrected"]["STRESS"][d]["level"] for d in SUPERCALC_DATES
    }

    missing_sessions = _find_missing_sessions(graph, "STRESS", SUPERCALC_DATES)

    return {
        "case": "supercalc-late-correction",
        "offline": True,
        "capability_label": "fixture-verified",
        "change": {
            "id": "S2_Q_CORRECTION",
            "index": "STRESS",
            "origin_date": "S2",
            "field": "q",
            "original_value": 0,
            "corrected_value": 5,
            "note": "S2 displayed level unchanged; carry changes and propagates",
        },
        "as_executed_history": original_levels,
        "corrected_plan_levels": corrected_levels,
        "hedge_arm": {
            "original_s3": SUPERCALC_GOLDEN["original"]["HEDGE_ARM"]["S3"]["level"],
            "corrected_s3": SUPERCALC_GOLDEN["corrected"]["HEDGE_ARM"]["S3"]["level"],
        },
        "impact": {
            "origin_execution_id": origin_id,
            "complete": impact.complete,
            "affected_indices": sorted(affected_indices),
            "affected_dates": affected_dates,
            "directly_affected": impact.directly_affected,
            "transitively_affected": impact.transitively_affected,
            "unrelated_excluded": len(unrelated_hit) == 0,
            "unrelated_hits": unrelated_hit,
        },
        "trust": {
            "missing_sessions": missing_sessions,
            "freshness_ok": len(missing_sessions) == 0,
        },
        "repair_plan": plan.to_dict(),
        "assertions": {
            "origin_is_s2": True,
            "stress_s3_to_s5_affected": affected_dates == ["S3", "S4", "S5"]
            or set(affected_dates) >= {"S3", "S4", "S5"},
            "hedge_arm_affected": "HEDGE_ARM" in affected_indices,
            "trust_unrelated_excluded": len(unrelated_hit) == 0,
            "history_preserved": original_levels
            == {d: SUPERCALC_GOLDEN["original"]["STRESS"][d]["level"] for d in SUPERCALC_DATES},
        },
    }


def _find_missing_sessions(
    graph: DependencyGraph,
    index_id: str,
    expected_dates: List[str],
) -> List[str]:
    """Return expected dates with no execution node for the index."""
    found = {n.business_date for n in graph.get_all_by_index(index_id)}
    return sorted(set(expected_dates) - found)


def assert_supercalc_late_correction_report(report: Dict[str, Any]) -> None:
    """Raise AssertionError if the late-correction report fails hard guarantees."""
    assertions = report.get("assertions", {})
    failures = [name for name, ok in assertions.items() if not ok]
    if failures:
        raise AssertionError(f"Supercalc late-correction assertions failed: {failures}")
    if not report["impact"]["unrelated_excluded"]:
        raise AssertionError("TRUST_UNRELATED leaked into STRESS impact closure")
    if "HEDGE_ARM" not in report["impact"]["affected_indices"]:
        raise AssertionError("HEDGE_ARM missing from impact")
    if report["change"]["origin_date"] != "S2":
        raise AssertionError("Origin date must be S2")
