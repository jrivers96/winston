"""Execution and artifact domain models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from winston.domain.enums import ArtifactType, ExecutionStatus
from winston.domain.identities import (
    ArtifactId,
    BusinessDate,
    ExecutionId,
    IndexId,
    ManifestId,
    RepositoryId,
    RevisionId,
)


class Execution(BaseModel):
    """An immutable record of a calculation execution.
    
    Separates logical calculation identity from execution identity.
    """
    
    # Execution identity
    id: ExecutionId = Field(..., description="Immutable execution ID")
    attempt_id: Optional[str] = Field(None, description="Attempt/repair identifier")
    
    # Logical calculation identity
    index_id: IndexId = Field(..., description="Index being calculated")
    environment: str = Field(..., description="Environment (prod/uat/synthetic)")
    business_date: BusinessDate = Field(..., description="Business date being calculated")
    stage: Optional[str] = Field(None, description="Calculation stage if multi-stage")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Execution start time (UTC)")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time (UTC)")
    
    # Status
    status: ExecutionStatus = Field(..., description="Execution status")
    status_message: Optional[str] = Field(None, description="Status details or error message")
    
    # Manifests
    input_manifest_id: Optional[ManifestId] = Field(None, description="Input manifest reference")
    code_manifest_id: Optional[ManifestId] = Field(None, description="Code version manifest reference")
    
    # Outputs
    state_artifact_id: Optional[ArtifactId] = Field(None, description="Produced state artifact")
    output_artifact_id: Optional[ArtifactId] = Field(None, description="Produced output artifact")
    
    # Validation
    validation_status: Optional[str] = Field(None, description="Independent validation status")
    validation_time: Optional[datetime] = Field(None, description="When validated")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class InputManifest(BaseModel):
    """Manifest of actual consumed inputs for an execution."""
    
    id: ManifestId = Field(..., description="Manifest identifier")
    execution_id: ExecutionId = Field(..., description="Parent execution")
    
    # Parent state references
    parent_state_refs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="References to consumed parent state artifacts",
    )
    
    # Input dataset references
    input_dataset_refs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="References to consumed input datasets with versions",
    )
    
    # Configuration
    configuration_ref: Optional[str] = Field(None, description="Configuration version reference")
    
    # Version vector for multi-table inputs
    version_vector: Dict[str, str] = Field(
        default_factory=dict,
        description="Version vector for inputs from multiple tables",
    )
    
    # Completeness
    is_complete: bool = Field(True, description="Whether manifest is complete")
    missing_refs: List[str] = Field(
        default_factory=list, description="References that could not be resolved"
    )
    
    # Timestamps
    created_at: datetime = Field(..., description="When manifest was created")


class CodeManifest(BaseModel):
    """Manifest of code/configuration versions for an execution.
    
    Attached to executions to record exactly what code ran.
    """
    
    id: ManifestId = Field(..., description="Manifest identifier")
    execution_id: Optional[ExecutionId] = Field(None, description="Parent execution if applicable")
    
    # Execution environment
    execution_environment: Optional[str] = Field(
        None, description="Runtime environment description"
    )
    task_identity: Optional[str] = Field(None, description="Task/worker identity")
    observation_interval_start: Optional[datetime] = Field(None)
    observation_interval_end: Optional[datetime] = Field(None)
    
    # Runtime artifact
    runtime_artifact_id: Optional[str] = Field(None, description="Artifact identity (container, wheel)")
    runtime_artifact_digest: Optional[str] = Field(None, description="Artifact digest")
    build_ref: Optional[str] = Field(None, description="Build/deployment reference")
    
    # Source repositories
    repository_refs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Repository IDs, commits, and scoped paths",
    )
    
    # Packages
    package_versions: Dict[str, str] = Field(
        default_factory=dict, description="Resolved package versions"
    )
    package_digests: Dict[str, str] = Field(
        default_factory=dict, description="Package digests where available"
    )
    
    # Configuration and methodology
    configuration_revision: Optional[str] = Field(None, description="Configuration revision")
    methodology_revision: Optional[str] = Field(None, description="Methodology/formula revision")
    schema_revision: Optional[str] = Field(None, description="Schema revision")
    
    # Provenance
    provenance_authority: Optional[str] = Field(
        None, description="Source of provenance (build system, runtime observation)"
    )
    observation_time: Optional[datetime] = Field(None, description="When observed")
    is_complete: bool = Field(False, description="Whether manifest is complete")
    unresolved_mappings: List[str] = Field(
        default_factory=list, description="Mappings that could not be resolved"
    )
    
    # Timestamps
    created_at: datetime = Field(..., description="When manifest was created")


class Artifact(BaseModel):
    """A produced state or output artifact."""
    
    id: ArtifactId = Field(..., description="Artifact identifier")
    execution_id: ExecutionId = Field(..., description="Producing execution")
    artifact_type: ArtifactType = Field(..., description="Type of artifact")
    
    # Schema
    schema_id: Optional[str] = Field(None, description="Schema identifier")
    schema_version: Optional[str] = Field(None, description="Schema version")
    
    # Availability
    is_available: bool = Field(True, description="Whether artifact data is available")
    availability_note: Optional[str] = Field(None, description="Note if not available")
    
    # Integrity
    byte_hash: Optional[str] = Field(None, description="Byte-level integrity hash")
    semantic_hash: Optional[str] = Field(None, description="Canonical semantic hash")
    
    # Storage
    storage_ref: Optional[str] = Field(None, description="Storage reference/path")
    size_bytes: Optional[int] = Field(None, description="Size in bytes")
    
    # Content (for small artifacts like state)
    content: Optional[Dict[str, Any]] = Field(None, description="Artifact content if inline")
    
    # Sample flag
    is_sample: bool = Field(False, description="Whether this is sampled data")
    
    # Timestamps
    created_at: datetime = Field(..., description="When artifact was created")


class SelectedRevision(BaseModel):
    """Record of which execution revision is currently selected.
    
    A newer run is not automatically the selected revision. Selection
    follows an explicit policy.
    """
    
    index_id: IndexId = Field(..., description="Index")
    environment: str = Field(..., description="Environment")
    business_date: BusinessDate = Field(..., description="Business date")
    
    # Selection
    selected_execution_id: ExecutionId = Field(..., description="Currently selected execution")
    selection_policy: str = Field(..., description="Policy that determined selection")
    selection_reason: Optional[str] = Field(None, description="Reason for selection")
    
    # History
    previous_execution_id: Optional[ExecutionId] = Field(
        None, description="Previously selected execution"
    )
    
    # Timestamps
    selected_at: datetime = Field(..., description="When selection was made")
    
    # Publication status (separate from execution success)
    is_published: bool = Field(False, description="Whether this revision is published")
    published_at: Optional[datetime] = Field(None, description="When published")
