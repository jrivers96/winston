"""Base classes for source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from winston.domain import CollectionReceipt, CompletionStatus


class SourceResult(BaseModel):
    """Result from a source query."""
    
    data: Any
    receipt: CollectionReceipt
    
    @property
    def is_complete(self) -> bool:
        """Check if result is complete."""
        return self.receipt.status == CompletionStatus.COMPLETE


T = TypeVar("T")


class SourceAdapter(ABC, Generic[T]):
    """Base class for source adapters.
    
    Source adapters provide read access to external data sources
    like Databricks and Datadog, with recording and replay support.
    """
    
    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier."""
        ...
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the source is available."""
        ...
    
    @abstractmethod
    def query(self, **kwargs: Any) -> SourceResult:
        """Execute a query against the source.
        
        All queries must return a SourceResult with a CollectionReceipt.
        """
        ...


class RecordingAdapter(SourceAdapter[T]):
    """Wrapper adapter that records queries for replay."""
    
    def __init__(self, inner: SourceAdapter[T], recording_path: str):
        self._inner = inner
        self._recording_path = recording_path
    
    @property
    def source_type(self) -> str:
        return f"recording:{self._inner.source_type}"
    
    def is_available(self) -> bool:
        return self._inner.is_available()
    
    def query(self, **kwargs: Any) -> SourceResult:
        result = self._inner.query(**kwargs)
        # Would record the query and result here
        return result


class ReplayAdapter(SourceAdapter[T]):
    """Adapter that replays recorded queries."""
    
    def __init__(self, recording_path: str):
        self._recording_path = recording_path
        self._recordings: dict[str, Any] = {}
    
    @property
    def source_type(self) -> str:
        return "replay"
    
    def is_available(self) -> bool:
        return True  # Replay is always available if recordings exist
    
    def query(self, **kwargs: Any) -> SourceResult:
        # Would look up recorded result here
        raise NotImplementedError("Replay not yet implemented")
