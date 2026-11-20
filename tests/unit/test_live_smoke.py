"""Tests for live source contracts and opt-in live smoke (Postgres)."""

from pathlib import Path

import pytest

from winston.evaluation.live_smoke import run_live_smoke
from winston.sources.contracts import (
    validate_live_contract,
    validate_live_profile_file,
)
from winston.sources.postgres import PostgresConfig, PostgresLiveReader


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
    return {"relation": "schema.example_view", "columns": dict(columns)}


class TestLiveContracts:
    def test_template_or_local_profile_is_not_ready(self):
        report = validate_live_profile_file(
            "supercalc_live",
            Path("profiles"),
        )
        assert report["loaded"] is True
        # Prefer local gitignored yaml when present; else .example
        assert report["ready_for_live_smoke"] is False
        assert report["capability_label"] == "live-template"
        assert len(report["missing"]) > 0
        assert any("postgres." in m for m in report["missing"])

    def test_validate_lists_missing_postgres_fields(self, incomplete_live_profile):
        report = validate_live_contract(incomplete_live_profile)
        assert report["ready_for_live_smoke"] is False
        assert "postgres.host" in report["missing"]
        assert "postgres.database" in report["missing"]
        assert any(m.startswith("postgres.mappings.") for m in report["missing"])
        # Datadog optional when disabled
        assert not any(m.startswith("datadog.") for m in report["missing"])

    def test_databricks_block_warns(self, incomplete_live_profile):
        incomplete_live_profile["databricks"] = {"host": "x"}
        report = validate_live_contract(incomplete_live_profile)
        assert any("databricks" in w for w in report["warnings"])

    def test_ready_when_postgres_contracts_filled(self, incomplete_live_profile):
        profile = incomplete_live_profile
        profile["postgres"].update(
            {
                "host": "10.0.0.5",
                "database": "supercalc",
                "sslmode": "require",
                "auth_method": "password",
                "credential_provider": "secret:winston-staging-supercalc-pg-password",
            }
        )
        base_cols = {
            "index_id": "index_id",
            "environment": "environment",
            "business_date": "business_date",
            "execution_id": "execution_id",
            "col": "col",
        }
        for name in (
            "index_definitions",
            "calendars",
            "executions",
            "input_manifests",
            "artifacts",
            "selected_revisions",
        ):
            profile["postgres"]["mappings"][name] = _filled_mapping(base_cols)
        profile["indices"] = [{"id": "EXAMPLE_INDEX"}]
        report = validate_live_contract(profile)
        assert report["ready_for_live_smoke"] is True
        assert report["missing"] == []
        assert report["postgres_configured"] is True

    def test_datadog_required_only_when_enabled(self, incomplete_live_profile):
        profile = incomplete_live_profile
        profile["postgres"].update(
            {
                "host": "10.0.0.5",
                "database": "supercalc",
                "sslmode": "require",
                "auth_method": "password",
                "credential_provider": "env:PG",
            }
        )
        for name in (
            "index_definitions",
            "calendars",
            "executions",
            "input_manifests",
            "artifacts",
            "selected_revisions",
        ):
            profile["postgres"]["mappings"][name] = _filled_mapping({"a": "a"})
        profile["indices"] = [{"id": "EXAMPLE_INDEX"}]
        profile["datadog"] = {"enabled": True, "site": "", "metrics": []}
        report = validate_live_contract(profile)
        assert report["ready_for_live_smoke"] is False
        assert "datadog.site" in report["missing"]


class TestPostgresReader:
    def test_unavailable_without_config(self):
        reader = PostgresLiveReader(PostgresConfig())
        assert reader.is_available() is False

    def test_available_with_config_and_psycopg(self):
        reader = PostgresLiveReader(
            PostgresConfig(
                host="10.0.0.5",
                database="supercalc",
                auth_method="password",
                credential_provider="env:PG",
            )
        )
        assert reader.is_available() is True
        assert reader.source_type == "postgres"

    def test_probe_returns_unsupported_stub(self):
        reader = PostgresLiveReader(
            PostgresConfig(
                host="10.0.0.5",
                database="supercalc",
                auth_method="password",
                credential_provider="env:PG",
            )
        )
        result = reader.get_executions("X", "S1", "S2")
        assert result.receipt.status.value == "unsupported"


class TestLiveSmokeRunner:
    def test_blocked_without_flag(self, monkeypatch):
        monkeypatch.delenv("WINSTON_LIVE_SMOKE", raising=False)
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "true")
        report = run_live_smoke("supercalc_live")
        assert report["passed"] is False
        assert report["network_attempted"] is False
        assert report["capability_label"] == "live-template"
        assert report["primary_source"] == "postgres"
        assert report["missing_configuration"]

    def test_reports_missing_contracts_when_forced_offline_disabled(self, monkeypatch):
        monkeypatch.setenv("WINSTON_LIVE_SMOKE", "1")
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "false")
        report = run_live_smoke("supercalc_live")
        assert report["network_attempted"] is False
        assert report["capability_label"] == "live-template"
        assert any(
            "supercalc_live.yaml" in m or "mappings" in m or "Copy" in m or "postgres" in m
            for m in report["missing_configuration"]
        )

    def test_force_still_does_not_claim_live_verified_on_example(self, monkeypatch):
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "false")
        report = run_live_smoke("supercalc_live", force=True)
        assert report["capability_label"] == "live-template"
        assert report["passed"] is False
        assert report["network_attempted"] is False
