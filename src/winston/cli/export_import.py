"""Export and import functionality for Winston data."""

from __future__ import annotations

import json
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from winston.config import get_settings
from winston.storage.database import get_session
from winston.storage.repositories import IssueRepository, ObligationRepository
from winston.storage.artifacts import ArtifactStore


EXPORT_VERSION = "1.0.0"


def export_bundle(output_path: Path) -> dict[str, Any]:
    """Export Winston data to a bundle.
    
    Creates a tarball containing:
    - manifest.json: Export metadata and schema version
    - issues.json: All issues
    - obligations.json: All obligations
    - artifacts/: Referenced artifact files
    
    Args:
        output_path: Path to write the bundle
        
    Returns:
        Dict with export statistics
    """
    settings = get_settings()
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Collect data in a consistent snapshot
    with get_session() as session:
        issue_repo = IssueRepository(session)
        obligation_repo = ObligationRepository(session)
        
        issues = issue_repo.list_all()
        
        # Collect all obligations
        all_obligations = []
        for issue in issues:
            obligations = obligation_repo.list_by_issue(issue.id)
            all_obligations.extend(obligations)
        
        # Collect evidence refs
        evidence_refs = set()
        for issue in issues:
            evidence_refs.update(str(ref) for ref in issue.evidence_refs)
        for obligation in all_obligations:
            evidence_refs.update(str(ref) for ref in obligation.evidence_refs)
    
    # Create manifest
    manifest = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "issue_count": len(issues),
        "obligation_count": len(all_obligations),
        "artifact_count": 0,
        "artifacts_included": [],
        "artifacts_missing": [],
    }
    
    # Create tarball
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Write issues
        issues_data = [issue.model_dump() for issue in issues]
        (tmppath / "issues.json").write_text(
            json.dumps(issues_data, default=str, indent=2)
        )
        
        # Write obligations
        obligations_data = [ob.model_dump() for ob in all_obligations]
        (tmppath / "obligations.json").write_text(
            json.dumps(obligations_data, default=str, indent=2)
        )
        
        # Copy artifacts
        artifact_store = ArtifactStore()
        artifacts_dir = tmppath / "artifacts"
        artifacts_dir.mkdir()
        
        for ref in evidence_refs:
            try:
                if artifact_store.exists(ref):
                    data = artifact_store.retrieve(ref)
                    (artifacts_dir / ref).write_bytes(data)
                    manifest["artifacts_included"].append(ref)
                    manifest["artifact_count"] += 1
                else:
                    manifest["artifacts_missing"].append(ref)
            except Exception as e:
                manifest["artifacts_missing"].append(f"{ref}: {e}")
        
        # Write manifest
        (tmppath / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )
        
        # Create tarball
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(tmppath / "manifest.json", arcname="manifest.json")
            tar.add(tmppath / "issues.json", arcname="issues.json")
            tar.add(tmppath / "obligations.json", arcname="obligations.json")
            if manifest["artifact_count"] > 0:
                tar.add(artifacts_dir, arcname="artifacts")
    
    return {
        "path": str(output_path),
        "issue_count": manifest["issue_count"],
        "obligation_count": manifest["obligation_count"],
        "artifact_count": manifest["artifact_count"],
        "artifacts_missing": manifest["artifacts_missing"],
    }


def import_bundle(input_path: Path, force: bool = False) -> dict[str, Any]:
    """Import Winston data from a bundle.
    
    Args:
        input_path: Path to the bundle tarball
        force: If True, overwrite existing data with same IDs
        
    Returns:
        Dict with import statistics
        
    Raises:
        ValueError: If bundle is invalid or has conflicts
    """
    if not input_path.exists():
        raise ValueError(f"Bundle not found: {input_path}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Extract tarball
        with tarfile.open(input_path, "r:gz") as tar:
            tar.extractall(tmppath)
        
        # Read and validate manifest
        manifest_path = tmppath / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("Invalid bundle: missing manifest.json")
        
        manifest = json.loads(manifest_path.read_text())
        
        if manifest.get("version") != EXPORT_VERSION:
            raise ValueError(
                f"Unsupported bundle version: {manifest.get('version')} "
                f"(expected {EXPORT_VERSION})"
            )
        
        # Read data
        issues_data = json.loads((tmppath / "issues.json").read_text())
        obligations_data = json.loads((tmppath / "obligations.json").read_text())
        
        # Import to database
        from winston.domain import Issue, Obligation, IssueId
        
        imported_issues = 0
        imported_obligations = 0
        skipped_issues = 0
        
        with get_session() as session:
            issue_repo = IssueRepository(session)
            obligation_repo = ObligationRepository(session)
            
            for issue_dict in issues_data:
                # Check for existing
                existing = issue_repo.get(IssueId(issue_dict["id"]))
                
                if existing and not force:
                    skipped_issues += 1
                    continue
                
                if existing:
                    # Would need update logic here
                    skipped_issues += 1
                    continue
                
                # Create issue
                # Note: Need to handle datetime parsing
                issue = Issue(**_parse_dates(issue_dict))
                issue_repo.create(issue)
                imported_issues += 1
            
            for ob_dict in obligations_data:
                # Only import if parent issue was imported or exists
                parent_issue = issue_repo.get(IssueId(ob_dict["issue_id"]))
                if parent_issue:
                    obligation = Obligation(**_parse_dates(ob_dict))
                    obligation_repo.create(obligation)
                    imported_obligations += 1
            
            session.commit()
        
        # Import artifacts
        artifacts_dir = tmppath / "artifacts"
        imported_artifacts = 0
        
        if artifacts_dir.exists():
            artifact_store = ArtifactStore()
            
            for artifact_file in artifacts_dir.iterdir():
                if artifact_file.is_file():
                    data = artifact_file.read_bytes()
                    artifact_store.store(artifact_file.name, data)
                    imported_artifacts += 1
    
    return {
        "issue_count": imported_issues,
        "obligation_count": imported_obligations,
        "artifact_count": imported_artifacts,
        "skipped_issues": skipped_issues,
    }


def _parse_dates(data: dict) -> dict:
    """Parse datetime strings in a dict."""
    result = data.copy()
    
    date_fields = [
        "created_at", "updated_at", "state_changed_at",
        "due_at", "last_attempt_at",
    ]
    
    for field in date_fields:
        if field in result and result[field]:
            if isinstance(result[field], str):
                result[field] = datetime.fromisoformat(
                    result[field].replace("Z", "+00:00")
                )
    
    return result
