"""Trust, freshness, and SLA checks for Supercalc-shaped products."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from winston.checks.base import Check, CheckResult, CheckSeverity, CheckStatus
from winston.lineage.graph import DependencyGraph
from winston.lineage.traversal import find_impact


class FreshnessSLACheck(Check):
    """Fail when expected calculation sessions are missing (not healthy)."""

    @property
    def check_id(self) -> str:
        return "freshness_sla"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Missing/stale expected sessions must not be treated as healthy"

    def run(self, context: Dict[str, Any]) -> CheckResult:
        graph: Optional[DependencyGraph] = context.get("graph")
        index_id: Optional[str] = context.get("index_id")
        expected_sessions: Optional[List[str]] = context.get("expected_sessions")

        if graph is None or index_id is None or expected_sessions is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Missing required context: graph, index_id, expected_sessions",
                severity=CheckSeverity.WARNING,
            )

        present = {n.business_date for n in graph.get_all_by_index(index_id)}
        missing = sorted(set(expected_sessions) - present)

        if missing:
            return self._create_result(
                CheckStatus.FAIL,
                f"Freshness/SLA gap: missing sessions {missing}",
                index_id=index_id,
                expected=str(sorted(expected_sessions)),
                observed=str(sorted(present)),
                severity=CheckSeverity.ERROR,
                metadata={"missing_sessions": missing},
            )

        return self._create_result(
            CheckStatus.PASS,
            f"All expected sessions present for {index_id}",
            index_id=index_id,
            observed=str(sorted(present)),
        )


class StaleWindowCheck(Check):
    """Fail/unknown when observation age exceeds configured SLA hours."""

    @property
    def check_id(self) -> str:
        return "stale_window"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Observation windows older than SLA are not healthy"

    def run(self, context: Dict[str, Any]) -> CheckResult:
        observed_at = context.get("observed_at")
        sla_hours = float(context.get("sla_hours", 24))
        now = context.get("now") or datetime.now(timezone.utc)

        if observed_at is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "No observation timestamp available — cannot claim freshness",
                severity=CheckSeverity.WARNING,
            )

        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if isinstance(now, str):
            now = datetime.fromisoformat(now.replace("Z", "+00:00"))

        age_hours = (now - observed_at).total_seconds() / 3600.0
        if age_hours > sla_hours:
            return self._create_result(
                CheckStatus.FAIL,
                f"Stale window: age {age_hours:.1f}h exceeds SLA {sla_hours}h",
                expected=f"<= {sla_hours}h",
                observed=f"{age_hours:.1f}h",
                severity=CheckSeverity.ERROR,
                metadata={"age_hours": age_hours, "sla_hours": sla_hours},
            )

        return self._create_result(
            CheckStatus.PASS,
            f"Observation age {age_hours:.1f}h within SLA {sla_hours}h",
            observed=f"{age_hours:.1f}h",
        )


class CoverageGapCheck(Check):
    """Fail when declared coverage is below a minimum threshold."""

    @property
    def check_id(self) -> str:
        return "coverage_gap"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Universe coverage below threshold is an explicit gap, not healthy"

    def run(self, context: Dict[str, Any]) -> CheckResult:
        covered = context.get("covered_count")
        universe = context.get("universe_count")
        min_ratio = float(context.get("min_coverage_ratio", 0.0))

        if covered is None or universe is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Coverage counts unavailable — cannot claim healthy coverage",
                severity=CheckSeverity.WARNING,
            )

        if universe <= 0:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Universe count is zero — coverage undefined",
                severity=CheckSeverity.WARNING,
            )

        ratio = float(covered) / float(universe)
        if ratio < min_ratio:
            return self._create_result(
                CheckStatus.FAIL,
                f"Coverage gap: {ratio:.2%} below minimum {min_ratio:.2%}",
                expected=f">= {min_ratio:.2%}",
                observed=f"{ratio:.2%} ({covered}/{universe})",
                severity=CheckSeverity.ERROR,
                metadata={"coverage_ratio": ratio},
            )

        return self._create_result(
            CheckStatus.PASS,
            f"Coverage {ratio:.2%} meets minimum {min_ratio:.2%}",
            observed=f"{ratio:.2%} ({covered}/{universe})",
        )


class UnrelatedExclusionCheck(Check):
    """Fail if an unrelated index leaks into an impact closure."""

    @property
    def check_id(self) -> str:
        return "unrelated_exclusion"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Unrelated trust/status series must stay out of impact closure"

    def run(self, context: Dict[str, Any]) -> CheckResult:
        graph: Optional[DependencyGraph] = context.get("graph")
        origin_execution_id: Optional[str] = context.get("origin_execution_id")
        excluded_prefixes: Optional[List[str]] = context.get("excluded_prefixes")

        if graph is None or origin_execution_id is None or excluded_prefixes is None:
            return self._create_result(
                CheckStatus.UNKNOWN,
                "Missing required context for unrelated exclusion check",
                severity=CheckSeverity.WARNING,
            )

        impact = find_impact(graph, origin_execution_id)
        leaks = [
            eid
            for eid in impact.all_affected
            if any(eid.startswith(prefix) for prefix in excluded_prefixes)
        ]

        if leaks:
            return self._create_result(
                CheckStatus.FAIL,
                f"Unrelated indices leaked into impact: {leaks}",
                observed=str(leaks),
                severity=CheckSeverity.ERROR,
                metadata={"leaks": leaks},
            )

        return self._create_result(
            CheckStatus.PASS,
            "Unrelated indices excluded from impact closure",
            observed=str(sorted(impact.affected_indices)),
        )
