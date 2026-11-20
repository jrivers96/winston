"""Maintenance loop: trust checks → issues/obligations."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from winston.checks.base import CheckResult, CheckStatus
from winston.checks.runner import CheckRunner
from winston.checks.trust import (
    CoverageGapCheck,
    FreshnessSLACheck,
    IntegrityStatusCheck,
    StaleWindowCheck,
    UnrelatedExclusionCheck,
)
from winston.domain import (
    Issue,
    IssueId,
    IssueState,
    Obligation,
    ObligationId,
    ObligationState,
)
from winston.evaluation.supercalc import (
    SUPERCALC_DATES,
    create_execution_id,
    create_supercalc_graph,
)
from winston.lineage.graph import DependencyGraph
from winston.maintenance.live_trust import (
    LIVE_PROFILES,
    build_live_trust_contexts_from_snapshot,
    fetch_live_trust_snapshot,
    load_live_maintain_gate,
    trust_config_from_profile,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(check_id: str, index_id: str, scope: str) -> str:
    raw = f"{check_id}|{index_id}|{scope}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_supercalc_trust_contexts(
    *,
    inject_missing_session: Optional[str] = None,
    covered_count: Optional[int] = 22,
    universe_count: Optional[int] = 100,
    min_coverage_ratio: float = 0.15,
    observed_at: Optional[datetime] = None,
    sla_hours: float = 24.0,
) -> Dict[str, Any]:
    """Build offline Supercalc-shaped graph + check contexts.

    Args:
        inject_missing_session: If set, drop that STRESS session to fail freshness
    """
    graph = create_supercalc_graph("original")

    if inject_missing_session:
        # Remove the STRESS node for the injected gap (and its edges via rebuild)
        drop_id = create_execution_id("STRESS", inject_missing_session, "original")
        nodes = {
            nid: node
            for nid, node in graph.nodes.items()
            if nid != drop_id
        }
        edges = [
            e
            for e in graph.edges
            if e.source_execution_id != drop_id and e.target_execution_id != drop_id
        ]
        rebuilt = DependencyGraph()
        for node in nodes.values():
            rebuilt.add_node(node)
        for edge in edges:
            rebuilt.add_edge(edge)
        graph = rebuilt

    origin = create_execution_id("STRESS", "S2", "original")
    # If S2 was removed, fall back to S1 origin when present
    if graph.get_node(origin) is None:
        origin = create_execution_id("STRESS", "S1", "original")

    return {
        "graph": graph,
        "index_id": "STRESS",
        "expected_sessions": list(SUPERCALC_DATES),
        "origin_execution_id": origin,
        "excluded_prefixes": ["TRUST_UNRELATED_"],
        "covered_count": covered_count,
        "universe_count": universe_count,
        "min_coverage_ratio": min_coverage_ratio,
        "observed_at": observed_at or _now(),
        "sla_hours": sla_hours,
        "now": _now(),
        # Synthetic path has no integrity snapshot — skip that check
        "integrity_failures": [],
    }


def run_trust_checks(context: Dict[str, Any]) -> List[CheckResult]:
    """Run the Phase E / live trust/SLA check suite."""
    runner = CheckRunner()
    runner.register_all(
        [
            FreshnessSLACheck(),
            StaleWindowCheck(),
            CoverageGapCheck(),
            UnrelatedExclusionCheck(),
            IntegrityStatusCheck(),
        ]
    )
    return runner.run_all(context).results


def results_to_issue_drafts(
    results: List[CheckResult],
    *,
    environment: str = "synthetic",
) -> List[Dict[str, Any]]:
    """Convert failing/unknown trust checks into issue+obligation drafts."""
    drafts: List[Dict[str, Any]] = []
    now = _now()

    for result in results:
        if result.status not in (CheckStatus.FAIL, CheckStatus.UNKNOWN):
            continue

        index_id = result.index_id or "STRESS"
        scope = (
            result.metadata.get("missing_sessions")
            or result.metadata.get("failure_names")
            or result.observed
            or result.message
        )
        fingerprint = _fingerprint(result.check_id, index_id, str(scope))
        issue_id = f"issue_{fingerprint[:12]}"
        obligation_id = f"obl_{fingerprint[:12]}"

        severity = "high" if result.status == CheckStatus.FAIL else "medium"
        title = f"Trust check failed: {result.check_id}"
        if result.status == CheckStatus.UNKNOWN:
            title = f"Trust check unknown: {result.check_id}"

        drafts.append(
            {
                "fingerprint": fingerprint,
                "issue": Issue(
                    id=IssueId(issue_id),
                    title=title,
                    description=result.message,
                    index_id=index_id,
                    environment=environment,
                    affected_dates=list(result.metadata.get("missing_sessions") or []),
                    state=IssueState.OPEN,
                    state_changed_at=now,
                    severity=severity,
                    impact_summary=result.message,
                    completion_criteria=(
                        "Re-run trust checks until status is pass; "
                        "unknown must not be forced to pass"
                    ),
                    created_at=now,
                    created_by="winston.maintain",
                    updated_at=now,
                    fingerprint=fingerprint,
                    metadata={
                        "check_id": result.check_id,
                        "check_status": result.status.value,
                        "check_version": result.check_version,
                    },
                ),
                "obligation": Obligation(
                    id=ObligationId(obligation_id),
                    issue_id=IssueId(issue_id),
                    title=f"Verify {result.check_id}",
                    description=(
                        f"Discriminating follow-up for {result.check_id}: {result.message}"
                    ),
                    action_type="verify",
                    state=ObligationState.PENDING,
                    state_changed_at=now,
                    wake_condition=f"check:{result.check_id}",
                    created_at=now,
                    updated_at=now,
                    metadata={"check_id": result.check_id},
                ),
            }
        )

    return drafts


def _persist_drafts(drafts: List[Dict[str, Any]]) -> Dict[str, Any]:
    persisted = {
        "enabled": True,
        "issues_created": 0,
        "issues_existing": 0,
        "obligations_created": 0,
    }
    if not drafts:
        return persisted

    from winston.storage.database import get_session
    from winston.storage.repositories import IssueRepository, ObligationRepository

    with get_session() as session:
        issue_repo = IssueRepository(session)
        obl_repo = ObligationRepository(session)

        for draft in drafts:
            existing = issue_repo.get_by_fingerprint(draft["fingerprint"])
            if existing is not None:
                persisted["issues_existing"] += 1
                continue
            issue_repo.create(draft["issue"])
            obl_repo.create(draft["obligation"])
            persisted["issues_created"] += 1
            persisted["obligations_created"] += 1

        session.commit()
    return persisted


def _report_from_results(
    *,
    profile: str,
    results: List[CheckResult],
    drafts: List[Dict[str, Any]],
    persist: bool,
    capability_label: str,
    environment: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    persisted = {
        "enabled": persist,
        "issues_created": 0,
        "issues_existing": 0,
        "obligations_created": 0,
    }
    if persist and drafts:
        persisted = _persist_drafts(drafts)

    report: Dict[str, Any] = {
        "profile": profile,
        "ran_at": _now().isoformat(),
        "capability_label": capability_label,
        "environment": environment,
        "checks": [r.to_dict() for r in results],
        "failed": sum(1 for r in results if r.status == CheckStatus.FAIL),
        "unknown": sum(1 for r in results if r.status == CheckStatus.UNKNOWN),
        "passed": sum(1 for r in results if r.status == CheckStatus.PASS),
        "drafts": [
            {
                "fingerprint": d["fingerprint"],
                "issue_id": str(d["issue"].id),
                "obligation_id": str(d["obligation"].id),
                "title": d["issue"].title,
                "severity": d["issue"].severity,
                "check_status": d["issue"].metadata.get("check_status"),
            }
            for d in drafts
        ],
        "persisted": persisted,
        "ok": all(
            r.status in (CheckStatus.PASS, CheckStatus.NOT_APPLICABLE)
            for r in results
        ),
    }
    if extra:
        report.update(extra)
    return report


def _maintain_live(
    *,
    profile: str,
    persist: bool,
    force: bool = False,
    live_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Live SoR → trust checks → same draft report shape as synthetic maintain."""
    environment = "production"

    if live_snapshot is not None:
        # Unit-test / injected path: skip network + contract gates.
        # Still require a trust_cfg; use defaults if profile file absent.
        from winston.config import get_settings
        from winston.sources.contracts import (
            load_profile_yaml,
            resolve_live_profile_path,
        )

        settings = get_settings()
        path, _notes = resolve_live_profile_path(profile, settings.profiles_dir)
        profile_data: Dict[str, Any] = {}
        if path is not None:
            profile_data = load_profile_yaml(path)
        trust_cfg = trust_config_from_profile(profile_data)
        context = build_live_trust_contexts_from_snapshot(live_snapshot, trust_cfg)
        # Tag integrity check with trust_status index when failures present
        if context.get("integrity_failures") is not None:
            # IntegrityStatusCheck uses index_id from context; use dedicated id
            integrity_ctx_index = trust_cfg["integrity_index_id"]
        else:
            integrity_ctx_index = trust_cfg["index_id"]
        # Run freshness/coverage against series index; integrity uses trust_status
        results = run_trust_checks(context)
        # Re-label integrity results onto integrity index for clearer drafts
        for result in results:
            if result.check_id == "integrity_status":
                result.index_id = integrity_ctx_index
        drafts = results_to_issue_drafts(results, environment=environment)
        return _report_from_results(
            profile=profile,
            results=results,
            drafts=drafts,
            persist=persist,
            capability_label="live-verified",
            environment=environment,
            extra={"source": "injected_snapshot"},
        )

    gate = load_live_maintain_gate(profile, force=force)
    if not gate.get("ready"):
        return {
            "profile": profile,
            "ran_at": _now().isoformat(),
            "capability_label": "live-template",
            "environment": environment,
            "checks": [],
            "failed": 0,
            "unknown": 0,
            "passed": 0,
            "drafts": [],
            "persisted": {
                "enabled": persist,
                "issues_created": 0,
                "issues_existing": 0,
                "obligations_created": 0,
            },
            "ok": False,
            "missing_configuration": gate.get("missing_configuration") or [],
            "warnings": gate.get("warnings") or [],
            "contract": gate.get("contract"),
        }

    profile_data = gate["profile_data"]
    trust_cfg = trust_config_from_profile(profile_data)
    try:
        snapshot = fetch_live_trust_snapshot(profile_data, trust_cfg)
    except Exception as exc:  # noqa: BLE001
        return {
            "profile": profile,
            "ran_at": _now().isoformat(),
            "capability_label": "live-template",
            "environment": environment,
            "checks": [],
            "failed": 0,
            "unknown": 0,
            "passed": 0,
            "drafts": [],
            "persisted": {
                "enabled": persist,
                "issues_created": 0,
                "issues_existing": 0,
                "obligations_created": 0,
            },
            "ok": False,
            "missing_configuration": [str(exc)],
            "warnings": gate.get("warnings") or [],
            "contract": gate.get("contract"),
        }

    context = build_live_trust_contexts_from_snapshot(snapshot, trust_cfg)
    results = run_trust_checks(context)
    for result in results:
        if result.check_id == "integrity_status":
            result.index_id = trust_cfg["integrity_index_id"]
    drafts = results_to_issue_drafts(results, environment=environment)
    return _report_from_results(
        profile=profile,
        results=results,
        drafts=drafts,
        persist=persist,
        capability_label="live-verified",
        environment=environment,
        extra={
            "source": "live_sor",
            "snapshot_summary": {
                "integrity_failures": len(snapshot.get("integrity_failures") or []),
                "series_dates": snapshot.get("series_dates"),
                "latest_integrity_run_ts": snapshot.get("latest_integrity_run_ts"),
                "covered_count": snapshot.get("covered_count"),
                "universe_count": snapshot.get("universe_count"),
            },
        },
    )


