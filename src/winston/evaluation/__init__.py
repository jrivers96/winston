"""Winston evaluation - synthetic cases, recorded evidence, fault injection."""

from winston.evaluation.calculator import SyntheticCalculator
from winston.evaluation.cases import list_cases, run_case
from winston.evaluation.fixtures import (
    GOLDEN_VALUES,
    create_demo_graph,
    load_fixture,
    verify_golden_values,
)
from winston.evaluation.recorded import (
    list_recorded_bundles,
    load_bundle,
    record_supercalc_late_correction,
    replay_bundle,
)
from winston.evaluation.supercalc import (
    analyze_supercalc_late_correction,
    create_supercalc_graph,
    verify_supercalc_golden_values,
)

__all__ = [
    "SyntheticCalculator",
    "load_fixture",
    "create_demo_graph",
    "verify_golden_values",
    "GOLDEN_VALUES",
    "list_cases",
    "run_case",
    "create_supercalc_graph",
    "verify_supercalc_golden_values",
    "analyze_supercalc_late_correction",
    "list_recorded_bundles",
    "load_bundle",
    "record_supercalc_late_correction",
    "replay_bundle",
]
