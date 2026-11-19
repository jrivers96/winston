"""SQLAlchemy ORM models for Winston."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    
    type_annotation_map = {
        Dict[str, Any]: JSONB,
    }


class IssueModel(Base):
    """SQLAlchemy model for issues."""
    
    __tablename__ = "issues"
    
    # Primary key (internal)
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Stable identifier
    id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Scope
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    index_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    environment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    affected_dates: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    
    # State
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="open", index=True)
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Impact
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    impact_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_executions: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    
    # Evidence
    evidence_refs: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    
    # Completion
    completion_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Recurrence
    previous_issue_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Fingerprint
    fingerprint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    
    # Custom metadata
    extra_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Version for optimistic locking
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Relationships
    obligations: Mapped[List["ObligationModel"]] = relationship(
        "ObligationModel", back_populates="issue", cascade="all, delete-orphan"
    )


class ObligationModel(Base):
    """SQLAlchemy model for obligations."""
    
    __tablename__ = "obligations"
    
    # Primary key
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Stable identifier
    id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Parent issue
    issue_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("issues.id"), nullable=False, index=True
    )
    
    # Action
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Ownership
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # State
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Wake conditions
    wake_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Progress
    progress_notes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Evidence
    evidence_refs: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Custom metadata
    extra_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Version for optimistic locking
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Relationships
    issue: Mapped["IssueModel"] = relationship("IssueModel", back_populates="obligations")


class ExecutionModel(Base):
    """SQLAlchemy model for executions."""
    
    __tablename__ = "executions"
    
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    attempt_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Logical calculation identity
    index_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    business_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Manifests
    input_manifest_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    code_manifest_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Outputs
    state_artifact_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    output_artifact_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Validation
    validation_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    validation_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Custom metadata
    extra_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint(
            "index_id", "environment", "business_date", "attempt_id",
            name="uq_execution_identity"
        ),
    )


class ArtifactModel(Base):
    """SQLAlchemy model for artifacts."""
    
    __tablename__ = "artifacts"
    
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Schema
    schema_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    schema_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    availability_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Integrity
    byte_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    semantic_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Storage
    storage_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Content (for small inline artifacts)
    content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Sample flag
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RepositoryModel(Base):
    """SQLAlchemy model for repository registry entries."""
    
    __tablename__ = "repositories"
    
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Location
    location_type: Mapped[str] = mapped_column(String(50), nullable=False)
    location_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location_origin: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    credential_provider: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Metadata
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    languages: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    
    # Access control
    allowed_paths: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    excluded_paths: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    access_scope: Mapped[str] = mapped_column(String(50), default="read_only")
    
    # Budgets
    retrieval_budget_mb: Mapped[int] = mapped_column(Integer, default=10)
    cache_budget_mb: Mapped[int] = mapped_column(Integer, default=100)
    
    # Exploration
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    
    # Registration
    registration_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    registry_revision: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status
    sync_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEventModel(Base):
    """SQLAlchemy model for audit events."""
    
    __tablename__ = "audit_events"
    
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Event identification
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Actor
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Details
    old_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Timestamp
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class CollectionReceiptModel(Base):
    """SQLAlchemy model for collection receipts."""
    
    __tablename__ = "collection_receipts"
    
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Source
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_scope: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Request
    external_statement_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    query_template_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Time bounds
    requested_time_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    requested_time_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_time_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_time_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Collection
    collection_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collection_completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    warnings: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=list)
    
    # Evidence
    evidence_artifact_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
