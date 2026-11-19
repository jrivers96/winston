"""Recorded fixture bundles for offline continual testing.

Bundles are allowlisted evidence only: no credentials, no customer P&L,
no raw auth headers. Large/runtime payloads stay under `.winston/`;
tiny samples may be checked into `fixtures/recorded/samples/`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set
from uuid import uuid4

from winston.lineage.graph import (
    DependencyEdge,
    DependencyGraph,
    EdgeType,
    ExecutionNode,
)
from winston.lineage.replay import create_replay_plan
from winston.lineage.traversal import find_impact


BUNDLE_SCHEMA_VERSION = "1.0.0"

# Keys that hold secrets (not policy booleans like credentials_excluded)
_SECRET_KEY_PATTERN = re.compile(
    r"(^|_)(password|passwd|secret|token|api[_-]?key|authorization|credential|credentials|private[_-]?key)s?$",
    re.IGNORECASE,
)

_FORBIDDEN_CONTENT_KEYS = {
    "customer_pnl",
    "positions",
    "inventory",
    "p_and_l",
    "pnl",
}

_POLICY_SUFFIXES = ("_excluded", "_blocked_on_replay", "_enabled", "_disabled")


class RecordingError(ValueError):
    """Raised when a bundle violates recording policy."""


def default_samples_dir() -> Path:
    """Checked-in sample bundles directory."""
    return Path("fixtures/recorded/samples")


def default_runtime_dir() -> Path:
    """Runtime recorded fixtures (gitignored under .winston)."""
    return Path(".winston/fixtures/recorded")


def _is_secret_key(key: str) -> bool:
    """Return True for keys that should be redacted as secrets."""
    lowered = key.lower()
    if any(lowered.endswith(suffix) for suffix in _POLICY_SUFFIXES):
        return False
    return bool(_SECRET_KEY_PATTERN.search(lowered))


def redact_value(value: Any, key: Optional[str] = None) -> Any:
    """Redact secrets and forbidden customer fields from nested data."""
    if key is not None:
        if _is_secret_key(key):
            return "[REDACTED]"
        if key.lower() in _FORBIDDEN_CONTENT_KEYS:
            return "[OMITTED_CUSTOMER_DATA]"

    if isinstance(value, dict):
        return {k: redact_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def validate_no_secrets(payload: Any, path: str = "$") -> None:
    """Raise RecordingError if secrets or forbidden fields remain."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}"
            if _is_secret_key(str(key)):
                if value != "[REDACTED]":
                    raise RecordingError(f"Secret-like key not redacted at {child}")
            if str(key).lower() in _FORBIDDEN_CONTENT_KEYS:
                if value != "[OMITTED_CUSTOMER_DATA]":
                    raise RecordingError(f"Forbidden customer field at {child}")
            validate_no_secrets(value, child)
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            validate_no_secrets(item, f"{path}[{i}]")


def graph_to_dict(graph: DependencyGraph) -> Dict[str, Any]:
    """Serialize a dependency graph for a recorded bundle."""
    return {
        "nodes": [
            {
                "execution_id": node.execution_id,
                "index_id": node.index_id,
                "business_date": node.business_date,
                "environment": node.environment,
                "status": node.status,
                "state_content": redact_value(node.state_content or {}),
                "is_selected": node.is_selected,
            }
            for node in graph.nodes.values()
        ],
        "edges": [
            {
                "source_execution_id": edge.source_execution_id,
                "target_execution_id": edge.target_execution_id,
                "edge_type": edge.edge_type.value,
                "artifact_id": edge.artifact_id,
                "field_path": edge.field_path,
                "evidence_category": edge.evidence_category,
            }
            for edge in graph.edges
        ],
    }


def graph_from_dict(data: Dict[str, Any]) -> DependencyGraph:
    """Deserialize a dependency graph from a recorded bundle."""
    graph = DependencyGraph()
    for node_data in data.get("nodes", []):
        graph.add_node(
            ExecutionNode(
                execution_id=node_data["execution_id"],
                index_id=node_data["index_id"],
                business_date=node_data["business_date"],
                environment=node_data.get("environment", "synthetic"),
                status=node_data.get("status", "succeeded"),
                state_content=node_data.get("state_content"),
                is_selected=node_data.get("is_selected", True),
            )
        )
    for edge_data in data.get("edges", []):
        graph.add_edge(
            DependencyEdge(
                source_execution_id=edge_data["source_execution_id"],
                target_execution_id=edge_data["target_execution_id"],
                edge_type=EdgeType(edge_data["edge_type"]),
                artifact_id=edge_data.get("artifact_id"),
                field_path=edge_data.get("field_path"),
                evidence_category=edge_data.get("evidence_category", "observed"),
            )
        )
    return graph


