"""Unit tests for artifact storage."""

import json
from pathlib import Path

import pytest

from winston.storage.artifacts import ArtifactStore
from winston.domain.identities import ArtifactId


class TestArtifactStore:
    """Test ArtifactStore functionality."""
    
    @pytest.fixture
    def store(self, temp_dir: Path) -> ArtifactStore:
        """Create a test artifact store."""
        return ArtifactStore(temp_dir / "artifacts")
    
    def test_store_and_retrieve_bytes(self, store: ArtifactStore):
        """Test storing and retrieving raw bytes."""
        artifact_id = ArtifactId("test_artifact_001")
        content = b"Hello, Winston!"
        
        result = store.store(artifact_id, content)
        
        assert result["size_bytes"] == len(content)
        assert "content_hash" in result
        
        retrieved = store.retrieve(artifact_id)
        assert retrieved == content
    
    def test_store_and_retrieve_dict(self, store: ArtifactStore):
        """Test storing and retrieving JSON dict."""
        artifact_id = ArtifactId("test_artifact_002")
        content = {"key": "value", "number": 42}
        
        result = store.store(artifact_id, content)
        
        retrieved = store.retrieve_json(artifact_id)
        assert retrieved == content
    
    def test_store_and_retrieve_string(self, store: ArtifactStore):
        """Test storing and retrieving string."""
        artifact_id = ArtifactId("test_artifact_003")
        content = "Some text content"
        
        store.store(artifact_id, content)
        
        retrieved = store.retrieve(artifact_id)
        assert retrieved.decode("utf-8") == content
    
    def test_hash_verification(self, store: ArtifactStore):
        """Test hash verification on retrieval."""
        artifact_id = ArtifactId("test_artifact_004")
        content = b"Content to hash"
        
        result = store.store(artifact_id, content)
        correct_hash = result["content_hash"]
        
        # Should succeed with correct hash
        retrieved = store.retrieve(artifact_id, verify_hash=correct_hash)
        assert retrieved == content
        
        # Should fail with wrong hash
        with pytest.raises(ValueError, match="hash mismatch"):
            store.retrieve(artifact_id, verify_hash="wrong_hash")
    
    def test_expected_hash_on_store(self, store: ArtifactStore):
        """Test expected hash validation on store."""
        artifact_id = ArtifactId("test_artifact_005")
        content = b"Content"
        
        # Store first to get correct hash
        result = store.store(artifact_id, content)
        correct_hash = result["content_hash"]
        
        # Delete and re-store with expected hash
        store.delete(artifact_id)
        
        # Should succeed with correct expected hash
        result = store.store(ArtifactId("test_artifact_005b"), content, expected_hash=correct_hash)
        assert result["content_hash"] == correct_hash
        
        # Should fail with wrong expected hash
        with pytest.raises(ValueError, match="hash mismatch"):
            store.store(ArtifactId("test_artifact_005c"), content, expected_hash="wrong")
    
    def test_exists(self, store: ArtifactStore):
        """Test existence check."""
        artifact_id = ArtifactId("test_artifact_006")
        
        assert not store.exists(artifact_id)
        
        store.store(artifact_id, b"content")
        
        assert store.exists(artifact_id)
    
    def test_delete(self, store: ArtifactStore):
        """Test artifact deletion."""
        artifact_id = ArtifactId("test_artifact_007")
        
        store.store(artifact_id, b"content")
        assert store.exists(artifact_id)
        
        deleted = store.delete(artifact_id)
        assert deleted
        assert not store.exists(artifact_id)
        
        # Deleting non-existent returns False
        deleted = store.delete(artifact_id)
        assert not deleted
    
    def test_retrieve_nonexistent(self, store: ArtifactStore):
        """Test retrieving non-existent artifact."""
        artifact_id = ArtifactId("nonexistent")
        
        with pytest.raises(FileNotFoundError):
            store.retrieve(artifact_id)
    
    def test_list_artifacts(self, store: ArtifactStore):
        """Test listing all artifacts."""
        ids = [ArtifactId(f"list_test_{i}") for i in range(5)]
        
        for aid in ids:
            store.store(aid, b"content")
        
        listed = store.list_artifacts()
        
        for aid in ids:
            assert aid in listed
    
    def test_get_stats(self, store: ArtifactStore):
        """Test storage statistics."""
        content = b"x" * 1000
        
        for i in range(3):
            store.store(ArtifactId(f"stats_test_{i}"), content)
        
        stats = store.get_stats()
        
        assert stats["artifact_count"] == 3
        assert stats["total_size_bytes"] == 3000
    
    def test_hierarchical_storage(self, store: ArtifactStore):
        """Test that artifacts are stored hierarchically."""
        artifact_id = ArtifactId("abcd1234efgh")
        store.store(artifact_id, b"content")
        
        # Should be stored in ab/cd/ subdirectory
        expected_path = store.root_dir / "ab" / "cd" / "abcd1234efgh"
        assert expected_path.exists()
