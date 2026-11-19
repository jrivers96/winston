"""Issue and obligation domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from winston.domain.enums import IssueState, ObligationState
from winston.domain.identities import (
    ArtifactId,
    ExecutionId,
    IndexId,
    IssueId,
    ObligationId,
)


class Issue(BaseModel):
    """An identified problem requiring investigation or action.
    
    Issues track scope, impact, evidence, state, and completion criteria.
    """
    
    id: IssueId = Field(..., description="Unique issue identifier")
    
    # Scope
    title: str = Field(..., description="Brief issue title")
    description: str = Field(..., description="Detailed description")
    index_id: Optional[IndexId] = Field(None, description="Affected index if applicable")
    environment: Optional[str] = Field(None, description="Affected environment")
    affected_dates: List[str] = Field(default_factory=list, description="Affected business dates")
    
    # State
    state: IssueState = Field(default=IssueState.OPEN, description="Current lifecycle state")
    state_changed_at: datetime = Field(..., description="When state last changed")
    
    # Impact
    severity: str = Field(default="medium", description="Issue severity (low/medium/high/critical)")
    impact_summary: Optional[str] = Field(None, description="Summary of impact assessment")
    affected_executions: List[ExecutionId] = Field(
        default_factory=list, description="Affected execution IDs"
    )
    
    # Evidence
    evidence_refs: List[ArtifactId] = Field(
        default_factory=list, description="References to supporting evidence"
    )
    
    # Completion
    completion_criteria: Optional[str] = Field(None, description="What constitutes resolution")
    
    # Recurrence
    previous_issue_id: Optional[IssueId] = Field(
        None, description="Previous occurrence if recurring"
    )
    recurrence_count: int = Field(0, description="Number of recurrences")
    
    # Audit
    created_at: datetime = Field(..., description="When issue was created")
    created_by: str = Field(..., description="Who/what created the issue")
    updated_at: datetime = Field(..., description="When issue was last updated")
    
    # Fingerprint for deduplication
    fingerprint: Optional[str] = Field(
        None, description="Stable fingerprint for deduplication"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class Obligation(BaseModel):
    """A follow-up action required as part of issue resolution.
    
    Obligations track owner, next action, wake conditions, and status.
    """
    
    id: ObligationId = Field(..., description="Unique obligation identifier")
    issue_id: IssueId = Field(..., description="Parent issue")
    
    # Action
    title: str = Field(..., description="Brief obligation title")
    description: str = Field(..., description="What needs to be done")
    action_type: str = Field(..., description="Type of action (verify/investigate/remediate/etc)")
    
    # Ownership
    owner: Optional[str] = Field(None, description="Assigned owner")
    
    # State
    state: ObligationState = Field(
        default=ObligationState.PENDING, description="Current state"
    )
    state_changed_at: datetime = Field(..., description="When state last changed")
    
    # Wake conditions
    wake_condition: Optional[str] = Field(
        None, description="Condition that should trigger progress"
    )
    due_at: Optional[datetime] = Field(None, description="When obligation is due")
    
    # Progress
    progress_notes: List[str] = Field(default_factory=list, description="Progress updates")
    attempts: int = Field(0, description="Number of attempts")
    last_attempt_at: Optional[datetime] = Field(None, description="When last attempted")
    
    # Evidence
    evidence_refs: List[ArtifactId] = Field(
        default_factory=list, description="References to related evidence"
    )
    
    # Audit
    created_at: datetime = Field(..., description="When obligation was created")
    updated_at: datetime = Field(..., description="When obligation was last updated")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
