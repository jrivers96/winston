"""Investigation case contracts for token-efficiency evaluation (Phase 0).

Shared incident definitions used by the Winston arm and by BIT / VS Code
baseline exports. Cases are YAML under ``winston/evaluation/cases/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

CASES_DIR = Path(__file__).resolve().parent / "cases"


class GroundTruth(BaseModel):
    """Expected investigation outcome for deterministic scoring."""

    root_cause: str = Field(..., description="Canonical root-cause label")
    affected_dates: List[str] = Field(
        default_factory=list,
        description="Business-date labels that must be identified as impacted",
    )
    affected_indices: List[str] = Field(
        default_factory=list,
        description="Index IDs that must appear in the finding",
    )
    excluded_indices: List[str] = Field(
        default_factory=list,
        description="Index IDs that must NOT appear as impacted",
    )
    level_changes: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Optional expected level map: index -> date -> level",
    )
    notes: Optional[str] = None


class QualityRubric(BaseModel):
    """Weights for checklist scoring against ground truth."""

    root_cause_weight: float = 0.4
    affected_dates_weight: float = 0.3
    affected_indices_weight: float = 0.2
    exclusions_weight: float = 0.1

    def normalized(self) -> "QualityRubric":
        """Return a copy with weights summing to 1.0 (if total > 0)."""
        total = (
            self.root_cause_weight
            + self.affected_dates_weight
            + self.affected_indices_weight
            + self.exclusions_weight
        )
        if total <= 0:
            return self
        return QualityRubric(
            root_cause_weight=self.root_cause_weight / total,
            affected_dates_weight=self.affected_dates_weight / total,
            affected_indices_weight=self.affected_indices_weight / total,
            exclusions_weight=self.exclusions_weight / total,
        )


class BaselinePromptSpec(BaseModel):
    """How humans should paste the same incident into BIT / VS Code."""

    question: str
    arms: List[str] = Field(default_factory=lambda: ["bit", "vscode"])
    include_raw_log_bundle: bool = True
    instructions: str = (
        "Paste the entire frozen log bundle and answer the question. "
        "Do not trim the bundle. Record provider input_tokens when available; "
        "otherwise recount the pasted text with Winston's TokenCounter."
    )


class DatadogCaseFixture(BaseModel):
    """Scoped Datadog-shaped fixture attached to a case."""

    window_start: Optional[str] = None
    window_end: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    raw_log_lines: List[str] = Field(
        default_factory=list,
        description="Frozen lines for baseline paste (noise + signal)",
    )


class InvestigationCase(BaseModel):
    """One shared incident for Winston vs baseline comparison."""

    case_id: str
    title: str
    description: str = ""
    scenario: str = Field(
        "corrected",
        description="Synthetic scenario key (original, corrected, ...)",
    )
    index_id: str = "DEMO"
    business_date: str = "D3"
    question: str
    ground_truth: GroundTruth
    rubric: QualityRubric = Field(default_factory=QualityRubric)
    baseline: BaselinePromptSpec
    datadog: DatadogCaseFixture = Field(default_factory=DatadogCaseFixture)
    token_budget_default: int = 8000
    tags: List[str] = Field(default_factory=list)

    def baseline_bundle_text(self) -> str:
        """Frozen text a human pastes into BIT / VS Code."""
        lines = [
            f"# Baseline bundle: {self.case_id}",
            f"# Question: {self.question}",
            "",
            self.baseline.instructions,
            "",
            "## Raw logs",
        ]
        if self.datadog.raw_log_lines:
            lines.extend(self.datadog.raw_log_lines)
        else:
            lines.append("(no raw_log_lines in case fixture)")
        lines.append("")
        lines.append("## Question")
        lines.append(self.question)
        return "\n".join(lines) + "\n"


def cases_directory() -> Path:
    """Return the packaged cases directory."""
    return CASES_DIR


def list_case_ids(cases_dir: Optional[Path] = None) -> List[str]:
    """List case IDs from YAML filenames (stem)."""
    directory = cases_dir or CASES_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def load_case(case_id: str, cases_dir: Optional[Path] = None) -> InvestigationCase:
    """Load a single investigation case by id."""
    directory = cases_dir or CASES_DIR
    path = directory / f"{case_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown investigation case: {case_id} ({path})")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Case file must be a mapping: {path}")
    if "case_id" not in data:
        data["case_id"] = case_id
    if "baseline" not in data:
        data["baseline"] = {"question": data.get("question", "")}
    elif "question" not in data["baseline"]:
        data["baseline"]["question"] = data.get("question", "")
    return InvestigationCase.model_validate(data)


def load_all_cases(cases_dir: Optional[Path] = None) -> List[InvestigationCase]:
    """Load every YAML case in the cases directory."""
    return [load_case(case_id, cases_dir) for case_id in list_case_ids(cases_dir)]