def build_manifest(
    *,
    bundle_id: str,
    case_id: str,
    profile: str,
    change: Dict[str, Any],
    source: str = "synthetic_record",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a recorded bundle manifest."""
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "case_id": case_id,
        "profile": profile,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "capability_label": "fixture-verified",
        "change": redact_value(change),
        "policy": {
            "credentials_excluded": True,
            "customer_pnl_excluded": True,
            "live_network_blocked_on_replay": True,
        },
        "notes": notes,
    }


def write_bundle(
    output_dir: Path,
    *,
    manifest: Dict[str, Any],
    graph: DependencyGraph,
    evidence: Optional[List[Dict[str, Any]]] = None,
    expectations: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write a recorded fixture bundle atomically-ish to output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    graph_payload = graph_to_dict(graph)
    evidence_payload = redact_value(evidence or [])
    expectations_payload = redact_value(expectations or {})
    manifest_payload = redact_value(manifest)

    for name, payload in (
        ("manifest", manifest_payload),
        ("graph", graph_payload),
        ("evidence", evidence_payload),
        ("expectations", expectations_payload),
    ):
        validate_no_secrets(payload)

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "graph.json").write_text(
        json.dumps(graph_payload, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "evidence.json").write_text(
        json.dumps(evidence_payload, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "expectations.json").write_text(
        json.dumps(expectations_payload, indent=2, sort_keys=True) + "\n"
    )
    return output_dir


def load_bundle(bundle_dir: Path) -> Dict[str, Any]:
    """Load and validate a recorded fixture bundle."""
    bundle_dir = Path(bundle_dir)
    if not bundle_dir.exists():
        raise FileNotFoundError(f"Recorded bundle not found: {bundle_dir}")

    required = ["manifest.json", "graph.json"]
    missing = [name for name in required if not (bundle_dir / name).exists()]
    if missing:
        raise RecordingError(f"Incomplete bundle {bundle_dir}: missing {missing}")

    manifest = json.loads((bundle_dir / "manifest.json").read_text())
    graph_data = json.loads((bundle_dir / "graph.json").read_text())
    evidence_path = bundle_dir / "evidence.json"
    expectations_path = bundle_dir / "expectations.json"
    evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else []
    expectations = (
        json.loads(expectations_path.read_text()) if expectations_path.exists() else {}
    )

    if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise RecordingError(
            f"Unsupported bundle schema {manifest.get('schema_version')} "
            f"(expected {BUNDLE_SCHEMA_VERSION})"
        )

    validate_no_secrets(manifest)
    validate_no_secrets(graph_data)
    validate_no_secrets(evidence)
    validate_no_secrets(expectations)

    return {
        "dir": str(bundle_dir),
        "manifest": manifest,
        "graph": graph_from_dict(graph_data),
        "graph_data": graph_data,
        "evidence": evidence,
        "expectations": expectations,
    }


def resolve_bundle_path(bundle_ref: str) -> Path:
    """Resolve a bundle path or sample name to a directory."""
    path = Path(bundle_ref)
    if path.exists():
        return path

    sample = default_samples_dir() / bundle_ref
    if sample.exists():
        return sample

    runtime = default_runtime_dir() / bundle_ref
    if runtime.exists():
        return runtime

    raise FileNotFoundError(
        f"Recorded bundle '{bundle_ref}' not found under "
        f"{default_samples_dir()} or {default_runtime_dir()}"
    )


def replay_bundle(bundle_dir: Path, offline: bool = True) -> Dict[str, Any]:
    """Replay impact/repair analysis from a recorded bundle."""
    if not offline:
        raise ValueError("Recorded bundle replay is offline-only; pass --offline")

    bundle = load_bundle(bundle_dir)
    manifest = bundle["manifest"]
    graph: DependencyGraph = bundle["graph"]
    expectations = bundle["expectations"]
    change = manifest.get("change", {})

    origin_id = (
        change.get("origin_execution_id")
        or expectations.get("origin_execution_id")
    )
    if not origin_id:
        raise RecordingError("Bundle missing change.origin_execution_id")

    impact = find_impact(
        graph,
        origin_id,
        change_field=change.get("field_path") or change.get("field"),
    )
    plan = create_replay_plan(
        graph,
        impact.all_affected,
        checkpoint_execution_id=origin_id,
        endpoint_date=expectations.get("endpoint_date"),
        scenario="corrected_plan",
    )

    expected_indices = set(expectations.get("affected_indices", []))
    excluded_prefixes = expectations.get("excluded_index_prefixes", [])
    actual_indices = set(impact.affected_indices)

    unrelated_hits = [
        eid
        for eid in impact.all_affected
        if any(eid.startswith(prefix) for prefix in excluded_prefixes)
    ]

    assertions = {
        "origin_present": graph.get_node(origin_id) is not None,
        "expected_indices_affected": expected_indices.issubset(actual_indices)
        if expected_indices
        else True,
        "excluded_indices_absent": len(unrelated_hits) == 0,
        "impact_complete": impact.complete,
    }

    report = {
        "case": manifest.get("case_id"),
        "bundle_id": manifest.get("bundle_id"),
        "bundle_dir": str(bundle_dir),
        "offline": True,
        "capability_label": "fixture-verified",
        "source": "recorded_bundle",
        "change": change,
        "impact": {
            "origin_execution_id": origin_id,
            "complete": impact.complete,
            "affected_indices": sorted(actual_indices),
            "all_affected": impact.all_affected,
            "unrelated_excluded": len(unrelated_hits) == 0,
            "unrelated_hits": unrelated_hits,
        },
        "repair_plan": plan.to_dict(),
        "evidence_count": len(bundle["evidence"]),
        "assertions": assertions,
        "passed": all(assertions.values()),
    }
    return report


def record_supercalc_late_correction(output_dir: Path) -> Path:
    """Record the Supercalc late-correction synthetic graph as a sample bundle."""
    from winston.evaluation.supercalc import (
        SUPERCALC_GOLDEN,
        create_execution_id,
        create_supercalc_graph,
    )

    graph = create_supercalc_graph("original")
    origin = create_execution_id("STRESS", "S2", "original")
    bundle_id = f"rec_{uuid4().hex[:12]}"

    evidence = [
        {
            "type": "collection_receipt",
            "source_type": "synthetic",
            "source_scope": "supercalc_synthetic",
            "status": "complete",
            "note": "Allowlisted synthetic evidence only",
        },
        {
            "type": "state_snapshot",
            "index_id": "STRESS",
            "scenario": "original",
            "levels": {
                d: SUPERCALC_GOLDEN["original"]["STRESS"][d]["level"]
                for d in ["S1", "S2", "S3", "S4", "S5"]
            },
        },
        {
            "type": "state_snapshot",
            "index_id": "STRESS",
            "scenario": "corrected",
            "levels": {
                d: SUPERCALC_GOLDEN["corrected"]["STRESS"][d]["level"]
                for d in ["S1", "S2", "S3", "S4", "S5"]
            },
        },
    ]

    manifest = build_manifest(
        bundle_id=bundle_id,
        case_id="recorded-supercalc-late-correction",
        profile="supercalc_synthetic",
        change={
            "id": "S2_Q_CORRECTION",
            "index": "STRESS",
            "origin_date": "S2",
            "origin_execution_id": origin,
            "field": "q",
            "field_path": "state.carry",
            "original_value": 0,
            "corrected_value": 5,
        },
        source="synthetic_record",
        notes="Sample recorded bundle for nightly offline continual testing",
    )

    expectations = {
        "origin_execution_id": origin,
        "endpoint_date": "S5",
        "affected_indices": ["STRESS", "HEDGE_ARM"],
        "excluded_index_prefixes": ["TRUST_UNRELATED_"],
        "corrected_s5_level": 110,
        "original_s5_level": 105,
    }

    return write_bundle(
        output_dir,
        manifest=manifest,
        graph=graph,
        evidence=evidence,
        expectations=expectations,
    )


def list_recorded_bundles() -> Dict[str, str]:
    """List sample and runtime recorded bundles."""
    found: Dict[str, str] = {}
    for root in (default_samples_dir(), default_runtime_dir()):
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "manifest.json").exists():
                try:
                    manifest = json.loads((child / "manifest.json").read_text())
                    found[child.name] = manifest.get(
                        "case_id", child.name
                    ) + f" ({root})"
                except Exception:
                    found[child.name] = f"(unreadable) {root}"
    return found
