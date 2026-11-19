"""Doctor command implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from winston.config import get_settings
from winston.storage.database import check_connection


def run_doctor(profile_name: str) -> dict[str, Any]:
    """Run health checks and return results.
    
    Args:
        profile_name: Name of profile to check
        
    Returns:
        Dict with health check results
    """
    settings = get_settings()
    results: dict[str, Any] = {
        "healthy": True,
        "profile_name": profile_name,
    }
    
    # Check database
    db_result = check_connection()
    results["database"] = db_result
    if not db_result.get("connected"):
        results["healthy"] = False
    
    # Check directories
    dirs_result = {}
    for dir_name in ["data_dir", "artifacts_dir", "cache_dir", "fixtures_dir", "exports_dir"]:
        dir_path = getattr(settings, dir_name)
        dirs_result[dir_name] = {
            "path": str(dir_path),
            "exists": dir_path.exists(),
            "writable": dir_path.exists() and dir_path.is_dir(),
        }
    results["directories"] = dirs_result
    
    # Check profile
    profile_result = load_profile(profile_name, settings.profiles_dir)
    results["profile"] = profile_result
    if not profile_result.get("loaded"):
        results["healthy"] = False
    
    # Check repositories from registry
    repos_result = check_registry(settings.registry_dir)
    results["repositories"] = repos_result
    
    return results


def load_profile(profile_name: str, profiles_dir: Path) -> dict[str, Any]:
    """Load and validate a profile.
    
    Args:
        profile_name: Name of profile to load
        profiles_dir: Directory containing profiles
        
    Returns:
        Dict with profile loading result
    """
    profile_path = profiles_dir / f"{profile_name}.yaml"
    
    if not profile_path.exists():
        return {
            "name": profile_name,
            "loaded": False,
            "error": f"Profile file not found: {profile_path}",
        }
    
    try:
        with open(profile_path) as f:
            profile_data = yaml.safe_load(f)
        
        return {
            "name": profile_name,
            "loaded": True,
            "path": str(profile_path),
            "indices": len(profile_data.get("indices", [])),
            "calendars": len(profile_data.get("calendars", [])),
        }
    except Exception as e:
        return {
            "name": profile_name,
            "loaded": False,
            "error": str(e),
        }


def check_registry(registry_dir: Path) -> dict[str, Any]:
    """Check repository registry.
    
    Args:
        registry_dir: Directory containing registry files
        
    Returns:
        Dict with registry check results
    """
    repos_file = registry_dir / "repositories.yaml"
    
    if not repos_file.exists():
        return {
            "count": 0,
            "items": [],
            "error": f"Registry file not found: {repos_file}",
        }
    
    try:
        with open(repos_file) as f:
            registry_data = yaml.safe_load(f)
        
        repos = registry_data.get("repositories", [])
        items = []
        
        for repo in repos:
            repo_info = {
                "id": repo.get("id"),
                "role": repo.get("role"),
                "location_type": repo.get("location", {}).get("type"),
                "accessible": True,  # Would check actual accessibility
            }
            
            # Check if local path exists for local repos
            if repo_info["location_type"] == "local_fixture":
                local_path = repo.get("location", {}).get("path")
                if local_path:
                    repo_info["accessible"] = Path(local_path).exists()
            
            items.append(repo_info)
        
        return {
            "count": len(repos),
            "items": items,
        }
    except Exception as e:
        return {
            "count": 0,
            "items": [],
            "error": str(e),
        }
