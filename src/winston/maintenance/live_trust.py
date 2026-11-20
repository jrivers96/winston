"""Build trust-check contexts from live Supercalc SoR snapshots."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from winston.config import get_settings
from winston.sources.contracts import load_profile_yaml, validate_live_profile_file
from winston.sources.postgres import PostgresConfig, PostgresLiveReader

LIVE_SMOKE_FLAG = "WINSTON_LIVE_SMOKE"
LIVE_PROFILES = frozenset({"supercalc_live", "live"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _flag_enabled() -> bool:
    value = os.environ.get(LIVE_SMOKE_FLAG, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def trust_config_from_profile(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize trust_checks config from a live profile."""
    raw = profile_data.get("trust_checks") or {}
    if isinstance(raw, list):
        # Synthetic-style list of check decls — treat as empty live config.
        raw = {}
    indices = profile_data.get("indices") or []
    default_index = None
    for idx in indices:
        if isinstance(idx, dict) and idx.get("id"):
            # Prefer a series-backed index for freshness when listed.
            if idx.get("id") not in ("trust_status", "hedge_windows"):
                default_index = str(idx["id"])
                break
    if default_index is None:
        for idx in indices:
            if isinstance(idx, dict) and idx.get("id"):
                default_index = str(idx["id"])
                break

    freshness = raw.get("freshness") or {}
    coverage = raw.get("coverage") or {}
    stale = raw.get("stale_window") or {}
    integrity = raw.get("integrity") or {}

    lookback = int(freshness.get("lookback_dates") or raw.get("lookback_dates") or 5)
    index_id = str(
        freshness.get("index_name")
        or raw.get("index_name")
        or default_index
        or "systemic_stress"
    )

    expected = freshness.get("expected_sessions")
    if expected is not None and not isinstance(expected, list):
        expected = None

    return {
        "index_id": index_id,
        "lookback_dates": max(1, min(lookback, 30)),
        "expected_sessions": expected,
        "sla_hours": float(stale.get("sla_hours") or raw.get("sla_hours") or 24.0),
        "min_coverage_ratio": float(
            coverage.get("min_coverage_ratio")
            or raw.get("min_coverage_ratio")
            or 0.0
        ),
        "covered_count_override": coverage.get("covered_count"),
        "universe_count_override": coverage.get("universe_count"),
        "integrity_index_id": str(
            integrity.get("index_id") or "trust_status"
        ),
        "max_integrity_rows": int(
            integrity.get("max_rows") or raw.get("max_integrity_rows") or 50
        ),
    }


def expected_sessions_for_lookback(
    lookback_dates: int,
    *,
    now: Optional[datetime] = None,
) -> List[str]:
    """Calendar-date sessions ending today (UTC), oldest first."""
    anchor = now or _now()
    dates = []
    for offset in range(lookback_dates - 1, -1, -1):
        day = (anchor - timedelta(days=offset)).date()
        dates.append(day.isoformat())
    return dates


