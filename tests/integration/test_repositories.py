"""Integration tests for database repositories."""

from datetime import datetime, timezone

import pytest

from winston.domain import (
    Issue,
    IssueId,
    IssueState,
    Obligation,
    ObligationId,
    ObligationState,
)
from winston.storage.repositories import IssueRepository, ObligationRepository


@pytest.mark.integration
class TestIssueRepository:
    """Test IssueRepository database operations."""
    
    def test_create_and_get_issue(self, session, sample_issue_data):
        """Test creating and retrieving an issue."""
        repo = IssueRepository(session)
        
        issue = Issue(**sample_issue_data)
        created = repo.create(issue)
        
        assert created.id == issue.id
        
        retrieved = repo.get(issue.id)
        assert retrieved is not None
        assert retrieved.title == issue.title
        assert retrieved.state == IssueState.OPEN
    
    def test_get_nonexistent_issue(self, session):
        """Test retrieving non-existent issue."""
        repo = IssueRepository(session)
        
        result = repo.get(IssueId("nonexistent"))
        assert result is None
    
    def test_get_by_fingerprint(self, session, sample_issue_data):
        """Test retrieving issue by fingerprint."""
        repo = IssueRepository(session)
        
        issue = Issue(**sample_issue_data)
        repo.create(issue)
        session.flush()
        
        retrieved = repo.get_by_fingerprint(issue.fingerprint)
        assert retrieved is not None
        assert retrieved.id == issue.id
    
    def test_list_by_state(self, session, sample_issue_data):
        """Test listing issues by state."""
        repo = IssueRepository(session)
        
        # Create open issue
        open_issue = Issue(**sample_issue_data)
        repo.create(open_issue)
        
        # Create resolved issue
        resolved_data = sample_issue_data.copy()
        resolved_data["id"] = f"issue_resolved_{datetime.now().timestamp()}"
        resolved_data["state"] = IssueState.RESOLVED
        resolved_data["fingerprint"] = "resolved_fp"
        resolved_issue = Issue(**resolved_data)
        repo.create(resolved_issue)
        
        session.flush()
        
        # List open issues
        open_issues = repo.list_by_state(IssueState.OPEN)
        assert len(open_issues) >= 1
        assert any(i.id == open_issue.id for i in open_issues)
        
        # List resolved issues
        resolved_issues = repo.list_by_state(IssueState.RESOLVED)
        assert any(i.id == resolved_issue.id for i in resolved_issues)
    
    def test_update_state(self, session, sample_issue_data):
        """Test updating issue state."""
        repo = IssueRepository(session)
        
        issue = Issue(**sample_issue_data)
        repo.create(issue)
        session.flush()
        
        updated = repo.update_state(issue.id, IssueState.INVESTIGATING)
        
        assert updated is not None
        assert updated.state == IssueState.INVESTIGATING
        
        # Verify in database
        retrieved = repo.get(issue.id)
        assert retrieved.state == IssueState.INVESTIGATING
    
    def test_update_state_with_version_check(self, session, sample_issue_data):
        """Test optimistic locking on state update."""
        repo = IssueRepository(session)
        
        issue = Issue(**sample_issue_data)
        repo.create(issue)
        session.flush()
        
        # Update with correct version
        updated = repo.update_state(issue.id, IssueState.INVESTIGATING, expected_version=1)
        assert updated is not None
        
        # Update with wrong version should fail
        result = repo.update_state(issue.id, IssueState.RESOLVED, expected_version=1)
        assert result is None  # Version mismatch


@pytest.mark.integration
class TestObligationRepository:
    """Test ObligationRepository database operations."""
    
    def test_create_and_get_obligation(
        self, session, sample_issue_data, sample_obligation_data
    ):
        """Test creating and retrieving an obligation."""
        issue_repo = IssueRepository(session)
        obl_repo = ObligationRepository(session)
        
        # Create parent issue first
        issue = Issue(**sample_issue_data)
        issue_repo.create(issue)
        session.flush()
        
        # Create obligation
        obligation = Obligation(**sample_obligation_data)
        created = obl_repo.create(obligation)
        
        assert created.id == obligation.id
        
        retrieved = obl_repo.get(obligation.id)
        assert retrieved is not None
        assert retrieved.title == obligation.title
    
    def test_list_by_issue(self, session, sample_issue_data, sample_obligation_data):
        """Test listing obligations for an issue."""
        issue_repo = IssueRepository(session)
        obl_repo = ObligationRepository(session)
        
        issue = Issue(**sample_issue_data)
        issue_repo.create(issue)
        session.flush()
        
        # Create multiple obligations
        for i in range(3):
            obl_data = sample_obligation_data.copy()
            obl_data["id"] = f"obl_{i}_{datetime.now().timestamp()}"
            obl_data["title"] = f"Obligation {i}"
            obl = Obligation(**obl_data)
            obl_repo.create(obl)
        
        session.flush()
        
        obligations = obl_repo.list_by_issue(issue.id)
        assert len(obligations) == 3
    
    def test_list_pending(self, session, sample_issue_data, sample_obligation_data):
        """Test listing pending obligations."""
        issue_repo = IssueRepository(session)
        obl_repo = ObligationRepository(session)
        
        issue = Issue(**sample_issue_data)
        issue_repo.create(issue)
        session.flush()
        
        obligation = Obligation(**sample_obligation_data)
        obl_repo.create(obligation)
        session.flush()
        
        pending = obl_repo.list_pending()
        assert any(o.id == obligation.id for o in pending)
    
    def test_update_state(self, session, sample_issue_data, sample_obligation_data):
        """Test updating obligation state."""
        issue_repo = IssueRepository(session)
        obl_repo = ObligationRepository(session)
        
        issue = Issue(**sample_issue_data)
        issue_repo.create(issue)
        
        obligation = Obligation(**sample_obligation_data)
        obl_repo.create(obligation)
        session.flush()
        
        updated = obl_repo.update_state(obligation.id, ObligationState.COMPLETED)
        
        assert updated is not None
        assert updated.state == ObligationState.COMPLETED


@pytest.mark.integration
class TestIssueObligationRelationship:
    """Test issue-obligation relationships."""
    
    def test_issue_survives_restart(
        self, session, sample_issue_data, sample_obligation_data
    ):
        """Test that issue and obligations survive database commit.
        
        This is a Phase 1 exit criterion: synthetic issue + evidence + 
        pending obligation survive restart.
        """
        issue_repo = IssueRepository(session)
        obl_repo = ObligationRepository(session)
        
        # Create issue
        issue = Issue(**sample_issue_data)
        issue_repo.create(issue)
        
        # Create obligation
        obligation = Obligation(**sample_obligation_data)
        obl_repo.create(obligation)
        
        # Commit
        session.commit()
        
        # Clear session cache
        session.expire_all()
        
        # Retrieve and verify
        retrieved_issue = issue_repo.get(issue.id)
        assert retrieved_issue is not None
        assert retrieved_issue.state == IssueState.OPEN
        
        retrieved_obligation = obl_repo.get(obligation.id)
        assert retrieved_obligation is not None
        assert retrieved_obligation.state == ObligationState.PENDING
        assert retrieved_obligation.issue_id == issue.id
