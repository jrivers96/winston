"""Base classes for checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class CheckSeverity(str, Enum):
    """Severity level for check findings."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CheckStatus(str, Enum):
    """Status of a check result."""
    
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class CheckResult:
    """Result of running a check."""
    
    # Check identification
    check_id: str
    check_version: str
    
    # Scope
    index_id: Optional[str] = None
    business_date: Optional[str] = None
    execution_id: Optional[str] = None
    
    # Result
    status: CheckStatus = CheckStatus.UNKNOWN
    severity: CheckSeverity = CheckSeverity.INFO
    
    # Details
    message: str = ""
    expected: Optional[str] = None
    observed: Optional[str] = None
    
    # Evidence
    evidence_refs: List[str] = field(default_factory=list)
    
    # Completeness
    is_complete: bool = True
    incomplete_reason: Optional[str] = None
    
    # Timestamp
    checked_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_id": self.check_id,
            "check_version": self.check_version,
            "index_id": self.index_id,
            "business_date": self.business_date,
            "execution_id": self.execution_id,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "expected": self.expected,
            "observed": self.observed,
            "evidence_refs": self.evidence_refs,
            "is_complete": self.is_complete,
            "incomplete_reason": self.incomplete_reason,
            "checked_at": self.checked_at.isoformat(),
            "metadata": self.metadata,
        }


class Check(ABC):
    """Base class for deterministic checks."""
    
    @property
    @abstractmethod
    def check_id(self) -> str:
        """Unique identifier for this check."""
        ...
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Version of this check."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this check verifies."""
        ...
    
    @abstractmethod
    def run(self, context: Dict[str, Any]) -> CheckResult:
        """Run the check.
        
        Args:
            context: Context data needed for the check
            
        Returns:
            CheckResult with findings
        """
        ...
    
    def _create_result(
        self,
        status: CheckStatus,
        message: str,
        **kwargs: Any,
    ) -> CheckResult:
        """Helper to create a result with this check's metadata."""
        return CheckResult(
            check_id=self.check_id,
            check_version=self.version,
            status=status,
            message=message,
            **kwargs,
        )
