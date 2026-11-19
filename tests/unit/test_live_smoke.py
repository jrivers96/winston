"""Tests for live source contracts and opt-in live smoke."""

import os
from pathlib import Path

import pytest
import yaml

from winston.evaluation.live_smoke import run_live_smoke
from winston.sources.contracts import (
    validate_live_contract,
    validate_live_profile_file,
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
        "databricks": {
            "host": "",
            "warehouse_id": "",
            "catalog": "",
            "auth_method": "",
            "credential_provider": "",
            "mappings": {},
        },
        "datadog": {
            "site": "",
            "auth_method": "",
            "credential_provider": "",
            "metrics": [],
            "services": [],
        },
        "indices": [{"id": ""}],
    }


class TestLiveContracts:
    def test_example_profile_is_not_ready(self):
        report = validate_live_profile_file(
            "supercalc_live",
            Path("profiles"),
        )
        assert report["loaded"] is True
        assert report["is_example"] is True
        assert report["ready_for_live_smoke"] is False
        assert report["capability_label"] == "live-template"
        assert len(report["missing"]) > 0

    def test_validate_lists_missing_fields(self, incomplete_live_profile):
        report = validate_live_contract(incomplete_live_profile)
        assert report["ready_for_live_smoke"] is False
        assert "databricks.host" in report["missing"]
        assert "datadog.site" in report["missing"]
        assert any(m.startswith("databricks.mappings.") for m in report["missing"])

    def test_ready_when_contracts_filled(self, incomplete_live_profile):
        profile = incomplete_live_profile
        profile["databricks"].update(
            {
                "host": "https://example.cloud.databricks.com",
                "warehouse_id": "abc",
                "catalog": "main",
                "auth_method": "oauth_m2m",
                "credential_provider": "env:DATABRICKS",
            }
        )
        cols = {
            "index_id": "index_id",
            "environment": "env",
            "owner": "owner",
            "calendar_ref": "cal",
            "timezone": "tz",
        }
        # Minimal filled mappings (placeholder column names — not production claims)
        for name in (
            "index_definitions",
            "calendars",
            "executions",
            "input_manifests",
            "artifacts",
            "selected_revisions",
        ):
            profile["databricks"]["mappings"][name] = {
                "table_name": f"schema.{name}",
                "columns": {k: k for k in cols},
            }
            # Ensure required columns exist per mapping loosely — validator only checks blanks
            profile["databricks"]["mappings"][name]["columns"] = {
                "execution_id": "execution_id",
                "index_id": "index_id",
                "environment": "environment",
                "business_date": "business_date",
                "table_col": "table_col",
            }
        profile["datadog"].update(
            {
                "site": "datadoghq.com",
                "auth_method": "api_key",
                "credential_provider": "env:DD",
                "metrics": [{"name": "example.metric"}],
            }
        )
        profile["indices"] = [{"id": "EXAMPLE_INDEX"}]
        report = validate_live_contract(profile)
        assert report["ready_for_live_smoke"] is True
        assert report["missing"] == []


class TestLiveSmokeRunner:
    def test_blocked_without_flag(self, monkeypatch):
        monkeypatch.delenv("WINSTON_LIVE_SMOKE", raising=False)
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "true")
        report = run_live_smoke("supercalc_live")
        assert report["passed"] is False
        assert report["network_attempted"] is False
        assert report["capability_label"] == "live-template"
        assert report["missing_configuration"]

    def test_reports_missing_contracts_when_forced_offline_disabled(self, monkeypatch):
        monkeypatch.setenv("WINSTON_LIVE_SMOKE", "1")
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "false")
        report = run_live_smoke("supercalc_live")
        assert report["network_attempted"] is False
        assert report["capability_label"] == "live-template"
        assert any(
            "supercalc_live.yaml" in m or "mappings" in m or "Copy" in m
            for m in report["missing_configuration"]
        )

    def test_force_still_does_not_claim_live_verified_on_example(self, monkeypatch):
        monkeypatch.setenv("WINSTON_OFFLINE_MODE", "false")
        report = run_live_smoke("supercalc_live", force=True)
        assert report["capability_label"] == "live-template"
        assert report["passed"] is False
        assert report["network_attempted"] is False
