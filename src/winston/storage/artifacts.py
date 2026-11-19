"""Artifact storage with atomic writes and digest verification."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, Dict, List

from winston.config import get_settings
from winston.domain.identities import ArtifactId


class ArtifactStore:
    """Manages immutable artifact storage with atomic writes.
    
    Artifacts are stored with:
    - Atomic write (temp file -> fsync -> rename)
    - SHA-256 digest verification
    - Hierarchical directory structure
    """
    
    def __init__(self, root_dir: Path | None = None):
        """Initialize artifact store.
        
        Args:
            root_dir: Root directory for artifacts. Defaults to settings.artifacts_dir.
        """
        if root_dir is None:
            settings = get_settings()
            root_dir = settings.artifacts_dir
        
        self.root_dir = root_dir
        self._ensure_directory(self.root_dir)
    
    def _ensure_directory(self, path: Path) -> None:
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)
    
    def _get_artifact_path(self, artifact_id: ArtifactId) -> Path:
        """Get the storage path for an artifact.
        
        Uses hierarchical structure based on ID prefix to avoid
        too many files in one directory.
        """
        # Use first 2 and next 2 characters of ID for directory structure
        # e.g., "abc123..." -> artifacts/ab/c1/abc123...
        id_str = str(artifact_id)
        if len(id_str) >= 4:
            prefix1 = id_str[:2]
            prefix2 = id_str[2:4]
            return self.root_dir / prefix1 / prefix2 / id_str
        else:
            return self.root_dir / id_str
    
    def _compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()
    
    def store(
        self,
        artifact_id: ArtifactId,
        content: bytes | dict[str, Any] | str,
        expected_hash: str | None = None,
    ) -> dict[str, Any]:
        """Store an artifact atomically.
        
        Args:
            artifact_id: Unique identifier for the artifact
            content: Content to store (bytes, dict as JSON, or string)
            expected_hash: If provided, verify content matches this hash
            
        Returns:
            Dict with storage_path, content_hash, size_bytes
            
        Raises:
            ValueError: If expected_hash doesn't match computed hash
            OSError: If atomic write fails
        """
        # Convert content to bytes
        if isinstance(content, dict):
            data = json.dumps(content, sort_keys=True, indent=2).encode("utf-8")
        elif isinstance(content, str):
            data = content.encode("utf-8")
        else:
            data = content
        
        # Compute hash
        content_hash = self._compute_hash(data)
        
        # Verify hash if expected
        if expected_hash is not None and content_hash != expected_hash:
            raise ValueError(
                f"Content hash mismatch: expected {expected_hash}, got {content_hash}"
            )
        
        # Get target path and ensure directory exists
        target_path = self._get_artifact_path(artifact_id)
        self._ensure_directory(target_path.parent)
        
        # Atomic write: temp file -> fsync -> rename
        fd, temp_path = tempfile.mkstemp(
            dir=target_path.parent,
            prefix=".tmp_",
            suffix=".artifact",
        )
        try:
            os.write(fd, data)
            os.fsync(fd)
            os.close(fd)
            
            # Atomic rename
            os.rename(temp_path, target_path)
            
            # Sync parent directory
            dir_fd = os.open(target_path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
                
        except Exception:
            # Clean up temp file on failure
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
        
        return {
            "storage_path": str(target_path.relative_to(self.root_dir)),
            "content_hash": content_hash,
            "size_bytes": len(data),
        }
    
    def retrieve(
        self,
        artifact_id: ArtifactId,
        verify_hash: str | None = None,
    ) -> bytes:
        """Retrieve an artifact.
        
        Args:
            artifact_id: Artifact to retrieve
            verify_hash: If provided, verify content matches this hash
            
        Returns:
            Artifact content as bytes
            
        Raises:
            FileNotFoundError: If artifact doesn't exist
            ValueError: If hash verification fails
        """
        path = self._get_artifact_path(artifact_id)
        
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact_id}")
        
        data = path.read_bytes()
        
        if verify_hash is not None:
            actual_hash = self._compute_hash(data)
            if actual_hash != verify_hash:
                raise ValueError(
                    f"Artifact hash mismatch for {artifact_id}: "
                    f"expected {verify_hash}, got {actual_hash}"
                )
        
        return data
    
    def retrieve_json(
        self,
        artifact_id: ArtifactId,
        verify_hash: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve an artifact and parse as JSON.
        
        Args:
            artifact_id: Artifact to retrieve
            verify_hash: If provided, verify content matches this hash
            
        Returns:
            Artifact content as parsed JSON dict
        """
        data = self.retrieve(artifact_id, verify_hash)
        return json.loads(data.decode("utf-8"))
    
    def exists(self, artifact_id: ArtifactId) -> bool:
        """Check if an artifact exists."""
        return self._get_artifact_path(artifact_id).exists()
    
    def get_hash(self, artifact_id: ArtifactId) -> str:
        """Get the hash of a stored artifact."""
        data = self.retrieve(artifact_id)
        return self._compute_hash(data)
    
    def delete(self, artifact_id: ArtifactId) -> bool:
        """Delete an artifact.
        
        Returns:
            True if artifact was deleted, False if it didn't exist
        """
        path = self._get_artifact_path(artifact_id)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def list_artifacts(self) -> list[ArtifactId]:
        """List all artifact IDs in the store."""
        artifacts = []
        for path in self.root_dir.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                artifacts.append(ArtifactId(path.name))
        return artifacts
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        total_size = 0
        count = 0
        
        for path in self.root_dir.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                total_size += path.stat().st_size
                count += 1
        
        return {
            "artifact_count": count,
            "total_size_bytes": total_size,
            "root_dir": str(self.root_dir),
        }
