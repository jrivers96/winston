"""Postgres source adapter for Supercalc business data.

Read-only access to Supercalc Postgres. Allowlisted relations only.
Does NOT provide write access, DDL, or job triggering.
Winston's own Cloud SQL is separate — never point this at winston-ops agent state.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from winston.domain import CollectionReceipt, CompletionStatus
from winston.sources.base import SourceResult
from winston.sources.databricks import BusinessDataReader


# Only these Supercalc relations may appear in live SQL
ALLOWED_RELATIONS = frozenset(
    {
        "discovered_index_definitions",
        "indexes",
        "integrity_checks",
        "hedge_alert_outcomes",
        "risk_rollups",
        "signals",
    }
)

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_PROVIDER = re.compile(r"^secret:(?P<name>[A-Za-z0-9_-]+)$")
_ENV_PROVIDER = re.compile(r"^env:(?P<name>[A-Za-z0-9_]+)$")


@dataclass
class PostgresConfig:
    """Configuration for Supercalc Postgres (references, not secret values)."""

    host: str = ""
    port: int = 5432
    database: str = ""
    sslmode: str = "require"
    auth_method: str = ""
    credential_provider: str = ""
    db_user: str = "winston_readonly"
    connect_timeout_seconds: int = 30
    statement_timeout_seconds: int = 60
    private_ip_required: bool = True
    read_only: bool = True
    max_rows_per_query: int = 500
    connection_name: str = ""
    # mapping_id -> {relation, columns}
    source_mappings: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        """Check if minimally configured for a live attempt."""
        return bool(
            self.host
            and self.database
            and self.auth_method
            and self.credential_provider
        )


def _validate_ident(name: str, kind: str) -> str:
    if not name or not _IDENT.match(name):
        raise ValueError(f"Invalid {kind} identifier: {name!r}")
    return name


def resolve_password(credential_provider: str) -> str:
    """Resolve password from env: or secret: providers without logging it.

    secret:NAME looks up:
      1) env WINSTON_SECRET_<NAME upper snake>
      2) env matching NAME if set
      3) google.cloud.secretmanager (optional) project from WINSTON_GCP_PROJECT
    """
    provider = (credential_provider or "").strip()
    env_match = _ENV_PROVIDER.match(provider)
    if env_match:
        value = os.environ.get(env_match.group("name"), "")
        if not value:
            raise RuntimeError(f"Environment variable {env_match.group('name')} is empty")
        return value

    secret_match = _SECRET_PROVIDER.match(provider)
    if secret_match:
        name = secret_match.group("name")
        env_key = f"WINSTON_SECRET_{name.upper().replace('-', '_')}"
        if os.environ.get(env_key):
            return os.environ[env_key]
        # Common Cloud Run injection
        if os.environ.get("WINSTON_SUPERCALC_PG_PASSWORD"):
            return os.environ["WINSTON_SUPERCALC_PG_PASSWORD"]
        if os.environ.get(name):
            return os.environ[name]
        project = os.environ.get("WINSTON_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project:
            try:
                from google.cloud import secretmanager  # type: ignore

                client = secretmanager.SecretManagerServiceClient()
                path = f"projects/{project}/secrets/{name}/versions/latest"
                response = client.access_secret_version(request={"name": path})
                return response.payload.data.decode("utf-8")
            except Exception as exc:  # noqa: BLE001 — surface as config error
                raise RuntimeError(
                    f"Failed to read secret {name} from project {project}: {exc}"
                ) from exc
        raise RuntimeError(
            f"Cannot resolve secret:{name}; set {env_key} or WINSTON_SUPERCALC_PG_PASSWORD "
            "or WINSTON_GCP_PROJECT with Secret Manager access"
        )

    raise RuntimeError(
        f"Unsupported credential_provider {provider!r}; use env:VAR or secret:NAME"
    )


class PostgresLiveReader(BusinessDataReader):
    """Live read-only Postgres reader for Supercalc (allowlisted relations)."""

    def __init__(self, config: PostgresConfig):
        self._config = config

    @property
    def source_type(self) -> str:
        return "postgres"

    def is_available(self) -> bool:
        if not self._config.is_configured:
            return False
        if not self._config.read_only:
            return False
        try:
            import psycopg  # noqa: F401
            return True
        except ImportError:
            return False

    def query(self, **kwargs: Any) -> SourceResult:
        return self._not_implemented("Use probe_mapped_relations / get_* allowlisted helpers")

    def get_executions(
        self,
        index_id: str,
        from_date: str,
        to_date: str,
        environment: Optional[str] = None,
    ) -> SourceResult:
        # Supercalc has no executions table — map smoke to integrity_checks window
        return self.probe_mapped_relations(mapping_ids=["integrity_checks"])

    def get_execution(self, execution_id: str) -> SourceResult:
        return self._not_implemented("get_execution")

    def get_input_manifest(self, manifest_id: str) -> SourceResult:
        return self._not_implemented("get_input_manifest")

    def get_state_artifact(self, artifact_id: str) -> SourceResult:
        return self._not_implemented("get_state_artifact")

    def check_table_version_available(
        self,
        table_name: str,
        version: int,
    ) -> SourceResult:
        return self._not_implemented("check_table_version_available")

    def probe_connectivity(self) -> SourceResult:
        started = datetime.now(timezone.utc)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return self._ok({"ok": True}, started, message="SELECT 1 ok")
        except Exception as exc:  # noqa: BLE001
            return self._fail(str(exc), started)

    def fetch_trust_snapshot(
        self,
        *,
        index_name: Optional[str] = None,
        lookback_dates: int = 5,
        max_integrity_rows: Optional[int] = None,
    ) -> SourceResult:
        """Bounded reads that feed live trust-check contexts.

        Pulls latest integrity run timestamps / non-pass rows, distinct series
        session dates for an index, and optional coverage counts. Read-only.
        """
        started = datetime.now(timezone.utc)
        mappings = self._config.source_mappings or {}
        limit = max(1, min(int(self._config.max_rows_per_query), 500))
        integrity_limit = max(
            1, min(int(max_integrity_rows or limit), limit)
        )
        lookback = max(1, min(int(lookback_dates), 30))

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET default_transaction_read_only = on")
                    timeout_ms = int(self._config.statement_timeout_seconds) * 1000
                    cur.execute(
                        "SELECT set_config('statement_timeout', %s, false)",
                        (str(timeout_ms),),
                    )

                snapshot: Dict[str, Any] = {
                    "latest_integrity_run_ts": None,
                    "integrity_failures": [],
                    "integrity_rows_scanned": 0,
                    "series_dates": [],
                    "series_latest_ts": None,
                    "covered_count": None,
                    "universe_count": None,
                    "index_name": index_name,
                }

                integrity_map = mappings.get("integrity_checks") or {}
                integrity_rel = str(
                    integrity_map.get("relation")
                    or integrity_map.get("table_name")
                    or ""
                ).strip()
                if integrity_rel:
                    if integrity_rel not in ALLOWED_RELATIONS:
                        raise ValueError(
                            f"Relation {integrity_rel!r} for integrity_checks "
                            "is not allowlisted"
                        )
                    cols = integrity_map.get("columns") or {}
                    run_ts_col = _validate_ident(
                        str(cols.get("run_ts") or "run_ts"), "column"
                    )
                    status_col = _validate_ident(
                        str(cols.get("status") or "status"), "column"
                    )
                    name_col = _validate_ident(
                        str(cols.get("check_name") or "check_name"), "column"
                    )
                    observed_col = _validate_ident(
                        str(cols.get("observed") or "observed"), "column"
                    )
                    threshold_col = _validate_ident(
                        str(cols.get("threshold") or "threshold"), "column"
                    )
                    details_col = _validate_ident(
                        str(cols.get("details") or "details"), "column"
                    )
                    rel = _validate_ident(integrity_rel, "relation")
                    sql = (
                        f'SELECT "{run_ts_col}", "{name_col}", "{status_col}", '
                        f'"{observed_col}", "{threshold_col}", "{details_col}" '
                        f'FROM public."{rel}" '
                        f'ORDER BY "{run_ts_col}" DESC NULLS LAST '
                        f"LIMIT {integrity_limit}"
                    )
                    with conn.cursor() as cur:
                        cur.execute(sql)
                        rows = cur.fetchall()
                    snapshot["integrity_rows_scanned"] = len(rows)
                    failures: List[Dict[str, Any]] = []
                    latest_ts = None
                    for row in rows:
                        run_ts, check_name, status, observed, threshold, details = row
                        if latest_ts is None and run_ts is not None:
                            latest_ts = run_ts
                        status_norm = (str(status).strip().lower() if status else "")
                        if status_norm and status_norm not in {
                            "pass",
                            "ok",
                            "healthy",
                            "succeeded",
                            "success",
                        }:
                            failures.append(
                                {
                                    "check_name": check_name,
                                    "status": status,
                                    "observed": observed,
                                    "threshold": threshold,
                                    "details": details,
                                    "run_ts": (
                                        run_ts.isoformat()
                                        if hasattr(run_ts, "isoformat")
                                        else run_ts
                                    ),
                                }
                            )
                    snapshot["latest_integrity_run_ts"] = (
                        latest_ts.isoformat()
                        if hasattr(latest_ts, "isoformat")
                        else latest_ts
                    )
                    snapshot["integrity_failures"] = failures

                series_map = mappings.get("index_series") or {}
                series_rel = str(
                    series_map.get("relation") or series_map.get("table_name") or ""
                ).strip()
                if series_rel and index_name:
                    if series_rel not in ALLOWED_RELATIONS:
                        raise ValueError(
                            f"Relation {series_rel!r} for index_series "
                            "is not allowlisted"
                        )
                    cols = series_map.get("columns") or {}
                    ts_col = _validate_ident(
                        str(cols.get("timestamp") or "timestamp"), "column"
                    )
                    name_col = _validate_ident(
                        str(cols.get("index_name") or "index_name"), "column"
                    )
                    rel = _validate_ident(series_rel, "relation")
                    # Distinct calendar dates for the configured index (bounded).
                    dates_sql = (
                        f'SELECT DISTINCT ("{ts_col}"::date)::text AS session_date '
                        f'FROM public."{rel}" '
                        f'WHERE "{name_col}" = %s '
                        f'ORDER BY session_date DESC '
                        f"LIMIT {lookback}"
                    )
                    latest_sql = (
                        f'SELECT MAX("{ts_col}") FROM public."{rel}" '
                        f'WHERE "{name_col}" = %s'
                    )
                    covered_sql = (
                        f'SELECT COUNT(*) FROM public."{rel}" '
                        f'WHERE "{name_col}" = %s'
                    )
                    with conn.cursor() as cur:
                        cur.execute(dates_sql, (index_name,))
                        date_rows = cur.fetchall()
                        cur.execute(latest_sql, (index_name,))
                        latest_row = cur.fetchone()
                        cur.execute(covered_sql, (index_name,))
                        covered_row = cur.fetchone()
                    # Oldest→newest for expected-session comparison readability
                    snapshot["series_dates"] = sorted(
                        str(r[0]) for r in date_rows if r and r[0]
                    )
                    latest_series = latest_row[0] if latest_row else None
                    snapshot["series_latest_ts"] = (
                        latest_series.isoformat()
                        if hasattr(latest_series, "isoformat")
                        else latest_series
                    )
                    snapshot["covered_count"] = (
                        int(covered_row[0]) if covered_row and covered_row[0] is not None else None
                    )

                defs_map = mappings.get("index_definitions") or {}
                defs_rel = str(
                    defs_map.get("relation") or defs_map.get("table_name") or ""
                ).strip()
                if defs_rel:
                    if defs_rel not in ALLOWED_RELATIONS:
                        raise ValueError(
                            f"Relation {defs_rel!r} for index_definitions "
                            "is not allowlisted"
                        )
                    rel = _validate_ident(defs_rel, "relation")
                    with conn.cursor() as cur:
                        cur.execute(f'SELECT COUNT(*) FROM public."{rel}"')
                        universe_row = cur.fetchone()
                    snapshot["universe_count"] = (
                        int(universe_row[0])
                        if universe_row and universe_row[0] is not None
                        else None
                    )

            return self._ok(
                snapshot,
                started,
                message="Trust snapshot fetched from allowlisted relations",
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(str(exc), started)

    def probe_mapped_relations(
        self,
        mapping_ids: Optional[Sequence[str]] = None,
    ) -> SourceResult:
        """Run bounded SELECT COUNT + LIMIT probes for allowlisted mappings."""
        started = datetime.now(timezone.utc)
        mappings = self._config.source_mappings or {}
        ids = list(mapping_ids) if mapping_ids is not None else list(mappings.keys())
        if not ids:
            return self._fail("No source_mappings configured", started)

        results: Dict[str, Any] = {}
        try:
            with self._connect() as conn:
                # Enforce read-only session
                with conn.cursor() as cur:
                    cur.execute("SET default_transaction_read_only = on")
                    timeout_ms = int(self._config.statement_timeout_seconds) * 1000
                    cur.execute("SELECT set_config('statement_timeout', %s, false)", (str(timeout_ms),))
                for mapping_id in ids:
                    mapping = mappings.get(mapping_id)
                    if not isinstance(mapping, dict):
                        raise ValueError(f"Missing mapping object: {mapping_id}")
                    relation = mapping.get("relation") or mapping.get("table_name") or ""
                    relation = str(relation).strip()
                    if relation not in ALLOWED_RELATIONS:
                        raise ValueError(
                            f"Relation {relation!r} for {mapping_id} is not allowlisted"
                        )
                    columns = mapping.get("columns") or {}
                    if not isinstance(columns, dict) or not columns:
                        raise ValueError(f"Mapping {mapping_id} has no columns")
                    col_names = [
                        _validate_ident(str(v), "column")
                        for v in columns.values()
                        if str(v).strip()
                    ]
                    if not col_names:
                        raise ValueError(f"Mapping {mapping_id} columns are blank")
                    rel = _validate_ident(relation, "relation")
                    limit = max(1, min(int(self._config.max_rows_per_query), 500))
                    cols_sql = ", ".join(col_names)
                    count_sql = f'SELECT COUNT(*) FROM public."{rel}"'
                    sample_sql = (
                        f'SELECT {cols_sql} FROM public."{rel}" LIMIT {limit}'
                    )
                    with conn.cursor() as cur:
                        cur.execute(count_sql)
                        count = int(cur.fetchone()[0])
                        cur.execute(sample_sql)
                        rows = cur.fetchall()
                        colnames = [d.name for d in cur.description] if cur.description else []
                    results[mapping_id] = {
                        "relation": rel,
                        "count": count,
                        "sample_rows": len(rows),
                        "columns": colnames,
                    }
            return self._ok(
                {"probes": results},
                started,
                message=f"Probed {len(results)} allowlisted relations",
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(str(exc), started)

    def _connect(self):
        import psycopg

        password = resolve_password(self._config.credential_provider)
        kwargs: Dict[str, Any] = {
            "dbname": self._config.database,
            "user": self._config.db_user or "winston_readonly",
            "password": password,
            "connect_timeout": int(self._config.connect_timeout_seconds),
        }
        host = self._config.host
        if host.startswith("/cloudsql/") or host.startswith("/"):
            # Cloud SQL Auth Proxy unix socket directory
            kwargs["host"] = host
        else:
            kwargs["host"] = host
            kwargs["port"] = int(self._config.port)
            kwargs["sslmode"] = self._config.sslmode or "require"
        return psycopg.connect(**kwargs)

    def _ok(self, data: Dict[str, Any], started: datetime, message: str) -> SourceResult:
        return SourceResult(
            data=data,
            receipt=CollectionReceipt(
                source_type="postgres",
                source_scope=self._config.host or "configured",
                local_request_id=uuid4().hex,
                collection_started_at=started,
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.COMPLETE,
                warnings=[],
            ),
        )

    def _fail(self, message: str, started: datetime) -> SourceResult:
        return SourceResult(
            data={"error": message},
            receipt=CollectionReceipt(
                source_type="postgres",
                source_scope=self._config.host or "unconfigured",
                local_request_id=uuid4().hex,
                collection_started_at=started,
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.FAILED,
                warnings=[message],
            ),
        )

    def _not_implemented(self, operation: str) -> SourceResult:
        return SourceResult(
            data={"error": f"Live {operation} not implemented"},
            receipt=CollectionReceipt(
                source_type="postgres",
                source_scope=self._config.host or "unconfigured",
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.UNSUPPORTED,
                warnings=[
                    f"Live {operation} requires allowlisted read-only SQL "
                    f"and credential_provider={self._config.credential_provider or 'unset'}"
                ],
            ),
        )
