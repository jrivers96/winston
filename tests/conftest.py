"""Pytest configuration and fixtures."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from winston.config import WinstonSettings
from winston.storage.models import Base


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Get test database URL.
    
    Uses WINSTON_TEST_DATABASE_URL env var or falls back to default.
    """
    return os.environ.get(
        "WINSTON_TEST_DATABASE_URL",
        "postgresql://winston:winston_dev@localhost:5432/winston_test"
    )


@pytest.fixture(scope="session")
def engine(test_database_url: str):
    """Create test database engine."""
    engine = create_engine(test_database_url)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Drop all tables after tests
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    """Create a test session with rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    
    Session = sessionmaker(bind=connection)
    session = Session()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> WinstonSettings:
    """Create test settings with temporary directories."""
    return WinstonSettings(
        data_dir=temp_dir / ".winston",
        profiles_dir=Path("profiles"),
        registry_dir=Path("registry"),
        profile="synthetic",
        offline_mode=True,
    )


@pytest.fixture
def sample_issue_data() -> dict:
    """Sample issue data for testing."""
    now = datetime.now(timezone.utc)
    return {
        "id": f"issue_{uuid4().hex[:12]}",
        "title": "Test Issue",
        "description": "A test issue for unit testing",
        "index_id": "DEMO",
        "environment": "synthetic",
        "affected_dates": ["D1", "D2"],
        "state": "open",
        "state_changed_at": now,
        "severity": "medium",
        "impact_summary": None,
        "affected_executions": [],
        "evidence_refs": [],
        "completion_criteria": "Verify calculation is correct",
        "previous_issue_id": None,
        "recurrence_count": 0,
        "created_at": now,
        "created_by": "test",
        "updated_at": now,
        "fingerprint": "test_fingerprint_123",
        "metadata": {},
    }


@pytest.fixture
def sample_obligation_data(sample_issue_data: dict) -> dict:
    """Sample obligation data for testing."""
    now = datetime.now(timezone.utc)
    return {
        "id": f"obl_{uuid4().hex[:12]}",
        "issue_id": sample_issue_data["id"],
        "title": "Verify Calculation",
        "description": "Verify the calculation produces correct results",
        "action_type": "verify",
        "owner": None,
        "state": "pending",
        "state_changed_at": now,
        "wake_condition": None,
        "due_at": None,
        "progress_notes": [],
        "attempts": 0,
        "last_attempt_at": None,
        "evidence_refs": [],
        "created_at": now,
        "updated_at": now,
        "metadata": {},
    }
