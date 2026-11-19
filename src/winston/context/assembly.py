"""Context assembly for investigations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


@dataclass
class ContextItem:
    """A single item in an assembled context."""
    
    # Identification
    item_id: str
    item_type: str  # issue, execution, evidence, source_excerpt, etc.
    
    # Content
    summary: str
    content: Optional[Dict[str, Any]] = None
    
    # Source
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    
    # For source excerpts
    repository_id: Optional[str] = None
    commit: Optional[str] = None
    path: Optional[str] = None
    
    # Validity
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    # Selection metadata
    selection_reason: str = ""
    relevance_score: float = 0.0
    
    # Tokens estimate (for context budget)
    estimated_tokens: int = 0


@dataclass
class ContextManifest:
    """Manifest of assembled context with provenance."""
    
    # Identification
    manifest_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Scope
    investigation_id: Optional[str] = None
    index_id: Optional[str] = None
    business_date: Optional[str] = None
    scenario: Optional[str] = None
    
    # Items
    items: List[ContextItem] = field(default_factory=list)
    
    # Selection metadata
    total_items_considered: int = 0
    items_included: int = 0
    items_excluded: int = 0
    
    # Budgets
    token_budget: int = 0
    tokens_used: int = 0
    
    # Gaps and exclusions
    exclusion_reasons: List[str] = field(default_factory=list)
    source_gaps: List[str] = field(default_factory=list)
    lineage_gaps: List[str] = field(default_factory=list)
    
    # Builder info
    builder_version: str = "1.0.0"
    policy_version: str = "1.0.0"
    
    def add_item(self, item: ContextItem) -> None:
        """Add an item to the manifest."""
        self.items.append(item)
        self.items_included += 1
        self.tokens_used += item.estimated_tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "manifest_id": self.manifest_id,
            "created_at": self.created_at.isoformat(),
            "investigation_id": self.investigation_id,
            "index_id": self.index_id,
            "business_date": self.business_date,
            "scenario": self.scenario,
            "items": [
                {
                    "item_id": i.item_id,
                    "item_type": i.item_type,
                    "summary": i.summary,
                    "source_type": i.source_type,
                    "source_ref": i.source_ref,
                    "selection_reason": i.selection_reason,
                }
                for i in self.items
            ],
            "total_items_considered": self.total_items_considered,
            "items_included": self.items_included,
            "items_excluded": self.items_excluded,
            "token_budget": self.token_budget,
            "tokens_used": self.tokens_used,
            "source_gaps": self.source_gaps,
            "lineage_gaps": self.lineage_gaps,
        }


class ContextBuilder:
    """Builder for assembling investigation context.
    
    Assembles context from:
    - Open issues and obligations
    - Relevant executions and their chain
    - Evidence artifacts
    - Source code excerpts (at pinned revisions)
    - Previous investigation findings
    """
    
    def __init__(
        self,
        token_budget: int = 100000,
        max_items: int = 50,
    ):
        """Initialize builder.
        
        Args:
            token_budget: Maximum tokens for assembled context
            max_items: Maximum number of items to include
        """
        self.token_budget = token_budget
        self.max_items = max_items
        self._items: List[ContextItem] = []
        self._considered: int = 0
    
    def add_issue(
        self,
        issue_id: str,
        title: str,
        description: str,
        state: str,
        **kwargs: Any,
    ) -> None:
        """Add an issue to context."""
        self._considered += 1
        
        summary = f"Issue [{state}]: {title}"
        content = {
            "issue_id": issue_id,
            "title": title,
            "description": description,
            "state": state,
            **kwargs,
        }
        
        self._items.append(ContextItem(
            item_id=f"issue:{issue_id}",
            item_type="issue",
            summary=summary,
            content=content,
            selection_reason="Open issue in scope",
            estimated_tokens=len(description) // 4,  # Rough estimate
        ))
    
    def add_execution(
        self,
        execution_id: str,
        index_id: str,
        business_date: str,
        status: str,
        state_content: Optional[Dict] = None,
        **kwargs: Any,
    ) -> None:
        """Add an execution to context."""
        self._considered += 1
        
        summary = f"Execution {index_id}/{business_date}: {status}"
        content = {
            "execution_id": execution_id,
            "index_id": index_id,
            "business_date": business_date,
            "status": status,
            "state": state_content,
            **kwargs,
        }
        
        self._items.append(ContextItem(
            item_id=f"exec:{execution_id}",
            item_type="execution",
            summary=summary,
            content=content,
            selection_reason="In investigation chain",
            estimated_tokens=50 + (len(str(state_content)) // 4 if state_content else 0),
        ))
    
    def add_source_excerpt(
        self,
        repository_id: str,
        commit: str,
        path: str,
        excerpt: str,
        **kwargs: Any,
    ) -> None:
        """Add a source code excerpt to context."""
        self._considered += 1
        
        summary = f"Source: {repository_id}:{path}@{commit[:8]}"
        
        self._items.append(ContextItem(
            item_id=f"source:{repository_id}:{commit[:8]}:{path}",
            item_type="source_excerpt",
            summary=summary,
            content={"excerpt": excerpt, **kwargs},
            repository_id=repository_id,
            commit=commit,
            path=path,
            selection_reason="Relevant source code",
            estimated_tokens=len(excerpt) // 4,
        ))
    
    def add_evidence(
        self,
        artifact_id: str,
        artifact_type: str,
        summary: str,
        content: Optional[Dict] = None,
        **kwargs: Any,
    ) -> None:
        """Add evidence to context."""
        self._considered += 1
        
        self._items.append(ContextItem(
            item_id=f"evidence:{artifact_id}",
            item_type="evidence",
            summary=summary,
            content=content,
            source_type=artifact_type,
            source_ref=artifact_id,
            selection_reason="Supporting evidence",
            estimated_tokens=50 + (len(str(content)) // 4 if content else 0),
        ))
    
    def build(
        self,
        investigation_id: Optional[str] = None,
        index_id: Optional[str] = None,
        business_date: Optional[str] = None,
        scenario: Optional[str] = None,
    ) -> ContextManifest:
        """Build the context manifest.
        
        Applies budget constraints and creates the manifest.
        """
        from uuid import uuid4
        
        manifest = ContextManifest(
            manifest_id=f"ctx_{uuid4().hex[:12]}",
            investigation_id=investigation_id,
            index_id=index_id,
            business_date=business_date,
            scenario=scenario,
            token_budget=self.token_budget,
            total_items_considered=self._considered,
        )
        
        # Sort by relevance and apply budget
        sorted_items = sorted(
            self._items,
            key=lambda x: x.relevance_score,
            reverse=True,
        )
        
        tokens_remaining = self.token_budget
        
        for item in sorted_items:
            if manifest.items_included >= self.max_items:
                manifest.exclusion_reasons.append("Max items reached")
                break
            
            if item.estimated_tokens > tokens_remaining:
                manifest.exclusion_reasons.append(
                    f"Token budget exhausted for {item.item_id}"
                )
                manifest.items_excluded += 1
                continue
            
            manifest.add_item(item)
            tokens_remaining -= item.estimated_tokens
        
        manifest.items_excluded = self._considered - manifest.items_included
        
        return manifest
    
    def explain(self, manifest: ContextManifest) -> str:
        """Generate explanation of context assembly.
        
        Args:
            manifest: The manifest to explain
            
        Returns:
            Human-readable explanation
        """
        lines = [
            f"Context Manifest: {manifest.manifest_id}",
            f"Created: {manifest.created_at.isoformat()}",
            "",
            f"Scope:",
            f"  Investigation: {manifest.investigation_id or 'N/A'}",
            f"  Index: {manifest.index_id or 'N/A'}",
            f"  Date: {manifest.business_date or 'N/A'}",
            f"  Scenario: {manifest.scenario or 'N/A'}",
            "",
            f"Budget:",
            f"  Token budget: {manifest.token_budget}",
            f"  Tokens used: {manifest.tokens_used}",
            "",
            f"Items:",
            f"  Considered: {manifest.total_items_considered}",
            f"  Included: {manifest.items_included}",
            f"  Excluded: {manifest.items_excluded}",
            "",
            "Included Items:",
        ]
        
        for item in manifest.items:
            lines.append(f"  - [{item.item_type}] {item.summary}")
            lines.append(f"    Reason: {item.selection_reason}")
        
        if manifest.source_gaps:
            lines.append("")
            lines.append("Source Gaps:")
            for gap in manifest.source_gaps:
                lines.append(f"  - {gap}")
        
        if manifest.lineage_gaps:
            lines.append("")
            lines.append("Lineage Gaps:")
            for gap in manifest.lineage_gaps:
                lines.append(f"  - {gap}")
        
        return "\n".join(lines)