def maintain_once(
    *,
    profile: str = "supercalc_synthetic",
    persist: bool = False,
    inject_missing_session: Optional[str] = None,
    covered_count: Optional[int] = 22,
    universe_count: Optional[int] = 100,
    min_coverage_ratio: float = 0.15,
    observed_at: Optional[datetime] = None,
    sla_hours: float = 24.0,
    force: bool = False,
    live_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run one maintenance pass for Supercalc-shaped trust checks.

    Args:
        persist: When True, write issues/obligations to PostgreSQL (Winston agent DB)
        force: For live profiles, skip offline/flag gates (still needs contracts)
        live_snapshot: Injected SoR snapshot for tests / offline live-path exercise
    """
    synthetic_profiles = ("supercalc_synthetic", "supercalc", "synthetic")
    if profile in LIVE_PROFILES or live_snapshot is not None:
        if inject_missing_session:
            raise ValueError(
                "--inject-missing is for offline synthetic profiles only"
            )
        return _maintain_live(
            profile=profile if profile in LIVE_PROFILES else "supercalc_live",
            persist=persist,
            force=force,
            live_snapshot=live_snapshot,
        )

    if profile not in synthetic_profiles:
        raise ValueError(
            "maintain supports supercalc_synthetic (offline) or supercalc_live "
            f"(live SoR); got {profile}"
        )

    context = build_supercalc_trust_contexts(
        inject_missing_session=inject_missing_session,
        covered_count=covered_count,
        universe_count=universe_count,
        min_coverage_ratio=min_coverage_ratio,
        observed_at=observed_at,
        sla_hours=sla_hours,
    )
    results = run_trust_checks(context)
    drafts = results_to_issue_drafts(results, environment="synthetic")
    return _report_from_results(
        profile=profile,
        results=results,
        drafts=drafts,
        persist=persist,
        capability_label="fixture-verified",
        environment="synthetic",
    )
