"""Opt-in live smoke for Supercalc-shaped products.

Default: report precise missing configuration and exit without network.
When contracts + credentials + WINSTON_LIVE_SMOKE=1 are present, attempt
bounded read-only checks. Never mutate, trigger jobs, or publish.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from winston.config import get_settings
from winston.sources.contracts import (
    load_profile_yaml,
    validate_live_profile_file,
)
from winston.sources.databricks import DatabricksConfig, DatabricksLiveReader
from winston.sources.datadog import DatadogConfig, DatadogLiveReader


LIVE_SMOKE_FLAG = "WINSTON_LIVE_SMOKE"
FORBIDDEN_OPS = {
    "mutate_data",
    "trigger_jobs",
    "publish_results",
    "remediate_production",
}


def _flag_enabled() -> bool:
    value = os.environ.get(LIVE_SMOKE_FLAG, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _budgets_from_profile(profile_data: Dict[str, Any]) -> Dict[str, int]:
    live = profile_data.get("live_smoke") or {}
    budgets = live.get("budgets") or {}
    return {
        "max_business_dates": int(budgets.get("max_business_dates", 3)),
        "max_rows": int(budgets.get("max_rows", 500)),
        "max_seconds": int(budgets.get("max_seconds", 60)),
        "max_metric_series": int(budgets.get("max_metric_series", 20)),
    }


def run_live_smoke(
    profile_name: str = "supercalc_live",
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Run opt-in live smoke or return a precise missing-config report.

    Args:
        profile_name: Live profile name (without .yaml)
        force: If True, skip env-flag check (still won't invent credentials)

    Returns:
        Structured smoke report with capability_label
    """
    settings = get_settings()
    started = datetime.now(timezone.utc)

    report: Dict[str, Any] = {
        "command": "live-smoke",
        "profile": profile_name,
        "started_at": started.isoformat(),
        "offline_mode": settings.offline_mode,
        "live_smoke_flag": _flag_enabled(),
        "force": force,
        "checks": [],
        "missing_configuration": [],
        "warnings": [],
        "network_attempted": False,
        "capability_label": "live-template",
        "passed": False,
        "forbidden_operations": sorted(FORBIDDEN_OPS),
    }

    contract = validate_live_profile_file(profile_name, settings.profiles_dir)
    report["contract"] = {
        k: contract.get(k)
        for k in (
            "loaded",
            "path",
            "is_example",
            "ready_for_live_smoke",
            "missing",
            "warnings",
            "capability_label",
            "notes",
        )
    }
    report["missing_configuration"].extend(contract.get("missing") or [])
    report["warnings"].extend(contract.get("warnings") or [])
    report["warnings"].extend(contract.get("notes") or [])

    if settings.offline_mode and not force:
        report["checks"].append(
            {
                "id": "offline_mode_block",
                "status": "blocked",
                "detail": "WINSTON_OFFLINE_MODE=true blocks live smoke; "
                "set WINSTON_OFFLINE_MODE=false and WINSTON_LIVE_SMOKE=1",
            }
        )
        report["missing_configuration"].append(
            "Disable offline mode for live smoke (WINSTON_OFFLINE_MODE=false)"
        )
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    if not _flag_enabled() and not force:
        report["checks"].append(
            {
                "id": "env_flag",
                "status": "blocked",
                "detail": f"Set {LIVE_SMOKE_FLAG}=1 to opt in to live smoke",
            }
        )
        report["missing_configuration"].append(f"{LIVE_SMOKE_FLAG}=1")
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    report["checks"].append(
        {
            "id": "env_flag",
            "status": "pass" if _flag_enabled() or force else "blocked",
            "detail": "Live smoke explicitly opted in",
        }
    )

    if not contract.get("loaded") or not contract.get("path"):
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    if contract.get("is_example") or not contract.get("ready_for_live_smoke"):
        report["checks"].append(
            {
                "id": "source_contracts",
                "status": "incomplete",
                "detail": "Source contracts incomplete — not attempting live network",
                "missing": contract.get("missing"),
            }
        )
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    # Contracts ready — attempt bounded read-only probes
    profile_data = load_profile_yaml(Path(contract["path"]))
    budgets = _budgets_from_profile(profile_data)
    report["budgets"] = budgets

    forbidden = set((profile_data.get("live_smoke") or {}).get("forbidden_operations") or [])
    if not FORBIDDEN_OPS.issubset(forbidden):
        report["warnings"].append(
            "Profile should forbid mutate/trigger/publish/remediate operations"
        )

    report["network_attempted"] = True
    dbx_cfg = profile_data.get("databricks") or {}
    dd_cfg = profile_data.get("datadog") or {}

    databricks = DatabricksLiveReader(
        DatabricksConfig(
            host=dbx_cfg.get("host", ""),
            warehouse_id=dbx_cfg.get("warehouse_id", ""),
            catalog=dbx_cfg.get("catalog", ""),
            auth_method=dbx_cfg.get("auth_method", ""),
            credential_provider=dbx_cfg.get("credential_provider", ""),
            statement_timeout_seconds=int(
                dbx_cfg.get("statement_timeout_seconds", budgets["max_seconds"])
            ),
            max_rows_per_query=budgets["max_rows"],
        )
    )
    datadog = DatadogLiveReader(
        DatadogConfig(
            site=dd_cfg.get("site", "datadoghq.com"),
            auth_method=dd_cfg.get("auth_method", ""),
            credential_provider=dd_cfg.get("credential_provider", ""),
        )
    )

    dbx_available = databricks.is_available()
    dd_available = datadog.is_available()

    report["checks"].append(
        {
            "id": "databricks_sdk",
            "status": "pass" if dbx_available else "fail",
            "detail": (
                "databricks-sql-connector importable and config present"
                if dbx_available
                else "Databricks SDK/config unavailable — install winston[databricks] "
                "and provide credentials via credential_provider"
            ),
        }
    )
    report["checks"].append(
        {
            "id": "datadog_sdk",
            "status": "pass" if dd_available else "fail",
            "detail": (
                "datadog-api-client importable and config present"
                if dd_available
                else "Datadog SDK/config unavailable — install winston[datadog] "
                "and provide credentials via credential_provider"
            ),
        }
    )

    # Bounded probe: call live readers; stubs return unsupported without full wiring.
    # This keeps the surface read-only and documents remaining live work precisely.
    if dbx_available:
        probe = databricks.get_executions(
            index_id=(profile_data.get("indices") or [{}])[0].get("id", ""),
            from_date="1970-01-01",
            to_date="1970-01-01",
        )
        report["checks"].append(
            {
                "id": "databricks_read_probe",
                "status": (
                    "pass"
                    if probe.receipt.status.value
                    not in {"failed", "permission_denied"}
                    else "incomplete"
                ),
                "detail": (
                    f"status={probe.receipt.status.value}; "
                    "live SQL execution path still requires allowlisted query templates"
                ),
                "warnings": probe.receipt.warnings,
            }
        )
    else:
        report["missing_configuration"].append(
            "Databricks live reader unavailable (package or credential_provider)"
        )

    if dd_available:
        now = datetime.now(timezone.utc)
        probe = datadog.get_metrics(
            metric_query=(dd_cfg.get("metrics") or [{}])[0].get("name", "unset"),
            start_time=now,
            end_time=now,
        )
        report["checks"].append(
            {
                "id": "datadog_read_probe",
                "status": (
                    "pass"
                    if probe.receipt.status.value
                    not in {"failed", "permission_denied"}
                    else "incomplete"
                ),
                "detail": (
                    f"status={probe.receipt.status.value}; "
                    "live metric query path still requires configured metric mappings"
                ),
                "warnings": probe.receipt.warnings,
            }
        )
    else:
        report["missing_configuration"].append(
            "Datadog live reader unavailable (package or credential_provider)"
        )

    check_statuses = {c["status"] for c in report["checks"]}
    fully_live = (
        contract.get("ready_for_live_smoke")
        and dbx_available
        and dd_available
        and "fail" not in check_statuses
        and "blocked" not in check_statuses
        and not report["missing_configuration"]
    )
    # Live readers currently return unsupported until query templates are wired —
    # do not claim live-verified until a successful complete read exists.
    live_complete = any(
        c.get("id", "").endswith("_read_probe")
        and c.get("status") == "pass"
        and "unsupported" not in str(c.get("detail", ""))
        for c in report["checks"]
    )

    if fully_live and live_complete:
        report["capability_label"] = "live-verified"
        report["passed"] = True
    else:
        report["capability_label"] = "live-template"
        report["passed"] = False
        if not live_complete:
            report["warnings"].append(
                "Live adapters responded but did not complete a verified read; "
                "label remains live-template until allowlisted queries succeed"
            )

    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    return report
