"""Tests for trust checks and maintain loop."""

from datetime import datetime, timedelta, timezone

import pytest

from winston.checks.base import CheckStatus
from winston.checks.trust import (
    CoverageGapCheck,
    FreshnessSLACheck,
    StaleWindowCheck,
    UnrelatedExclusionCheck,
)
from winston.evaluation.supercalc import create_execution_id, create_supercalc_graph
from winston.maintenance.service import (
    build_supercalc_trust_contexts,
    maintain_once,
    results_to_issue_drafts,
    run_trust_checks,
)


class TestTrustChecks:
    def test_freshness_passes_when_complete(self):
        ctx = build_supercalc_trust_contexts()
        result = FreshnessSLACheck().run(ctx)
        assert result.status == CheckStatus.PASS

    def test_freshness_fails_when_session_missing(self):
        ctx = build_supercalc_trust_contexts(inject_missing_session="S5")
        result = FreshnessSLACheck().run(ctx)
        assert result.status == CheckStatus.FAIL
        assert "S5" in result.metadata["missing_sessions"]

    def test_stale_window_fails(self):
        old = datetime.now(timezone.utc) - timedelta(hours=48)
        result = StaleWindowCheck().run(
            {"observed_at": old, "sla_hours": 24, "now": datetime.now(timezone.utc)}
        )
        assert result.status == CheckStatus.FAIL

    def test_stale_window_unknown_without_timestamp(self):
        result = StaleWindowCheck().run({})
        assert result.status == CheckStatus.UNKNOWN

    def test_coverage_gap_fails_below_threshold(self):
        result = CoverageGapCheck().run(
            {"covered_count": 5, "universe_count": 100, "min_coverage_ratio": 0.15}
        )
        assert result.status == CheckStatus.FAIL

    def test_unrelated_exclusion_passes(self):
        graph = create_supercalc_graph("original")
        origin = create_execution_id("STRESS", "S2", "original")
        result = UnrelatedExclusionCheck().run(
            {
                "graph": graph,
                "origin_execution_id": origin,
                "excluded_prefixes": ["TRUST_UNRELATED_"],
            }
        )
        assert result.status == CheckStatus.PASS


class TestMaintainOnce:
    def test_healthy_run_has_no_drafts(self):
        report = maintain_once(persist=False)
        assert report["ok"] is True
        assert report["failed"] == 0
        assert report["drafts"] == []

    def test_missing_session_opens_draft_issue(self):
        report = maintain_once(persist=False, inject_missing_session="S5")
        assert report["ok"] is False
        assert report["failed"] >= 1
        assert any("freshness_sla" in d["title"] for d in report["drafts"])

    def test_unknown_not_forced_to_pass(self):
        results = run_trust_checks(
            {
                "graph": create_supercalc_graph("original"),
                "index_id": "STRESS",
                "expected_sessions": ["S1", "S2", "S3", "S4", "S5"],
                "origin_execution_id": create_execution_id("STRESS", "S2", "original"),
                "excluded_prefixes": ["TRUST_UNRELATED_"],
                # Force coverage unknown
                "covered_count": None,
                "universe_count": None,
                "observed_at": None,
            }
        )
        statuses = {r.check_id: r.status for r in results}
        assert statuses["coverage_gap"] == CheckStatus.UNKNOWN
        assert statuses["stale_window"] == CheckStatus.UNKNOWN
        drafts = results_to_issue_drafts(results)
        # Unknown checks still create follow-up obligations
        assert any(d["issue"].metadata["check_status"] == "unknown" for d in drafts)
