"""Context assembly for investigations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from winston.evaluation.tokens import PromptPackage, TokenCounter


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
    tokenizer_name: str = ""

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
                    "estimated_tokens": i.estimated_tokens,
                }
                for i in self.items
            ],
            "total_items_considered": self.total_items_considered,
            "items_included": self.items_included,
            "items_excluded": self.items_excluded,
            "token_budget": self.token_budget,
            "tokens_used": self.tokens_used,
            "tokenizer_name": self.tokenizer_name,
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
        token_counter: Optional["TokenCounter"] = None,
    ):
        """Initialize builder.

        Args:
            token_budget: Maximum tokens for assembled context
            max_items: Maximum number of items to include
            token_counter: Counter used for estimates and prompt export;
                defaults to ``get_default_counter()``
        """
        from winston.evaluation.tokens import get_default_counter

        self.token_budget = token_budget
        self.max_items = max_items
        self.token_counter: TokenCounter = token_counter or get_default_counter()
        self._items: List[ContextItem] = []
        self._considered: int = 0

    def _estimate_item_tokens(
        self,
        summary: str,
        content: Optional[Dict[str, Any]],
        selection_reason: str = "",
        overhead: int = 0,
    ) -> int:
        """Estimate tokens for one item as it would appear in the prompt."""
        from winston.evaluation.tokens import render_context_prompt

        stub = ContextItem(
            item_id="_estimate",
            item_type="estimate",
            summary=summary,
            content=content,
            selection_reason=selection_reason,
        )
        text = render_context_prompt([stub])
        return self.token_counter.count(text) + overhead

    def add_issue(
        self,
        issue_id: str,
        title: str,
        description: str,
        state: str,
        relevance_score: float = 0.0,
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
        reason = "Open issue in scope"

        self._items.append(
            ContextItem(
                item_id=f"issue:{issue_id}",
                item_type="issue",
                summary=summary,
                content=content,
                selection_reason=reason,
                relevance_score=relevance_score,
                estimated_tokens=self._estimate_item_tokens(summary, content, reason),
            )
        )

    def add_execution(
        self,
        execution_id: str,
        index_id: str,
        business_date: str,
        status: str,
        state_content: Optional[Dict] = None,
        relevance_score: float = 0.0,
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
        reason = "In investigation chain"

        self._items.append(
            ContextItem(
                item_id=f"exec:{execution_id}",
                item_type="execution",
                summary=summary,
                content=content,
                selection_reason=reason,
                relevance_score=relevance_score,
                estimated_tokens=self._estimate_item_tokens(summary, content, reason),
            )
        )

    def add_source_excerpt(
        self,
        repository_id: str,
        commit: str,
        path: str,
        excerpt: str,
        relevance_score: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """Add a source code excerpt to context."""
        self._considered += 1

        summary = f"Source: {repository_id}:{path}@{commit[:8]}"
        content = {"excerpt": excerpt, **kwargs}
        reason = "Relevant source code"

        self._items.append(
            ContextItem(
                item_id=f"source:{repository_id}:{commit[:8]}:{path}",
                item_type="source_excerpt",
                summary=summary,
                content=content,
                repository_id=repository_id,
                commit=commit,
                path=path,
                selection_reason=reason,
                relevance_score=relevance_score,
                estimated_tokens=self._estimate_item_tokens(summary, content, reason),
            )
        )

    def add_evidence(
        self,
        artifact_id: str,
        artifact_type: str,
        summary: str,
        content: Optional[Dict] = None,
        relevance_score: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """Add evidence to context."""
        self._considered += 1
        reason = "Supporting evidence"
        payload = content if content is not None else {}
        if kwargs:
            payload = {**payload, **kwargs}

        self._items.append(
            ContextItem(
                item_id=f"evidence:{artifact_id}",
                item_type="evidence",
                summary=summary,
                content=payload or None,
                source_type=artifact_type,
                source_ref=artifact_id,
                selection_reason=reason,
                relevance_score=relevance_score,
                estimated_tokens=self._estimate_item_tokens(
                    summary, payload or None, reason
                ),
            )
        )

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
            tokenizer_name=self.token_counter.name,
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

    def export_prompt(
        self,
        manifest: ContextManifest,
        *,
        case_id: Optional[str] = None,
        header: Optional[str] = None,
    ) -> "PromptPackage":
        """Export the model-visible prompt and recount tokens.

        The returned ``prompt_text`` is the canonical string for A/B recounts
        against BIT / VS Code pasted baselines.
        """
        from winston.evaluation.tokens import PromptPackage, render_context_prompt

        prompt_header = header or (
            f"Investigation context"
            f" (manifest={manifest.manifest_id}"
            f", tokenizer={self.token_counter.name})"
        )
        prompt_text = render_context_prompt(manifest.items, header=prompt_header)
        token_count = self.token_counter.count(prompt_text)

        return PromptPackage(
            prompt_text=prompt_text,
            token_count=token_count,
            tokenizer_name=self.token_counter.name,
            case_id=case_id,
            investigation_id=manifest.investigation_id,
            manifest_id=manifest.manifest_id,
            item_count=manifest.items_included,
            metadata={
                "token_budget": manifest.token_budget,
                "tokens_used_estimate": manifest.tokens_used,
                "items_excluded": manifest.items_excluded,
            },
        )

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
            "Scope:",
            f"  Investigation: {manifest.investigation_id or 'N/A'}",
            f"  Index: {manifest.index_id or 'N/A'}",
            f"  Date: {manifest.business_date or 'N/A'}",
            f"  Scenario: {manifest.scenario or 'N/A'}",
            "",
            "Budget:",
            f"  Token budget: {manifest.token_budget}",
            f"  Tokens used: {manifest.tokens_used}",
            f"  Tokenizer: {manifest.tokenizer_name or 'N/A'}",
            "",
            "Items:",
            f"  Considered: {manifest.total_items_considered}",
            f"  Included: {manifest.items_included}",
            f"  Excluded: {manifest.items_excluded}",
            "",
            "Included Items:",
        ]

        for item in manifest.items:
            lines.append(f"  - [{item.item_type}] {item.summary}")
            lines.append(f"    Reason: {item.selection_reason}")
            lines.append(f"    Tokens: {item.estimated_tokens}")

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
