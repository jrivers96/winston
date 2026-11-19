"""Repository management CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from winston.config import get_settings


def list_repositories() -> list[dict[str, Any]]:
    """List all registered repositories.
    
    Returns:
        List of repository info dicts
    """
    settings = get_settings()
    repos_file = settings.registry_dir / "repositories.yaml"
    
    if not repos_file.exists():
        return []
    
    try:
        with open(repos_file) as f:
            registry_data = yaml.safe_load(f)
        
        repos = registry_data.get("repositories", [])
        result = []
        
        for repo in repos:
            location = repo.get("location", {})
            result.append({
                "id": repo.get("id"),
                "description": repo.get("description"),
                "role": repo.get("role"),
                "location_type": location.get("type"),
                "location_path": location.get("path"),
                "is_accessible": _check_accessible(location),
            })
        
        return result
    except Exception:
        return []


def check_repositories() -> dict[str, Any]:
    """Check health of all registered repositories.
    
    Returns:
        Dict with repository health results
    """
    settings = get_settings()
    repos_file = settings.registry_dir / "repositories.yaml"
    
    if not repos_file.exists():
        return {
            "healthy": False,
            "error": "Registry file not found",
            "repositories": [],
        }
    
    try:
        with open(repos_file) as f:
            registry_data = yaml.safe_load(f)
        
        repos = registry_data.get("repositories", [])
        results = []
        all_healthy = True
        
        for repo in repos:
            location = repo.get("location", {})
            is_accessible = _check_accessible(location)
            
            repo_result = {
                "id": repo.get("id"),
                "healthy": is_accessible,
            }
            
            if not is_accessible:
                all_healthy = False
                if location.get("type") == "local_fixture":
                    repo_result["error"] = f"Path not found: {location.get('path')}"
                else:
                    repo_result["error"] = "Not accessible"
            
            results.append(repo_result)
        
        return {
            "healthy": all_healthy,
            "repositories": results,
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "repositories": [],
        }


def _check_accessible(location: dict) -> bool:
    """Check if a repository location is accessible.
    
    Args:
        location: Location dict from registry
        
    Returns:
        True if accessible
    """
    loc_type = location.get("type")
    
    if loc_type == "local_fixture":
        path = location.get("path")
        if path:
            # Fixture paths are relative to .winston
            settings = get_settings()
            full_path = settings.data_dir / path.lstrip("./")
            return full_path.exists()
        return False
    
    # For remote repos, would need to actually check connectivity
    # For now, assume accessible if configured
    return location.get("origin") is not None
