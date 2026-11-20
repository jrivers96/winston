"""Postgres source adapter for Supercalc business data.

Read-only access to Supercalc Postgres (views preferred over raw tables).
Does NOT provide write access, DDL, or job triggering.
Winston's own Cloud SQL is separate — never point this at winston-ops agent state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from winston.domain import CollectionReceipt, CompletionStatus
from winston.sources.base import SourceResult
from winston.sources.databricks import BusinessDataReader


@dataclass
class PostgresConfig:
    """Configuration for Supercalc Postgres (references, not secret values)."""

    host: str = ""
    port: int = 5432
    database: str = ""
    sslmode: str = "require"
    auth_method: str = ""
    credential_provider: str = ""
    connect_timeout_seconds: int = 30
    statement_timeout_seconds: int = 60
    private_ip_required: bool = True
    read_only: bool = True
    max_rows_per_query: int = 500
    # relation name -> column map (filled from live profile)
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


class PostgresLiveReader(BusinessDataReader):
    """Live read-only Postgres reader for Supercalc.

    Requires psycopg (core Winston dep) and a configured credential_provider.
    Query templates stay allowlisted — this stub never invents SQL against
    unknown relations.
    """

    def __init__(self, config: PostgresConfig):
        self._config = config

    @property
    def source_type(self) -> str:
        return "postgres"

    def is_available(self) -> bool:
        """True when config is present and psycopg can be imported."""
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
        return self._not_implemented("Live queries require allowlisted SQL templates")

    def get_executions(
        self,
        index_id: str,
        from_date: str,
        to_date: str,
        environment: Optional[str] = None,
    ) -> SourceResult:
        return self._not_implemented("get_executions")

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
        # Postgres time-travel is not assumed; Supercalc may use as-of views instead.
        return self._not_implemented("check_table_version_available")

    def probe_connectivity(self) -> SourceResult:
        """Bounded readiness probe — does not run product queries.

        Stub: reports unsupported until DSN resolution + SELECT 1 is wired
        against credential_provider without logging secrets.
        """
        return self._not_implemented("probe_connectivity")

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
