"""Unit tests for Supercalc-shaped synthetic fixtures and offline cases."""

import pytest

from winston.evaluation.cases import list_cases, run_case
from winston.evaluation.supercalc import (
    SUPERCALC_GOLDEN,
    analyze_supercalc_late_correction,
    create_execution_id,
    create_supercalc_graph,
    verify_supercalc_golden_values,
)
from winston.lineage.traversal import find_impact


@pytest.mark.supercalc
class TestSupercalcGoldenValues:
    def test_verify_all(self):
        results = verify_supercalc_golden_values()
        for name, ok in results.items():
            assert ok, f"Failed: {name}"

    def test_corrected_stress_levels(self):
        corrected = SUPERCALC_GOLDEN["corrected"]["STRESS"]
        assert corrected["S2"]["level"] == 102
        assert corrected["S2"]["carry"] == 5
        assert corrected["S3"]["level"] == 108
        assert corrected["S5"]["level"] == 110

    def test_hedge_arm_tracks_stress_s3(self):
        assert SUPERCALC_GOLDEN["original"]["HEDGE_ARM"]["S3"]["level"] == 206
        assert SUPERCALC_GOLDEN["corrected"]["HEDGE_ARM"]["S3"]["level"] == 216


@pytest.mark.supercalc
class TestSupercalcImpact:
    def test_s2_impacts_s3_to_s5_and_hedge(self):
        graph = create_supercalc_graph("original")
        origin = create_execution_id("STRESS", "S2", "original")
        impact = find_impact(graph, origin, change_field="state.carry")

        assert "STRESS" in impact.affected_indices
        assert "HEDGE_ARM" in impact.affected_indices
        assert "TRUST_UNRELATED" not in impact.affected_indices

        dates = {
            graph.get_node(eid).business_date
            for eid in impact.all_affected
            if graph.get_node(eid)
        }
        assert {"S3", "S4", "S5"} <= dates

    def test_unrelated_trust_not_in_closure(self):
        graph = create_supercalc_graph("original")
        origin = create_execution_id("STRESS", "S2", "original")
        impact = find_impact(graph, origin)

        for eid in impact.all_affected:
            assert not eid.startswith("TRUST_UNRELATED_")


@pytest.mark.supercalc
class TestSupercalcLateCorrectionCase:
    def test_analyze_report_assertions(self):
        report = analyze_supercalc_late_correction()
        assert report["change"]["origin_date"] == "S2"
        assert report["impact"]["unrelated_excluded"] is True
        assert "HEDGE_ARM" in report["impact"]["affected_indices"]
        assert report["as_executed_history"]["S5"] == 105
        assert report["corrected_plan_levels"]["S5"] == 110
        assert report["hedge_arm"]["original_s3"] == 206
        assert report["hedge_arm"]["corrected_s3"] == 216

    def test_run_case_offline(self):
        report = run_case("supercalc-late-correction", offline=True)
        assert report["passed"] is True
        assert report["capability_label"] == "fixture-verified"

    def test_live_mode_rejected(self):
        with pytest.raises(ValueError, match="offline-only"):
            run_case("supercalc-late-correction", offline=False)

    def test_list_cases_includes_supercalc(self):
        cases = list_cases()
        assert "supercalc-late-correction" in cases
