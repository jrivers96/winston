"""Named offline evaluation cases for Winston replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from winston.evaluation.fixtures import create_demo_graph, verify_golden_values
from winston.evaluation.fixtures import create_execution_id as demo_exec_id
from winston.evaluation.recorded import (
    list_recorded_bundles,
    replay_bundle,
    resolve_bundle_path,
)
from winston.evaluation.supercalc import (
    analyze_supercalc_late_correction,
    assert_supercalc_late_correction_report,
)
from winston.lineage.replay import create_replay_plan
from winston.lineage.traversal import find_impact


CaseFn = Callable[[], Dict[str, Any]]


def _demo_late_correction() -> Dict[str, Any]:
    """DEMO D2 q correction offline case."""
    graph = create_demo_graph("original")
    origin = demo_exec_id("DEMO", "D2", "original")
    impact = find_impact(graph, origin, change_field="state.carry")
    plan = create_replay_plan(
        graph,
        impact.all_affected,
        checkpoint_execution_id=origin,
        endpoint_date="D5",
        scenario="corrected_plan",
    )
    golden_ok = verify_golden_values()
    return {
        "case": "demo-late-correction",
        "offline": True,
        "capability_label": "fixture-verified",
        "change": {
            "id": "D2_Q_CORRECTION",
            "index": "DEMO",
            "origin_date": "D2",
            "field": "q",
        },
        "impact": {
            "origin_execution_id": origin,
            "affected_indices": sorted(impact.affected_indices),
            "all_affected": impact.all_affected,
            "complete": impact.complete,
        },
        "repair_plan": plan.to_dict(),
        "golden_verification": golden_ok,
        "assertions": {
            "demo_in_impact": "DEMO" in impact.affected_indices,
            "dependent_in_impact": "DEMO_DEPENDENT" in impact.affected_indices,
            "unrelated_excluded": "DEMO_UNRELATED" not in impact.affected_indices,
            "golden_ok": all(golden_ok.values()),
        },
    }


def run_case(
    case_id: str,
    offline: bool = True,
    bundle: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a named evaluation case or recorded bundle.

    Args:
        case_id: Case identifier (or 'recorded' when using --bundle)
        offline: When True, refuse live adapters
        bundle: Optional recorded bundle path or sample name

    Returns:
        Structured case report
    """
    if not offline:
        raise ValueError(
            f"Case '{case_id}' is offline-only in v1; pass --offline "
            "(live smoke is Phase D and not enabled here)"
        )

    if bundle or case_id.startswith("recorded:"):
        bundle_ref = bundle or case_id.split(":", 1)[1]
        report = replay_bundle(resolve_bundle_path(bundle_ref), offline=True)
        report["passed"] = all(report.get("assertions", {}).values())
        return report

    # Convenience: treat known sample names as recorded bundles
    if case_id in list_recorded_bundles():
        report = replay_bundle(resolve_bundle_path(case_id), offline=True)
        report["passed"] = all(report.get("assertions", {}).values())
        return report

    cases: Dict[str, CaseFn] = {
        "supercalc-late-correction": analyze_supercalc_late_correction,
        "demo-late-correction": _demo_late_correction,
    }

    if case_id not in cases:
        known = ", ".join(sorted(list(cases) + list(list_recorded_bundles())))
        raise ValueError(f"Unknown case '{case_id}'. Known cases/bundles: {known}")

    report = cases[case_id]()

    if case_id == "supercalc-late-correction":
        assert_supercalc_late_correction_report(report)

    assertions = report.get("assertions", {})
    report["passed"] = all(assertions.values()) if assertions else True
    return report


def list_cases() -> Dict[str, str]:
    """Return known offline case IDs and recorded bundles."""
    cases = {
        "supercalc-late-correction": (
            "STRESS S2 q correction → S3-S5 + HEDGE_ARM; TRUST_UNRELATED excluded"
        ),
        "demo-late-correction": (
            "DEMO D2 q correction → D3-D5 + DEMO_DEPENDENT; DEMO_UNRELATED excluded"
        ),
    }
    for name, description in list_recorded_bundles().items():
        cases[name] = f"recorded bundle: {description}"
    return cases
