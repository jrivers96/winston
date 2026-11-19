"""Repository and software dependency domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from winston.domain.enums import DependencyCategory, EvidenceCategory
from winston.domain.identities import ComponentId, RepositoryId


class Repository(BaseModel):
    """A registered repository that Winston can inspect."""
    
    id: RepositoryId = Field(..., description="Stable repository identifier")
    description: Optional[str] = Field(None, description="Repository description")
    
    # Location
    location_type: str = Field(..., description="Type: local_fixture, git_remote, etc")
    location_path: Optional[str] = Field(None, description="Local path if applicable")
    location_origin: Optional[str] = Field(None, description="Git remote origin if applicable")
    credential_provider: Optional[str] = Field(
        None, description="Credential provider reference (no secrets)"
    )
    
    # Metadata
    role: str = Field(..., description="Role: calculation, shared_library, config, etc")
    owner: Optional[str] = Field(None, description="Owner/team")
    languages: List[str] = Field(default_factory=list, description="Primary languages")
    
    # Access control
    allowed_paths: List[str] = Field(default_factory=list, description="Allowed path patterns")
    excluded_paths: List[str] = Field(default_factory=list, description="Excluded path patterns")
    access_scope: str = Field("read_only", description="Access scope")
    
    # Budgets
    retrieval_budget_mb: int = Field(10, description="Max MB to retrieve")
    cache_budget_mb: int = Field(100, description="Max MB to cache")
    
    # Exploration
    default_branch: str = Field("main", description="Default branch for exploration")
    
    # Registration
    registration_source: Optional[str] = Field(None, description="Source of registration")
    registry_revision: Optional[str] = Field(None, description="Registry revision that defined this")
    
    # Status
    sync_status: Optional[str] = Field(None, description="Last sync status")
    last_synced_at: Optional[datetime] = Field(None, description="When last synced")
    is_accessible: bool = Field(True, description="Whether currently accessible")
    
    # Timestamps
    created_at: datetime = Field(..., description="When registered")
    updated_at: datetime = Field(..., description="When last updated")


class ComponentMapping(BaseModel):
    """Mapping of a component to repository paths.
    
    Many-to-many: one monorepo can hold several components;
    one component can span several repositories.
    """
    
    component_id: ComponentId = Field(..., description="Component identifier")
    repository_id: RepositoryId = Field(..., description="Repository containing this mapping")
    
    # Paths
    paths: List[str] = Field(..., description="Paths within the repository")
    
    # Role
    role: str = Field(..., description="Role of this component")
    
    # Dependencies
    consumers: List[ComponentId] = Field(
        default_factory=list, description="Components that consume this one"
    )
    
    # Version tracking
    effective_from_commit: Optional[str] = Field(None, description="Commit where mapping became valid")
    effective_until_commit: Optional[str] = Field(None, description="Commit where mapping ended")
    
    # Profile reference
    profile_path: Optional[str] = Field(None, description="Path to component profile if any")
    
    # Timestamps
    created_at: datetime = Field(..., description="When mapping was created")
    updated_at: datetime = Field(..., description="When mapping was last updated")


class SoftwareDependency(BaseModel):
    """An edge in the software dependency graph.
    
    Software relationships are separate from calculation-consumption edges.
    Cycles are allowed in the software graph.
    """
    
    # Source and target
    source_component_id: ComponentId = Field(..., description="Depending component")
    target_component_id: ComponentId = Field(..., description="Dependency component")
    
    # Category
    category: DependencyCategory = Field(..., description="Type of dependency")
    
    # Version applicability
    source_version_start: Optional[str] = Field(None, description="Source version where edge starts")
    source_version_end: Optional[str] = Field(None, description="Source version where edge ends")
    target_version_constraint: Optional[str] = Field(None, description="Constraint on target version")
    
    # Evidence
    evidence_category: EvidenceCategory = Field(
        ..., description="How this edge was determined"
    )
    evidence_ref: Optional[str] = Field(None, description="Reference to supporting evidence")
    
    # Metadata
    is_optional: bool = Field(False, description="Whether dependency is optional")
    scope: Optional[str] = Field(None, description="Scope (runtime, build, dev, test)")
    
    # Timestamps
    observed_at: datetime = Field(..., description="When dependency was observed")
    
    # Additional context
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
