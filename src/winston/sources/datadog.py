"""Datadog source adapter for operational telemetry.

Provides read access to:
- Execution metrics (duration, errors, resources)
- Service health indicators
- Time-windowed observations

Does NOT provide write access.
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
class DatadogConfig:
    """Configuration for Datadog connection."""
    
    # Connection
    site: str = "datadoghq.com"  # or datadoghq.eu, etc.
    
    # Authentication (references, not values)
    auth_method: str = "api_key"
    credential_provider: str = ""
    
    # Query settings
    max_query_window_hours: int = 24
    max_series_per_query: int = 100
    
    # Metric mappings
    metric_mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    @property
    def is_configured(self) -> bool:
        """Check if minimally configured."""
        return bool(self.site and self.credential_provider)


class TelemetryReader(SourceAdapter[Dict]):
    """Reader for telemetry from Datadog.
    
    This is an abstract base class. Concrete implementations:
    - DatadogLiveReader: Connects to actual Datadog
    - DatadogFixtureReader: Uses recorded fixtures
    """
    
    @property
    def source_type(self) -> str:
        return "datadog"
    
    @abstractmethod
    def get_metrics(
        self,
        metric_query: str,
        start_time: datetime,
        end_time: datetime,
    ) -> SourceResult:
        """Get metrics for a time window."""
        ...
    
    @abstractmethod
    def get_execution_metrics(
        self,
        execution_id: str,
        execution_start: datetime,
        execution_end: datetime,
        margin_minutes: int = 5,
    ) -> SourceResult:
        """Get metrics for a specific execution window."""
        ...


class DatadogFixtureReader(TelemetryReader):
    """Fixture-based reader for offline testing."""
    
    def __init__(self, fixtures: Dict[str, Any]):
        """Initialize with fixture data.
        
        Args:
            fixtures: Dict containing fixture metric data
        """
        self._fixtures = fixtures
    
    def is_available(self) -> bool:
        return True
    
    def query(self, **kwargs: Any) -> SourceResult:
        """Execute a query against fixtures."""
        query_type = kwargs.get("query_type")
        
        if query_type == "get_metrics":
            return self.get_metrics(
                kwargs["metric_query"],
                kwargs["start_time"],
                kwargs["end_time"],
            )
        elif query_type == "get_execution_metrics":
            return self.get_execution_metrics(
                kwargs["execution_id"],
                kwargs["execution_start"],
                kwargs["execution_end"],
                kwargs.get("margin_minutes", 5),
            )
        else:
            return self._error_result(f"Unknown query type: {query_type}")
    
    def get_metrics(
        self,
        metric_query: str,
        start_time: datetime,
        end_time: datetime,
    ) -> SourceResult:
        """Get metrics from fixtures."""
        metrics = self._fixtures.get("metrics", {})
        
        # Simple lookup by query string
        if metric_query in metrics:
            return self._success_result({
                "query": metric_query,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "series": metrics[metric_query],
            })
        
        # Return empty series for unknown metrics
        return self._success_result({
            "query": metric_query,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "series": [],
        })
    
    def get_execution_metrics(
        self,
        execution_id: str,
        execution_start: datetime,
        execution_end: datetime,
        margin_minutes: int = 5,
    ) -> SourceResult:
        """Get metrics for execution from fixtures."""
        exec_metrics = self._fixtures.get("execution_metrics", {})
        
        if execution_id in exec_metrics:
            data = exec_metrics[execution_id]
            data["execution_id"] = execution_id
            data["window_start"] = execution_start.isoformat()
            data["window_end"] = execution_end.isoformat()
            return self._success_result(data)
        
        # Return empty metrics
        return self._success_result({
            "execution_id": execution_id,
            "window_start": execution_start.isoformat(),
            "window_end": execution_end.isoformat(),
            "metrics": {},
            "note": "No metrics found in fixtures",
        })
    
    def _success_result(self, data: Any) -> SourceResult:
        """Create a successful result."""
        return SourceResult(
            data=data,
            receipt=CollectionReceipt(
                source_type="datadog_fixture",
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
                source_type="datadog_fixture",
                source_scope="fixture",
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.FAILED,
                warnings=[message],
            ),
        )


class DatadogLiveReader(TelemetryReader):
    """Live reader connecting to actual Datadog.
    
    Requires datadog-api-client package and valid credentials.
    """
    
    def __init__(self, config: DatadogConfig):
        """Initialize with configuration.
        
        Args:
            config: Datadog connection configuration
        """
        self._config = config
    
    def is_available(self) -> bool:
        """Check if Datadog is available."""
        if not self._config.is_configured:
            return False
        
        try:
            import datadog_api_client  # noqa
            return True
        except ImportError:
            return False
    
    def query(self, **kwargs: Any) -> SourceResult:
        """Execute a query - requires live implementation."""
        return self._not_implemented("Live queries require datadog-api-client")
    
    def get_metrics(
        self,
        metric_query: str,
        start_time: datetime,
        end_time: datetime,
    ) -> SourceResult:
        """Get metrics - requires live implementation."""
        return self._not_implemented("get_metrics")
    
    def get_execution_metrics(
        self,
        execution_id: str,
        execution_start: datetime,
        execution_end: datetime,
        margin_minutes: int = 5,
    ) -> SourceResult:
        """Get execution metrics - requires live implementation."""
        return self._not_implemented("get_execution_metrics")
    
    def _not_implemented(self, operation: str) -> SourceResult:
        """Create a not-implemented result."""
        return SourceResult(
            data={"error": f"Live {operation} not implemented"},
            receipt=CollectionReceipt(
                source_type="datadog",
                source_scope=self._config.site,
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.UNSUPPORTED,
                warnings=[f"Live {operation} requires implementation with credentials"],
            ),
        )
