"""Token counting and prompt packaging for context budgets.

Phase 1: replace ad-hoc ``len // 4`` estimates with a pluggable
``TokenCounter``. ``tiktoken`` is preferred when installed; otherwise a
documented character approximation is used so offline/CI stays zero-dep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class TokenCounter(Protocol):
    """Protocol for counting tokens in text."""

    @property
    def name(self) -> str:
        """Stable identifier for the tokenizer (recorded on manifests)."""
        ...

    def count(self, text: str) -> int:
        """Return token count for ``text``."""
        ...


class CharApproxCounter:
    """Character-based approximation: ``max(0, len(text) // 4)``.

    Matches the historical Winston heuristic so budgets stay comparable
    when tiktoken is unavailable.
    """

    @property
    def name(self) -> str:
        return "char_approx_div4"

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(text) // 4


class TiktokenCounter:
    """Count tokens with OpenAI ``tiktoken`` encodings.

    Default encoding ``cl100k_base`` covers GPT-4 / GPT-3.5-turbo families.
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        try:
            import tiktoken
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "tiktoken is required for TiktokenCounter; "
                "install with: pip install winston[eval]"
            ) from exc
        self._encoding_name = encoding_name
        self._encoding = tiktoken.get_encoding(encoding_name)

    @property
    def name(self) -> str:
        return f"tiktoken:{self._encoding_name}"

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text))


def get_default_counter() -> TokenCounter:
    """Return the best available counter (tiktoken if importable)."""
    try:
        return TiktokenCounter()
    except ImportError:
        return CharApproxCounter()


@dataclass
class PromptPackage:
    """Serializable model-visible prompt plus token accounting.

    ``prompt_text`` is the canonical string used for recounting; baselines
    that paste raw logs should use the same counter on their pasted text.
    """

    prompt_text: str
    token_count: int
    tokenizer_name: str
    case_id: Optional[str] = None
    investigation_id: Optional[str] = None
    manifest_id: Optional[str] = None
    item_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return {
            "case_id": self.case_id,
            "investigation_id": self.investigation_id,
            "manifest_id": self.manifest_id,
            "tokenizer_name": self.tokenizer_name,
            "token_count": self.token_count,
            "item_count": self.item_count,
            "prompt_text": self.prompt_text,
            "metadata": self.metadata,
        }


def render_context_prompt(
    items: List[Any],
    *,
    header: Optional[str] = None,
) -> str:
    """Render context items into a single prompt string.

    Each item is expected to expose ``item_type``, ``summary``, and optional
    ``content`` (dict). Used by ``ContextBuilder.export_prompt``.
    """
    lines: List[str] = []
    if header:
        lines.append(header)
        lines.append("")

    for item in items:
        item_type = getattr(item, "item_type", "item")
        summary = getattr(item, "summary", "")
        content = getattr(item, "content", None)
        reason = getattr(item, "selection_reason", "")

        lines.append(f"### [{item_type}] {summary}")
        if reason:
            lines.append(f"Reason: {reason}")
        if content is not None:
            lines.append(_format_content(content))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_content(content: Any) -> str:
    if isinstance(content, dict):
        parts = []
        for key, value in content.items():
            parts.append(f"{key}: {value}")
        return "\n".join(parts)
    return str(content)
