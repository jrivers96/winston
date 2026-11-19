"""Domain enumerations."""

from enum import Enum, auto


class ExecutionStatus(str, Enum):
    """Status of a calculation execution."""
    
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactType(str, Enum):
    """Type of produced artifact."""
    
    STATE = "state"
    OUTPUT = "output"
    EVIDENCE = "evidence"
    REPORT = "report"


class Scenario(str, Enum):
    """Investigation scenario type."""
    
    AS_EXECUTED = "as_executed"
    COUNTERFACTUAL = "counterfactual"
    CORRECTED_PLAN = "corrected_plan"


class IssueState(str, Enum):
    """Lifecycle state of an issue."""
    
    OPEN = "open"
    INVESTIGATING = "investigating"
    PENDING_ACTION = "pending_action"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class ObligationState(str, Enum):
    """State of a follow-up obligation."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class EvidenceCategory(str, Enum):
    """Category of evidence for a dependency or claim."""
    
    OBSERVED = "observed"      # Directly observed in source/runtime
    DECLARED = "declared"      # Declared in manifest/config
    INFERRED = "inferred"      # Inferred from analysis
    UNRESOLVED = "unresolved"  # Dependency exists but details unknown


class DependencyCategory(str, Enum):
    """Category of software dependency edge."""
    
    BUILD_INPUT = "build_input"
    PACKAGED = "packaged"
    DYNAMIC_LOAD = "dynamic_load"
    API_CONTRACT = "api_contract"
    DEV_ONLY = "dev_only"


class CompletionStatus(str, Enum):
    """Completion status for collection or analysis."""
    
    COMPLETE = "complete"
    EMPTY = "empty"
    PARTIAL = "partial"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    TIMED_OUT = "timed_out"
    HISTORICAL_UNAVAILABLE = "historical_unavailable"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
