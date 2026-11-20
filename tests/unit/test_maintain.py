"""Tests for trust checks and maintain loop."""

from datetime import datetime, timedelta, timezone

import pytest

from winston.checks.base import CheckStatus
from winston.checks.trust import (
    CoverageGapCheck,
    FreshnessSLACheck,
    IntegrityStatusCheck,
    StaleWindowCheck,
    UnrelatedExclusionCheck,
)
from winston.evaluation.supercalc import create_execution_id, create_supercalc_graph
from winston.maintenance.live_trust import (
    build_live_trust_contexts_from_snapshot,
    expected_sessions_for_lookback,
    trust_config_from_profile,
)
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
                "integrity_failures": [],
            }
        )
        statuses = {r.check_id: r.status for r in results}
        assert statuses["coverage_gap"] == CheckStatus.UNKNOWN
        assert statuses["stale_window"] == CheckStatus.UNKNOWN
        drafts = results_to_issue_drafts(results)
        # Unknown checks still create follow-up obligations
        assert any(d["issue"].metadata["check_status"] == "unknown" for d in drafts)

    def test_rejects_unknown_live_profile_name(self):
        with pytest.raises(ValueError, match="supercalc_live"):
            maintain_once(profile="not_a_profile", persist=False)


class TestLiveTrustPath:
    def test_freshness_via_present_sessions(self):
        result = FreshnessSLACheck().run(
            {
                "index_id": "systemic_stress",
                "expected_sessions": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "present_sessions": ["2024-01-01", "2024-01-02"],
            }
        )
        assert result.status == CheckStatus.FAIL
        assert "2024-01-03" in result.metadata["missing_sessions"]

    def test_integrity_status_fails_on_non_pass(self):
        result = IntegrityStatusCheck().run(
            {
                "index_id": "trust_status",
                "integrity_failures": [
                    {"check_name": "series_fresh", "status": "fail"},
                ],
            }
        )
        assert result.status == CheckStatus.FAIL
        assert "series_fresh" in result.metadata["failure_names"]

    def test_unrelated_exclusion_not_applicable_without_lineage(self):
        result = UnrelatedExclusionCheck().run({"lineage_available": False})
        assert result.status == CheckStatus.NOT_APPLICABLE

    def test_snapshot_to_drafts_matches_synthetic_shape(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        d0 = (now - timedelta(days=2)).date().isoformat()
        d1 = (now - timedelta(days=1)).date().isoformat()
        d2 = now.date().isoformat()
        trust_cfg = trust_config_from_profile(
            {
                "indices": [{"id": "systemic_stress"}],
                "trust_checks": {
                    "freshness": {
                        "index_name": "systemic_stress",
                        "lookback_dates": 3,
                        "expected_sessions": [d0, d1, d2],
                    },
                    "stale_window": {"sla_hours": 24},
                    "coverage": {"min_coverage_ratio": 0.1},
                    "integrity": {"index_id": "trust_status"},
                },
            }
        )
        snapshot = {
            "latest_integrity_run_ts": (now - timedelta(hours=1)).isoformat(),
            "integrity_failures": [
                {"check_name": "gvf_ok", "status": "fail", "run_ts": now.isoformat()},
            ],
            "series_dates": [d0, d1],  # missing today
            "series_latest_ts": now.isoformat(),
            "covered_count": 50,
            "universe_count": 100,
        }
        ctx = build_live_trust_contexts_from_snapshot(snapshot, trust_cfg, now=now)
        results = run_trust_checks(ctx)
        statuses = {r.check_id: r.status for r in results}
        assert statuses["freshness_sla"] == CheckStatus.FAIL
        assert statuses["integrity_status"] == CheckStatus.FAIL
        assert statuses["stale_window"] == CheckStatus.PASS
        assert statuses["coverage_gap"] == CheckStatus.PASS
        assert statuses["unrelated_exclusion"] == CheckStatus.NOT_APPLICABLE

        report = maintain_once(
            profile="supercalc_live",
            persist=False,
            live_snapshot=snapshot,
        )
        assert report["capability_label"] == "live-verified"
        assert report["environment"] == "production"
        assert report["ok"] is False
        titles = [d["title"] for d in report["drafts"]]
        assert any("integrity_status" in t for t in titles)
        # Same draft keys as synthetic maintain
        assert set(report["drafts"][0].keys()) >= {
            "fingerprint",
            "issue_id",
            "obligation_id",
            "title",
            "severity",
            "check_status",
        }

    def test_live_gate_reports_missing_config(self, monkeypatch):
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "true")
        monkeypatch.delenv("WINSTON_LIVE_SMOKE", raising=False)
        report = maintain_once(profile="supercalc_live", persist=False)
        assert report["ok"] is False
        assert report["capability_label"] == "live-template"
        assert report["drafts"] == []
        assert any("OFFLINE" in m or "LIVE_SMOKE" in m for m in report["missing_configuration"])

    def test_lookback_expected_sessions(self):
        now = datetime(2024, 1, 10, tzinfo=timezone.utc)
        assert expected_sessions_for_lookback(3, now=now) == [
            "2024-01-08",
            "2024-01-09",
            "2024-01-10",
        ]
