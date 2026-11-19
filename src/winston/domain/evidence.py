"""Evidence envelopes and collection receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from winston.domain.enums import CompletionStatus
from winston.domain.identities import ArtifactId


class CollectionReceipt(BaseModel):
    """Receipt documenting a source collection operation.
    
    Every source result must include this common envelope.
    """
    
    # Source identification
    source_type: str = Field(..., description="Type of source (databricks, datadog, git, etc)")
    source_scope: str = Field(..., description="Authenticated scope without credentials")
    
    # Request identification
    local_request_id: str = Field(..., description="Local unique request identifier")
    external_statement_id: Optional[str] = Field(
        None, description="External statement/run ID if supported"
    )
    
    # Query details
    query_template_id: Optional[str] = Field(None, description="Template ID if using templates")
    query_template_revision: Optional[str] = Field(None, description="Template revision")
    parameters_ref: Optional[str] = Field(
        None, description="Reference to protected parameters (not inline)"
    )
    
    # Time bounds
    requested_time_start: Optional[datetime] = Field(None, description="Requested start time")
    requested_time_end: Optional[datetime] = Field(None, description="Requested end time")
    actual_time_start: Optional[datetime] = Field(None, description="Actual returned start time")
    actual_time_end: Optional[datetime] = Field(None, description="Actual returned end time")
    business_date_scope: Optional[List[str]] = Field(None, description="Business dates covered")
    
    # Collection metadata
    collection_started_at: datetime = Field(..., description="When collection started")
    collection_completed_at: datetime = Field(..., description="When collection completed")
    
    # Units and aggregation
    units: Optional[str] = Field(None, description="Units of returned values")
    aggregation: Optional[str] = Field(None, description="Aggregation/rollup applied")
    
    # Status
    status: CompletionStatus = Field(..., description="Collection completion status")
    truncated: bool = Field(False, description="Whether results were truncated")
    continuation_token: Optional[str] = Field(None, description="Token for continuation if truncated")
    warnings: List[str] = Field(default_factory=list, description="Collection warnings")
    
    # Evidence reference
    evidence_artifact_id: Optional[ArtifactId] = Field(
        None, description="Reference to stored evidence artifact"
    )


class EvidenceEnvelope(BaseModel):
    """Wrapper for evidence with provenance metadata."""
    
    artifact_id: ArtifactId = Field(..., description="Unique artifact identifier")
    artifact_type: str = Field(..., description="Type of evidence")
    
    # Content
    content_hash: str = Field(..., description="SHA-256 hash of content")
    content_size_bytes: int = Field(..., description="Size of content in bytes")
    storage_path: str = Field(..., description="Relative path in artifact storage")
    
    # Provenance
    source_type: str = Field(..., description="Source that produced this evidence")
    collection_receipt_id: Optional[str] = Field(
        None, description="Reference to collection receipt"
    )
    
    # Timestamps
    created_at: datetime = Field(..., description="When artifact was created")
    
    # Validity
    valid_from: Optional[datetime] = Field(None, description="Start of validity period")
    valid_until: Optional[datetime] = Field(None, description="End of validity period")
    superseded_by: Optional[ArtifactId] = Field(
        None, description="Artifact that supersedes this one"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
