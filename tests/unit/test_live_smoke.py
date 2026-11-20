"""Tests for live source contracts and opt-in live smoke (Supercalc Postgres)."""

from pathlib import Path

import pytest

from winston.evaluation.live_smoke import run_live_smoke
from winston.sources.contracts import (
    validate_live_contract,
    validate_live_profile_file,
)
from winston.sources.postgres import PostgresConfig, PostgresLiveReader


REQUIRED_MAPPINGS = (
    "index_definitions",
    "index_series",
    "integrity_checks",
    "hedge_alert_outcomes",
    "risk_rollups",
    "signals",
)


@pytest.fixture
def incomplete_live_profile() -> dict:
    return {
        "profile_id": "supercalc_live",
        "live_smoke": {
            "enabled_by_default": False,
            "forbidden_operations": [
                "mutate_data",
                "trigger_jobs",
                "publish_results",
                "remediate_production",
            ],
            "budgets": {"max_rows": 100},
        },
        "postgres": {
            "host": "",
            "database": "",
            "sslmode": "",
            "auth_method": "",
            "credential_provider": "",
            "read_only": True,
            "mappings": {},
        },
        "datadog": {"enabled": False},
        "indices": [{"id": ""}],
    }


def _filled_mapping(columns: dict) -> dict:
    return {"relation": "public.example", "columns": dict(columns)}


class TestLiveContracts:
    def test_template_or_local_profile_reports_postgres_shape(self):
        report = validate_live_profile_file(
            "supercalc_live",
            Path("profiles"),
        )
        assert report["loaded"] is True
        # Local filled profile may be ready for contracts; example is not.
        missing = report.get("missing") or []
        if report.get("is_example") or not report.get("ready_for_live_smoke"):
            assert any("postgres." in m for m in missing) or missing == []
        if report.get("ready_for_live_smoke"):
            assert report["postgres_configured"] is True

    def test_validate_lists_missing_postgres_fields(self, incomplete_live_profile):
        report = validate_live_contract(incomplete_live_profile)
        assert report["ready_for_live_smoke"] is False
        assert "postgres.host" in report["missing"]
        assert "postgres.database" in report["missing"]
        assert any(m.startswith("postgres.mappings.") for m in report["missing"])
        assert not any(m.startswith("datadog.") for m in report["missing"])

    def test_ready_when_supercalc_mappings_filled(self, incomplete_live_profile):
        profile = incomplete_live_profile
        profile["postgres"].update(
            {
                "host": "10.83.0.11",
                "database": "polymarket_gvf",
                "sslmode": "require",
                "auth_method": "password",
                "credential_provider": "secret:winston-staging-supercalc-pg-password",
            }
        )
        cols = {"id": "id", "created_at": "created_at"}
        for name in REQUIRED_MAPPINGS:
            profile["postgres"]["mappings"][name] = _filled_mapping(cols)
        profile["indices"] = [{"id": "systemic_stress"}]
        report = validate_live_contract(profile)
        assert report["ready_for_live_smoke"] is True
        assert report["missing"] == []
        assert report["postgres_configured"] is True


class TestPostgresReader:
    def test_unavailable_without_config(self):
        reader = PostgresLiveReader(PostgresConfig())
        assert reader.is_available() is False

    def test_available_with_config_and_psycopg(self):
        reader = PostgresLiveReader(
            PostgresConfig(
                host="10.83.0.11",
                database="polymarket_gvf",
                auth_method="password",
                credential_provider="env:PG",
            )
        )
        assert reader.is_available() is True
        assert reader.source_type == "postgres"


class TestLiveSmokeRunner:
    def test_blocked_without_flag(self, monkeypatch):
        monkeypatch.delenv("WINSTON_LIVE_SMOKE", raising=False)
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "true")
        report = run_live_smoke("supercalc_live")
        assert report["passed"] is False
        assert report["network_attempted"] is False
        assert report["primary_source"] == "postgres"

    def test_force_incomplete_without_credentials_still_template(self, monkeypatch):
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "false")
        report = run_live_smoke("supercalc_live", force=True)
        # Even with filled local contracts, stub reader cannot live-verify yet
        assert report["capability_label"] == "live-template"
        assert report["passed"] is False
