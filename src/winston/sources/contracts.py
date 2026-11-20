"""Source-contract validation for live profiles.

Reports precise missing configuration. Never invents production names.
Supercalc live contracts target Postgres (views preferred); Datadog is optional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


REQUIRED_POSTGRES_TOP = (
    "host",
    "database",
    "sslmode",
    "auth_method",
    "credential_provider",
)
# Supercalc (polymarket-gvf) product tables — not generic calc-ops lineage slots
REQUIRED_POSTGRES_MAPPINGS = (
    "index_definitions",
    "index_series",
    "integrity_checks",
    "hedge_alert_outcomes",
    "risk_rollups",
    "signals",
)
REQUIRED_DATADOG_TOP = ("site", "auth_method", "credential_provider")


def load_profile_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML profile file."""
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Profile must be a mapping: {path}")
    return data


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _check_mapping_relation(
    mapping_name: str,
    mapping: Any,
    missing: List[str],
    *,
    prefix_root: str = "postgres.mappings",
) -> None:
    prefix = f"{prefix_root}.{mapping_name}"
    if not isinstance(mapping, dict):
        missing.append(f"{prefix} (missing object)")
        return
    # Prefer "relation" (view/table); accept legacy "table_name" for transition
    relation = mapping.get("relation")
    if _blank(relation):
        relation = mapping.get("table_name")
    if _blank(relation):
        missing.append(f"{prefix}.relation")
    columns = mapping.get("columns") or {}
    if not isinstance(columns, dict) or not columns:
        missing.append(f"{prefix}.columns")
        return
    for col_name, col_value in columns.items():
        if _blank(col_value):
            missing.append(f"{prefix}.columns.{col_name}")


def validate_live_contract(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a live profile's source contracts.

    Returns a structured report with missing fields and readiness.
    Datadog is optional — incomplete Datadog only warns unless enabled: true.
    """
    missing: List[str] = []
    warnings: List[str] = []

    live = profile_data.get("live_smoke") or {}
    if live.get("enabled_by_default"):
        warnings.append(
            "live_smoke.enabled_by_default should be false; require WINSTON_LIVE_SMOKE"
        )

    # Reject Databricks-shaped Supercalc live profiles — wrong stack
    if "databricks" in profile_data and profile_data.get("databricks"):
        warnings.append(
            "databricks block is ignored for Supercalc live — use postgres mappings"
        )

    postgres = profile_data.get("postgres") or {}
    for key in REQUIRED_POSTGRES_TOP:
        if _blank(postgres.get(key)):
            missing.append(f"postgres.{key}")

    if postgres.get("read_only") is False:
        missing.append("postgres.read_only must be true (or omitted)")

    mappings = postgres.get("mappings") or {}
    for mapping_name in REQUIRED_POSTGRES_MAPPINGS:
        _check_mapping_relation(mapping_name, mappings.get(mapping_name), missing)

    datadog = profile_data.get("datadog") or {}
    datadog_enabled = bool(datadog.get("enabled"))
    datadog_configured = False
    if datadog_enabled:
        for key in REQUIRED_DATADOG_TOP:
            if _blank(datadog.get(key)):
                missing.append(f"datadog.{key}")
        if _blank(datadog.get("metrics")):
            missing.append("datadog.metrics (at least one configured metric)")
        datadog_configured = all(
            not _blank(datadog.get(k)) for k in REQUIRED_DATADOG_TOP
        ) and not _blank(datadog.get("metrics"))
    elif any(
        not _blank(datadog.get(k))
        for k in ("site", "auth_method", "credential_provider", "metrics")
    ):
        warnings.append(
            "datadog fields are set but datadog.enabled is false — telemetry skipped"
        )

    indices = profile_data.get("indices") or []
    if not indices:
        missing.append("indices (at least one live index identity)")
    else:
        for i, index in enumerate(indices):
            if not isinstance(index, dict) or _blank(index.get("id")):
                missing.append(f"indices[{i}].id")

    forbidden = live.get("forbidden_operations") or []
    for op in ("mutate_data", "trigger_jobs", "publish_results"):
        if op not in forbidden:
            warnings.append(f"live_smoke.forbidden_operations should include '{op}'")

    ready = len(missing) == 0
    return {
        "ready_for_live_smoke": ready,
        "missing": missing,
        "warnings": warnings,
        # Contracts-ready is not live-verified — only a successful read earns that
        "capability_label": "live-template",
        "postgres_configured": all(
            not _blank(postgres.get(k)) for k in REQUIRED_POSTGRES_TOP
        ),
        "datadog_enabled": datadog_enabled,
        "datadog_configured": datadog_configured,
    }


def resolve_live_profile_path(
    profile_name: str,
    profiles_dir: Path,
) -> Tuple[Optional[Path], List[str]]:
    """Resolve a live profile path, preferring real yaml then .example."""
    notes: List[str] = []
    real = profiles_dir / f"{profile_name}.yaml"
    example = profiles_dir / f"{profile_name}.yaml.example"

    if real.exists():
        return real, notes

    if example.exists():
        notes.append(
            f"Using example template {example.name}; "
            f"copy to {real.name} and fill contracts before live verification"
        )
        return example, notes

    return None, [f"Neither {real} nor {example} exists"]


def validate_live_profile_file(
    profile_name: str,
    profiles_dir: Path,
) -> Dict[str, Any]:
    """Load and validate a live profile from disk."""
    path, notes = resolve_live_profile_path(profile_name, profiles_dir)
    if path is None:
        return {
            "loaded": False,
            "ready_for_live_smoke": False,
            "missing": notes,
            "warnings": [],
            "capability_label": "live-template",
            "path": None,
        }

    data = load_profile_yaml(path)
    report = validate_live_contract(data)
    report.update(
        {
            "loaded": True,
            "path": str(path),
            "is_example": path.name.endswith(".example"),
            "notes": notes,
            "profile_id": data.get("profile_id"),
        }
    )
    if report.get("is_example"):
        report["ready_for_live_smoke"] = False
        report["capability_label"] = "live-template"
        if "Copy example to a real profile and fill mappings" not in report["missing"]:
            report["missing"] = [
                "Copy profiles/supercalc_live.yaml.example to "
                "profiles/supercalc_live.yaml and fill non-empty mappings"
            ] + list(report.get("missing", []))
    return report
