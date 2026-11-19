"""Repository classes for database operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, List
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from winston.domain import (
    Issue,
    IssueId,
    IssueState,
    Obligation,
    ObligationId,
    ObligationState,
    Execution,
    ExecutionId,
    Artifact,
    ArtifactId,
)
from winston.storage.models import (
    IssueModel,
    ObligationModel,
    ExecutionModel,
    ArtifactModel,
    AuditEventModel,
)


def _now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def _generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


class IssueRepository:
    """Repository for Issue operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, issue: Issue) -> Issue:
        """Create a new issue."""
        model = IssueModel(
            id=str(issue.id),
            title=issue.title,
            description=issue.description,
            index_id=str(issue.index_id) if issue.index_id else None,
            environment=issue.environment,
            affected_dates=issue.affected_dates,
            state=issue.state.value,
            state_changed_at=issue.state_changed_at,
            severity=issue.severity,
            impact_summary=issue.impact_summary,
            affected_executions=[str(e) for e in issue.affected_executions],
            evidence_refs=[str(e) for e in issue.evidence_refs],
            completion_criteria=issue.completion_criteria,
            previous_issue_id=str(issue.previous_issue_id) if issue.previous_issue_id else None,
            recurrence_count=issue.recurrence_count,
            created_at=issue.created_at,
            created_by=issue.created_by,
            updated_at=issue.updated_at,
            fingerprint=issue.fingerprint,
            extra_data=issue.metadata,
        )
        self.session.add(model)
        self.session.flush()
        
        # Create audit event
        self._audit("issue_created", "issue", str(issue.id), None, issue.model_dump())
        
        return issue
    
    def get(self, issue_id: IssueId) -> Issue | None:
        """Get an issue by ID."""
        stmt = select(IssueModel).where(IssueModel.id == str(issue_id))
        model = self.session.execute(stmt).scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_domain(model)
    
    def get_by_fingerprint(self, fingerprint: str) -> Issue | None:
        """Get an issue by fingerprint for deduplication."""
        stmt = select(IssueModel).where(IssueModel.fingerprint == fingerprint)
        model = self.session.execute(stmt).scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_domain(model)
    
    def list_by_state(self, state: IssueState) -> list[Issue]:
        """List issues by state."""
        stmt = select(IssueModel).where(IssueModel.state == state.value)
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in models]
    
    def list_all(self) -> list[Issue]:
        """List all issues."""
        stmt = select(IssueModel).order_by(IssueModel.created_at.desc())
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in models]
    
    def update_state(
        self,
        issue_id: IssueId,
        new_state: IssueState,
        expected_version: int | None = None,
    ) -> Issue | None:
        """Update issue state with optimistic locking.
        
        Args:
            issue_id: Issue to update
            new_state: New state
            expected_version: If provided, only update if version matches
            
        Returns:
            Updated issue or None if not found or version mismatch
        """
        stmt = select(IssueModel).where(IssueModel.id == str(issue_id))
        model = self.session.execute(stmt).scalar_one_or_none()
        
        if model is None:
            return None
        
        if expected_version is not None and model.version != expected_version:
            return None
        
        old_state = model.state
        now = _now()
        
        model.state = new_state.value
        model.state_changed_at = now
        model.updated_at = now
        model.version += 1
        
        self.session.flush()
        
        # Audit
        self._audit(
            "issue_state_changed",
            "issue",
            str(issue_id),
            {"state": old_state},
            {"state": new_state.value},
        )
        
        return self._to_domain(model)
    
    def _to_domain(self, model: IssueModel) -> Issue:
        """Convert ORM model to domain model."""
        return Issue(
            id=IssueId(model.id),
            title=model.title,
            description=model.description,
            index_id=model.index_id,
            environment=model.environment,
            affected_dates=model.affected_dates or [],
            state=IssueState(model.state),
            state_changed_at=model.state_changed_at,
            severity=model.severity,
            impact_summary=model.impact_summary,
            affected_executions=[ExecutionId(e) for e in (model.affected_executions or [])],
            evidence_refs=[ArtifactId(e) for e in (model.evidence_refs or [])],
            completion_criteria=model.completion_criteria,
            previous_issue_id=IssueId(model.previous_issue_id) if model.previous_issue_id else None,
            recurrence_count=model.recurrence_count,
            created_at=model.created_at,
            created_by=model.created_by,
            updated_at=model.updated_at,
            fingerprint=model.fingerprint,
            metadata=model.extra_data or {},
        )
    
    def _audit(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Create an audit event."""
        event = AuditEventModel(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor="winston",
            old_state=old_state,
            new_state=new_state,
            occurred_at=_now(),
        )
        self.session.add(event)


class ObligationRepository:
    """Repository for Obligation operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, obligation: Obligation) -> Obligation:
        """Create a new obligation."""
        model = ObligationModel(
            id=str(obligation.id),
            issue_id=str(obligation.issue_id),
            title=obligation.title,
            description=obligation.description,
            action_type=obligation.action_type,
            owner=obligation.owner,
            state=obligation.state.value,
            state_changed_at=obligation.state_changed_at,
            wake_condition=obligation.wake_condition,
            due_at=obligation.due_at,
            progress_notes=obligation.progress_notes,
            attempts=obligation.attempts,
            last_attempt_at=obligation.last_attempt_at,
            evidence_refs=[str(e) for e in obligation.evidence_refs],
            created_at=obligation.created_at,
            updated_at=obligation.updated_at,
            extra_data=obligation.metadata,
        )
        self.session.add(model)
        self.session.flush()
        return obligation
    
    def get(self, obligation_id: ObligationId) -> Obligation | None:
        """Get an obligation by ID."""
        stmt = select(ObligationModel).where(ObligationModel.id == str(obligation_id))
        model = self.session.execute(stmt).scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_domain(model)
    
    def list_by_issue(self, issue_id: IssueId) -> list[Obligation]:
        """List obligations for an issue."""
        stmt = select(ObligationModel).where(ObligationModel.issue_id == str(issue_id))
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in models]
    
    def list_pending(self) -> list[Obligation]:
        """List pending obligations."""
        stmt = select(ObligationModel).where(
            ObligationModel.state == ObligationState.PENDING.value
        )
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in models]
    
    def update_state(
        self,
        obligation_id: ObligationId,
        new_state: ObligationState,
        expected_version: int | None = None,
    ) -> Obligation | None:
        """Update obligation state with optimistic locking."""
        stmt = select(ObligationModel).where(ObligationModel.id == str(obligation_id))
        model = self.session.execute(stmt).scalar_one_or_none()
        
        if model is None:
            return None
        
        if expected_version is not None and model.version != expected_version:
            return None
        
        now = _now()
        model.state = new_state.value
        model.state_changed_at = now
        model.updated_at = now
        model.version += 1
        
        self.session.flush()
        return self._to_domain(model)
    
    def _to_domain(self, model: ObligationModel) -> Obligation:
        """Convert ORM model to domain model."""
        return Obligation(
            id=ObligationId(model.id),
            issue_id=IssueId(model.issue_id),
            title=model.title,
            description=model.description,
            action_type=model.action_type,
            owner=model.owner,
            state=ObligationState(model.state),
            state_changed_at=model.state_changed_at,
            wake_condition=model.wake_condition,
            due_at=model.due_at,
            progress_notes=model.progress_notes or [],
            attempts=model.attempts,
            last_attempt_at=model.last_attempt_at,
            evidence_refs=[ArtifactId(e) for e in (model.evidence_refs or [])],
            created_at=model.created_at,
            updated_at=model.updated_at,
            metadata=model.extra_data or {},
        )


