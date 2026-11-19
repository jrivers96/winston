"""Databricks source adapter for business data.

Provides read access to:
- Index definitions and calendars
- Executions and their status
- Input manifests and version information
- State/output artifacts
- Selected revisions

Does NOT provide write access or job triggering.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from winston.domain import CollectionReceipt, CompletionStatus
from winston.sources.base import SourceAdapter, SourceResult


@dataclass
class DatabricksConfig:
    """Configuration for Databricks connection."""
    
    # Connection
    host: str = ""
    warehouse_id: str = ""
    catalog: str = ""
    
    # Authentication (references, not values)
    auth_method: str = "oauth_m2m"
    credential_provider: str = ""
    
    # Query settings
    statement_timeout_seconds: int = 300
    max_rows_per_query: int = 10000
    
    # Source mappings
    source_mappings: Dict[str, str] = field(default_factory=dict)
    
    @property
    def is_configured(self) -> bool:
        """Check if minimally configured."""
        return bool(self.host and self.warehouse_id)


class BusinessDataReader(SourceAdapter[Dict]):
    """Reader for business data from Databricks.
    
    This is an abstract base class. Concrete implementations:
    - DatabricksLiveReader: Connects to actual Databricks
    - DatabricksFixtureReader: Uses recorded fixtures
    """
    
    @property
    def source_type(self) -> str:
        return "databricks"
    
    @abstractmethod
    def get_executions(
        self,
        index_id: str,
        from_date: str,
        to_date: str,
        environment: Optional[str] = None,
    ) -> SourceResult:
        """Get executions for an index and date range."""
        ...
    
    @abstractmethod
    def get_execution(self, execution_id: str) -> SourceResult:
        """Get a specific execution by ID."""
        ...
    
    @abstractmethod
    def get_input_manifest(self, manifest_id: str) -> SourceResult:
        """Get input manifest for an execution."""
        ...
    
    @abstractmethod
    def get_state_artifact(self, artifact_id: str) -> SourceResult:
        """Get state artifact content."""
        ...
    
    @abstractmethod
    def check_table_version_available(
        self,
        table_name: str,
        version: int,
    ) -> SourceResult:
        """Check if a table version is still available for time travel."""
        ...


class DatabricksFixtureReader(BusinessDataReader):
    """Fixture-based reader for offline testing.
    
    Uses pre-recorded or synthetic data instead of connecting
    to actual Databricks.
    """
    
    def __init__(self, fixtures: Dict[str, Any]):
        """Initialize with fixture data.
        
        Args:
            fixtures: Dict containing fixture data for various queries
        """
        self._fixtures = fixtures
    
    def is_available(self) -> bool:
        return True
    
    def query(self, **kwargs: Any) -> SourceResult:
        """Execute a query against fixtures."""
        query_type = kwargs.get("query_type")
        
        if query_type == "get_executions":
            return self.get_executions(
                kwargs["index_id"],
                kwargs["from_date"],
                kwargs["to_date"],
                kwargs.get("environment"),
            )
        elif query_type == "get_execution":
            return self.get_execution(kwargs["execution_id"])
        elif query_type == "get_input_manifest":
            return self.get_input_manifest(kwargs["manifest_id"])
        elif query_type == "get_state_artifact":
            return self.get_state_artifact(kwargs["artifact_id"])
        else:
            return self._error_result(f"Unknown query type: {query_type}")
    
    def get_executions(
        self,
        index_id: str,
        from_date: str,
        to_date: str,
        environment: Optional[str] = None,
    ) -> SourceResult:
        """Get executions from fixtures."""
        executions = self._fixtures.get("executions", {})
        
        results = []
        for exec_id, exec_data in executions.items():
            if exec_data.get("index_id") != index_id:
                continue
            
            date = exec_data.get("business_date", "")
            if date < from_date or date > to_date:
                continue
            
            if environment and exec_data.get("environment") != environment:
                continue
            
            results.append(exec_data)
        
        return self._success_result({"executions": results})
    
    def get_execution(self, execution_id: str) -> SourceResult:
        """Get single execution from fixtures."""
        executions = self._fixtures.get("executions", {})
        
        if execution_id in executions:
            return self._success_result(executions[execution_id])
        
        return self._error_result(f"Execution not found: {execution_id}")
    
    def get_input_manifest(self, manifest_id: str) -> SourceResult:
        """Get input manifest from fixtures."""
        manifests = self._fixtures.get("input_manifests", {})
        
        if manifest_id in manifests:
            return self._success_result(manifests[manifest_id])
        
        return self._error_result(f"Manifest not found: {manifest_id}")
    
    def get_state_artifact(self, artifact_id: str) -> SourceResult:
        """Get state artifact from fixtures."""
        artifacts = self._fixtures.get("artifacts", {})
        
        if artifact_id in artifacts:
            return self._success_result(artifacts[artifact_id])
        
        return self._error_result(f"Artifact not found: {artifact_id}")
    
    def check_table_version_available(
        self,
        table_name: str,
        version: int,
    ) -> SourceResult:
        """Check table version availability in fixtures."""
        versions = self._fixtures.get("table_versions", {})
        table_versions = versions.get(table_name, [])
        
        available = version in table_versions
        
        return self._success_result({
            "table_name": table_name,
            "version": version,
            "available": available,
            "reason": None if available else "historical_unavailable",
        })
    
    def _success_result(self, data: Any) -> SourceResult:
        """Create a successful result."""
        return SourceResult(
            data=data,
            receipt=CollectionReceipt(
                source_type="databricks_fixture",
                source_scope="fixture",
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.COMPLETE,
            ),
        )
    
    def _error_result(self, message: str) -> SourceResult:
        """Create an error result."""
        return SourceResult(
            data={"error": message},
            receipt=CollectionReceipt(
                source_type="databricks_fixture",
                source_scope="fixture",
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.FAILED,
                warnings=[message],
            ),
        )


class DatabricksLiveReader(BusinessDataReader):
    """Live reader connecting to actual Databricks.
    
    Requires databricks-sql-connector package and valid credentials.
    """
    
    def __init__(self, config: DatabricksConfig):
        """Initialize with configuration.
        
        Args:
            config: Databricks connection configuration
        """
        self._config = config
        self._connection = None
    
    def is_available(self) -> bool:
        """Check if Databricks is available."""
        if not self._config.is_configured:
            return False
        
        # Would check actual connectivity here
        try:
            # Import to check if package is installed
            import databricks.sql  # noqa
            return True
        except ImportError:
            return False
    
    def query(self, **kwargs: Any) -> SourceResult:
        """Execute a query - requires live implementation."""
        return self._not_implemented("Live queries require databricks-sql-connector")
    
    def get_executions(
        self,
        index_id: str,
        from_date: str,
        to_date: str,
        environment: Optional[str] = None,
    ) -> SourceResult:
        """Get executions - requires live implementation."""
        return self._not_implemented("get_executions")
    
    def get_execution(self, execution_id: str) -> SourceResult:
        """Get execution - requires live implementation."""
        return self._not_implemented("get_execution")
    
    def get_input_manifest(self, manifest_id: str) -> SourceResult:
        """Get manifest - requires live implementation."""
        return self._not_implemented("get_input_manifest")
    
    def get_state_artifact(self, artifact_id: str) -> SourceResult:
        """Get artifact - requires live implementation."""
        return self._not_implemented("get_state_artifact")
    
    def check_table_version_available(
        self,
        table_name: str,
        version: int,
    ) -> SourceResult:
        """Check version - requires live implementation."""
        return self._not_implemented("check_table_version_available")
    
    def _not_implemented(self, operation: str) -> SourceResult:
        """Create a not-implemented result."""
        return SourceResult(
            data={"error": f"Live {operation} not implemented"},
            receipt=CollectionReceipt(
                source_type="databricks",
                source_scope=self._config.host or "unconfigured",
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.UNSUPPORTED,
                warnings=[f"Live {operation} requires implementation with credentials"],
            ),
        )
