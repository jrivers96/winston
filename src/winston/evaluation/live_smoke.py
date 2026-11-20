"""Opt-in live smoke for Supercalc-shaped products (Postgres).

Default: report precise missing configuration and exit without network.
When contracts + credentials + WINSTON_LIVE_SMOKE=1 are present, attempt
bounded read-only checks. Never mutate, trigger jobs, or publish.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from winston.config import get_settings
from winston.sources.contracts import (
    load_profile_yaml,
    validate_live_profile_file,
)
from winston.sources.postgres import PostgresConfig, PostgresLiveReader
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
        "primary_source": "postgres",
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
            "postgres_configured",
            "datadog_enabled",
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
                "detail": "Postgres source contracts incomplete — not attempting live network",
                "missing": contract.get("missing"),
            }
        )
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    profile_data = load_profile_yaml(Path(contract["path"]))
    budgets = _budgets_from_profile(profile_data)
    report["budgets"] = budgets

    forbidden = set((profile_data.get("live_smoke") or {}).get("forbidden_operations") or [])
    if not FORBIDDEN_OPS.issubset(forbidden):
        report["warnings"].append(
            "Profile should forbid mutate/trigger/publish/remediate operations"
        )

    report["network_attempted"] = True
    pg_cfg = profile_data.get("postgres") or {}
    postgres = PostgresLiveReader(
        PostgresConfig(
            host=pg_cfg.get("host", ""),
            port=int(pg_cfg.get("port", 5432) or 5432),
            database=pg_cfg.get("database", ""),
            sslmode=pg_cfg.get("sslmode", "require") or "require",
            auth_method=pg_cfg.get("auth_method", ""),
            credential_provider=pg_cfg.get("credential_provider", ""),
            db_user=pg_cfg.get("db_user", "winston_readonly") or "winston_readonly",
            connect_timeout_seconds=int(pg_cfg.get("connect_timeout_seconds", 30)),
            statement_timeout_seconds=int(
                pg_cfg.get("statement_timeout_seconds", budgets["max_seconds"])
            ),
            private_ip_required=bool(pg_cfg.get("private_ip_required", True)),
            read_only=bool(pg_cfg.get("read_only", True)),
            max_rows_per_query=budgets["max_rows"],
            connection_name=pg_cfg.get("connection_name", "") or "",
            source_mappings=pg_cfg.get("mappings") or {},
        )
    )

    pg_available = postgres.is_available()
    report["checks"].append(
        {
            "id": "postgres_driver",
            "status": "pass" if pg_available else "fail",
            "detail": (
                "psycopg importable and postgres contract configured"
                if pg_available
                else "Postgres driver/config unavailable — install psycopg "
                "and provide credential_provider for Supercalc read-only access"
            ),
        }
    )

    live_read_complete = False
    if pg_available:
        connectivity = postgres.probe_connectivity()
        report["checks"].append(
            {
                "id": "postgres_connectivity",
                "status": (
                    "pass"
                    if connectivity.receipt.status.value == "complete"
                    else "fail"
                ),
                "detail": f"status={connectivity.receipt.status.value}",
                "warnings": connectivity.receipt.warnings,
            }
        )
        probe = postgres.probe_mapped_relations()
        live_read_complete = probe.receipt.status.value == "complete"
        report["checks"].append(
            {
                "id": "postgres_read_probe",
                "status": "pass" if live_read_complete else "fail",
                "detail": (
                    f"status={probe.receipt.status.value}; "
                    f"allowlisted probes={len((probe.data or {}).get('probes') or {})}"
                ),
                "probes": (probe.data or {}).get("probes"),
                "warnings": probe.receipt.warnings,
            }
        )
        if not live_read_complete:
            report["missing_configuration"].append(
                "Postgres allowlisted read probe failed — check VPC/Cloud SQL path and password"
            )
    else:
        report["missing_configuration"].append(
            "Postgres live reader unavailable (psycopg or credential_provider)"
        )

    dd_cfg = profile_data.get("datadog") or {}
    if dd_cfg.get("enabled"):
        datadog = DatadogLiveReader(
            DatadogConfig(
                site=dd_cfg.get("site", "datadoghq.com"),
                auth_method=dd_cfg.get("auth_method", ""),
                credential_provider=dd_cfg.get("credential_provider", ""),
            )
        )
        dd_available = datadog.is_available()
        report["checks"].append(
            {
                "id": "datadog_sdk",
                "status": "pass" if dd_available else "fail",
                "detail": (
                    "datadog-api-client importable and config present"
                    if dd_available
                    else "Datadog enabled but SDK/config unavailable"
                ),
            }
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
                    "detail": f"status={probe.receipt.status.value}",
                    "warnings": probe.receipt.warnings,
                }
            )
    else:
        report["checks"].append(
            {
                "id": "datadog_sdk",
                "status": "skipped",
                "detail": "datadog.enabled=false — telemetry optional for Supercalc",
            }
        )

    check_statuses = {c["status"] for c in report["checks"]}
    fully_live = (
        contract.get("ready_for_live_smoke")
        and pg_available
        and live_read_complete
        and "fail" not in check_statuses
        and "blocked" not in check_statuses
        and not report["missing_configuration"]
    )

    if fully_live:
        report["capability_label"] = "live-verified"
        report["passed"] = True
    else:
        report["capability_label"] = "live-template"
        report["passed"] = False
        if not live_read_complete:
            report["warnings"].append(
                "Postgres adapter did not complete allowlisted reads; "
                "label remains live-template until probes succeed"
            )

    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    return report
