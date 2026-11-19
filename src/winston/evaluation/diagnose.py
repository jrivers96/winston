"""Offline diagnose/impact helpers for synthetic profiles."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from winston.evaluation.fixtures import create_demo_graph, create_execution_id
from winston.evaluation.supercalc import (
    SUPERCALC_DATES,
    create_execution_id as sc_exec_id,
    create_supercalc_graph,
)
from winston.lineage.traversal import find_impact


def diagnose_index_date(
    index_id: str,
    business_date: str,
    scenario: str = "as_executed",
    profile: str = "synthetic",
) -> Dict[str, Any]:
    """Diagnose a synthetic index/date using offline fixtures."""
    scenario_key = "original" if scenario in ("as_executed", "original") else "corrected"

    if profile in ("supercalc_synthetic", "supercalc"):
        graph = create_supercalc_graph(scenario_key)
        exec_id = sc_exec_id(index_id, business_date, scenario_key)
        expected_dates = SUPERCALC_DATES
    elif profile == "synthetic":
        graph = create_demo_graph(scenario_key)
        exec_id = create_execution_id(index_id, business_date, scenario_key)
        expected_dates = ["D1", "D2", "D3", "D4", "D5"]
    else:
        raise ValueError(
            f"Unknown offline profile '{profile}'. "
            "Use 'synthetic' or 'supercalc_synthetic'."
        )

    node = graph.get_node(exec_id)
    findings: List[str] = []

    if node is None:
        return {
            "index_id": index_id,
            "business_date": business_date,
            "scenario": scenario,
            "profile": profile,
            "execution_id": None,
            "status": "missing_execution",
            "findings": [
                f"No execution for {index_id}/{business_date} in offline fixtures"
            ],
            "capability_label": "fixture-verified",
        }

    if index_id in ("STRESS", "DEMO"):
        present = {n.business_date for n in graph.get_all_by_index(index_id)}
        missing = sorted(set(expected_dates) - present)
        if missing:
            findings.append(f"Missing scheduled sessions: {missing}")
        else:
            findings.append("All expected sessions present")

    predecessors = graph.get_predecessors(exec_id)
    if predecessors:
        findings.append(f"Consumed parent: {predecessors[0].execution_id}")
    else:
        findings.append("No parent (seed/initial session)")

    return {
        "index_id": index_id,
        "business_date": business_date,
        "scenario": scenario,
        "profile": profile,
        "execution_id": exec_id,
        "status": node.status,
        "state": node.state_content,
        "findings": findings,
        "capability_label": "fixture-verified",
    }


def assess_change_impact(
    change_id: str,
    through_date: str,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Assess impact for a known synthetic change ID."""
    if change_id in ("S2_Q_CORRECTION", "STRESS_S2_Q"):
        resolved_profile = profile or "supercalc_synthetic"
        graph = create_supercalc_graph("original")
        origin = sc_exec_id("STRESS", "S2", "original")
        impact = find_impact(graph, origin, change_field="state.carry")
        unrelated_prefix = "TRUST_UNRELATED_"
    elif change_id in ("D2_Q_CORRECTION", "DEMO_D2_Q"):
        resolved_profile = profile or "synthetic"
        graph = create_demo_graph("original")
        origin = create_execution_id("DEMO", "D2", "original")
        impact = find_impact(graph, origin, change_field="state.carry")
        unrelated_prefix = "DEMO_UNRELATED_"
    else:
        raise ValueError(
            f"Unknown change '{change_id}'. "
            "Known: S2_Q_CORRECTION, D2_Q_CORRECTION"
        )

    unrelated = [eid for eid in impact.all_affected if eid.startswith(unrelated_prefix)]
    affected_dates = sorted(
        {
            graph.get_node(eid).business_date
            for eid in impact.all_affected
            if graph.get_node(eid) is not None
            and graph.get_node(eid).business_date <= through_date
        }
    )
    filtered_affected = [
        eid
        for eid in impact.all_affected
        if graph.get_node(eid)
        and graph.get_node(eid).business_date <= through_date
    ]

    return {
        "change_id": change_id,
        "through": through_date,
        "profile": resolved_profile,
        "origin_execution_id": origin,
        "affected_indices": sorted(impact.affected_indices),
        "affected_dates": affected_dates,
        "unrelated_excluded": len(unrelated) == 0,
        "all_affected": filtered_affected,
        "capability_label": "fixture-verified",
    }