def build_live_trust_contexts_from_snapshot(
    snapshot: Dict[str, Any],
    trust_cfg: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Map a SoR trust snapshot into the dict trust checks expect."""
    now = now or _now()
    index_id = trust_cfg["index_id"]
    lookback = int(trust_cfg["lookback_dates"])

    expected = trust_cfg.get("expected_sessions")
    if not expected:
        expected = expected_sessions_for_lookback(lookback, now=now)

    present = [str(s) for s in (snapshot.get("series_dates") or [])]

    observed_at = _parse_ts(snapshot.get("latest_integrity_run_ts"))
    if observed_at is None:
        observed_at = _parse_ts(snapshot.get("series_latest_ts"))

    covered = trust_cfg.get("covered_count_override")
    if covered is None:
        covered = snapshot.get("covered_count")
    universe = trust_cfg.get("universe_count_override")
    if universe is None:
        universe = snapshot.get("universe_count")

    return {
        # Freshness (live path uses present_sessions; no lineage graph)
        "index_id": index_id,
        "expected_sessions": list(expected),
        "present_sessions": present,
        "graph": None,
        # Stale window
        "observed_at": observed_at,
        "sla_hours": float(trust_cfg["sla_hours"]),
        "now": now,
        # Coverage
        "covered_count": covered,
        "universe_count": universe,
        "min_coverage_ratio": float(trust_cfg["min_coverage_ratio"]),
        # Integrity
        "integrity_failures": snapshot.get("integrity_failures"),
        # Unrelated exclusion is fixture-only until live lineage exists
        "lineage_available": False,
        "origin_execution_id": None,
        "excluded_prefixes": None,
        # Metadata for drafts
        "_live_index_id": index_id,
        "_integrity_index_id": trust_cfg["integrity_index_id"],
    }


def postgres_config_from_profile(
    profile_data: Dict[str, Any],
    *,
    max_rows: int = 500,
    statement_timeout_seconds: int = 60,
) -> PostgresConfig:
    pg_cfg = profile_data.get("postgres") or {}
    return PostgresConfig(
        host=pg_cfg.get("host", ""),
        port=int(pg_cfg.get("port", 5432) or 5432),
        database=pg_cfg.get("database", ""),
        sslmode=pg_cfg.get("sslmode", "require") or "require",
        auth_method=pg_cfg.get("auth_method", ""),
        credential_provider=pg_cfg.get("credential_provider", ""),
        db_user=pg_cfg.get("db_user", "winston_readonly") or "winston_readonly",
        connect_timeout_seconds=int(pg_cfg.get("connect_timeout_seconds", 30)),
        statement_timeout_seconds=int(
            pg_cfg.get("statement_timeout_seconds", statement_timeout_seconds)
        ),
        private_ip_required=bool(pg_cfg.get("private_ip_required", True)),
        read_only=bool(pg_cfg.get("read_only", True)),
        max_rows_per_query=max_rows,
        connection_name=pg_cfg.get("connection_name", "") or "",
        source_mappings=pg_cfg.get("mappings") or {},
    )


def load_live_maintain_gate(
    profile_name: str,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Validate env + contracts before attempting live maintain network."""
    settings = get_settings()
    report: Dict[str, Any] = {
        "profile": profile_name,
        "offline_mode": settings.offline_mode,
        "live_smoke_flag": _flag_enabled(),
        "force": force,
        "missing_configuration": [],
        "warnings": [],
        "ready": False,
        "contract": None,
        "profile_data": None,
        "profile_path": None,
    }

    if settings.offline_mode and not force:
        report["missing_configuration"].append(
            "Disable offline mode for live maintain (WINSTON_OFFLINE_MODE=false)"
        )
        return report

    if not _flag_enabled() and not force:
        report["missing_configuration"].append(f"{LIVE_SMOKE_FLAG}=1")
        return report

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

    if not contract.get("loaded") or not contract.get("path"):
        return report
    if contract.get("is_example") or not contract.get("ready_for_live_smoke"):
        report["missing_configuration"].append(
            "Postgres source contracts incomplete — not attempting live network"
        )
        return report

    path = Path(contract["path"])
    profile_data = load_profile_yaml(path)
    report["profile_data"] = profile_data
    report["profile_path"] = str(path)
    report["ready"] = len(report["missing_configuration"]) == 0
    return report


def fetch_live_trust_snapshot(
    profile_data: Dict[str, Any],
    trust_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Connect and fetch a trust snapshot; raises RuntimeError on failure."""
    live = profile_data.get("live_smoke") or {}
    budgets = live.get("budgets") or {}
    max_rows = int(budgets.get("max_rows", 500))
    max_seconds = int(budgets.get("max_seconds", 60))
    reader = PostgresLiveReader(
        postgres_config_from_profile(
            profile_data,
            max_rows=max_rows,
            statement_timeout_seconds=max_seconds,
        )
    )
    if not reader.is_available():
        raise RuntimeError(
            "Postgres live reader unavailable (psycopg or credential_provider)"
        )
    result = reader.fetch_trust_snapshot(
        index_name=trust_cfg["index_id"],
        lookback_dates=trust_cfg["lookback_dates"],
        max_integrity_rows=trust_cfg["max_integrity_rows"],
    )
    if result.receipt.status.value != "complete":
        warnings = "; ".join(result.receipt.warnings or []) or "unknown error"
        raise RuntimeError(f"Trust snapshot fetch failed: {warnings}")
    return dict(result.data or {})