class ExecutionRepository:
    """Repository for Execution operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, execution: Execution) -> Execution:
        """Create a new execution record."""
        model = ExecutionModel(
            id=str(execution.id),
            attempt_id=execution.attempt_id,
            index_id=str(execution.index_id),
            environment=execution.environment,
            business_date=str(execution.business_date),
            stage=execution.stage,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            status=execution.status.value,
            status_message=execution.status_message,
            input_manifest_id=str(execution.input_manifest_id) if execution.input_manifest_id else None,
            code_manifest_id=str(execution.code_manifest_id) if execution.code_manifest_id else None,
            state_artifact_id=str(execution.state_artifact_id) if execution.state_artifact_id else None,
            output_artifact_id=str(execution.output_artifact_id) if execution.output_artifact_id else None,
            validation_status=execution.validation_status,
            validation_time=execution.validation_time,
            extra_data=execution.metadata,
        )
        self.session.add(model)
        self.session.flush()
        return execution
    
    def get(self, execution_id: ExecutionId) -> Execution | None:
        """Get an execution by ID."""
        stmt = select(ExecutionModel).where(ExecutionModel.id == str(execution_id))
        model = self.session.execute(stmt).scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_domain(model)
    
    def list_by_index_date(
        self,
        index_id: str,
        business_date: str,
        environment: str | None = None,
    ) -> list[Execution]:
        """List executions for an index and date."""
        stmt = select(ExecutionModel).where(
            ExecutionModel.index_id == index_id,
            ExecutionModel.business_date == business_date,
        )
        if environment:
            stmt = stmt.where(ExecutionModel.environment == environment)
        
        models = self.session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in models]
    
    def _to_domain(self, model: ExecutionModel) -> Execution:
        """Convert ORM model to domain model."""
        from datetime import date
        from winston.domain import ExecutionStatus, BusinessDate
        
        return Execution(
            id=ExecutionId(model.id),
            attempt_id=model.attempt_id,
            index_id=model.index_id,
            environment=model.environment,
            business_date=BusinessDate(date.fromisoformat(model.business_date)),
            stage=model.stage,
            started_at=model.started_at,
            completed_at=model.completed_at,
            status=ExecutionStatus(model.status),
            status_message=model.status_message,
            input_manifest_id=model.input_manifest_id,
            code_manifest_id=model.code_manifest_id,
            state_artifact_id=model.state_artifact_id,
            output_artifact_id=model.output_artifact_id,
            validation_status=model.validation_status,
            validation_time=model.validation_time,
            metadata=model.extra_data or {},
        )


class ArtifactRepository:
    """Repository for Artifact metadata operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, artifact: Artifact) -> Artifact:
        """Create artifact metadata record."""
        model = ArtifactModel(
            id=str(artifact.id),
            execution_id=str(artifact.execution_id),
            artifact_type=artifact.artifact_type.value,
            schema_id=artifact.schema_id,
            schema_version=artifact.schema_version,
            is_available=artifact.is_available,
            availability_note=artifact.availability_note,
            byte_hash=artifact.byte_hash,
            semantic_hash=artifact.semantic_hash,
            storage_ref=artifact.storage_ref,
            size_bytes=artifact.size_bytes,
            content=artifact.content,
            is_sample=artifact.is_sample,
            created_at=artifact.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return artifact
    
    def get(self, artifact_id: ArtifactId) -> Artifact | None:
        """Get artifact metadata by ID."""
        stmt = select(ArtifactModel).where(ArtifactModel.id == str(artifact_id))
        model = self.session.execute(stmt).scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_domain(model)
    
    def _to_domain(self, model: ArtifactModel) -> Artifact:
        """Convert ORM model to domain model."""
        from winston.domain import ArtifactType
        
        return Artifact(
            id=ArtifactId(model.id),
            execution_id=ExecutionId(model.execution_id),
            artifact_type=ArtifactType(model.artifact_type),
            schema_id=model.schema_id,
            schema_version=model.schema_version,
            is_available=model.is_available,
            availability_note=model.availability_note,
            byte_hash=model.byte_hash,
            semantic_hash=model.semantic_hash,
            storage_ref=model.storage_ref,
            size_bytes=model.size_bytes,
            content=model.content,
            is_sample=model.is_sample,
            created_at=model.created_at,
        )
