"""Deterministic quality scoring against investigation ground truth (Phase 0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from winston.evaluation.cases import GroundTruth, InvestigationCase, QualityRubric


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _as_set(values: Optional[Iterable[str]]) -> Set[str]:
    if not values:
        return set()
    return {_normalize_label(v) for v in values if v is not None and str(v).strip()}


@dataclass
class QualityScore:
    """Checklist score for one investigation answer."""

    score: float
    root_cause_match: bool
    dates_recall: float
    indices_recall: float
    exclusions_ok: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "root_cause_match": self.root_cause_match,
            "dates_recall": self.dates_recall,
            "indices_recall": self.indices_recall,
            "exclusions_ok": self.exclusions_ok,
            "details": self.details,
        }


def _recall(expected: Set[str], actual: Set[str]) -> float:
    if not expected:
        return 1.0
    hits = len(expected & actual)
    return hits / len(expected)


def score_findings(
    ground_truth: GroundTruth,
    findings: Dict[str, Any],
    rubric: Optional[QualityRubric] = None,
) -> QualityScore:
    """Score a structured findings dict against ground truth.

    Expected ``findings`` keys (all optional but scored when present in GT):
    - ``root_cause``: str
    - ``affected_dates``: list[str]
    - ``affected_indices``: list[str]
    """
    weights = (rubric or QualityRubric()).normalized()

    expected_cause = _normalize_label(ground_truth.root_cause)
    actual_cause = _normalize_label(str(findings.get("root_cause", "")))
    root_cause_match = bool(actual_cause) and (
        actual_cause == expected_cause or expected_cause in actual_cause
    )

    expected_dates = _as_set(ground_truth.affected_dates)
    actual_dates = _as_set(findings.get("affected_dates") or [])
    dates_recall = _recall(expected_dates, actual_dates)

    expected_indices = _as_set(ground_truth.affected_indices)
    actual_indices = _as_set(findings.get("affected_indices") or [])
    indices_recall = _recall(expected_indices, actual_indices)

    excluded = _as_set(ground_truth.excluded_indices)
    exclusions_ok = excluded.isdisjoint(actual_indices)

    score = (
        weights.root_cause_weight * (1.0 if root_cause_match else 0.0)
        + weights.affected_dates_weight * dates_recall
        + weights.affected_indices_weight * indices_recall
        + weights.exclusions_weight * (1.0 if exclusions_ok else 0.0)
    )

    return QualityScore(
        score=round(score, 6),
        root_cause_match=root_cause_match,
        dates_recall=round(dates_recall, 6),
        indices_recall=round(indices_recall, 6),
        exclusions_ok=exclusions_ok,
        details={
            "expected_root_cause": ground_truth.root_cause,
            "actual_root_cause": findings.get("root_cause"),
            "missing_dates": sorted(expected_dates - actual_dates),
            "missing_indices": sorted(expected_indices - actual_indices),
            "forbidden_indices_present": sorted(excluded & actual_indices),
        },
    )


def score_case(case: InvestigationCase, findings: Dict[str, Any]) -> QualityScore:
    """Score findings for a loaded investigation case."""
    return score_findings(case.ground_truth, findings, case.rubric)
