"""Unit tests for domain models."""

from datetime import date, datetime, timezone

import pytest

from winston.domain import (
    BusinessDate,
    ExecutionId,
    IndexId,
    IssueId,
    IssueState,
    ObligationState,
    Scenario,
    ExecutionStatus,
    ArtifactType,
    CompletionStatus,
)
from winston.domain.calendars import CalendarConfig, CalendarDate
from winston.domain.issues import Issue, Obligation
from winston.domain.executions import Execution


class TestIdentities:
    """Test identity types."""
    
    def test_index_id_is_string(self):
        idx = IndexId("DEMO")
        assert str(idx) == "DEMO"
    
    def test_business_date_is_date(self):
        bd = BusinessDate(date(2024, 1, 15))
        assert bd.year == 2024
        assert bd.month == 1
        assert bd.day == 15
    
    def test_execution_id_uniqueness(self):
        e1 = ExecutionId("exec_001")
        e2 = ExecutionId("exec_002")
        assert e1 != e2


class TestEnums:
    """Test enum values."""
    
    def test_issue_states(self):
        assert IssueState.OPEN.value == "open"
        assert IssueState.RESOLVED.value == "resolved"
    
    def test_obligation_states(self):
        assert ObligationState.PENDING.value == "pending"
        assert ObligationState.COMPLETED.value == "completed"
    
    def test_scenarios(self):
        assert Scenario.AS_EXECUTED.value == "as_executed"
        assert Scenario.COUNTERFACTUAL.value == "counterfactual"
        assert Scenario.CORRECTED_PLAN.value == "corrected_plan"
    
    def test_completion_status(self):
        assert CompletionStatus.COMPLETE.value == "complete"
        assert CompletionStatus.HISTORICAL_UNAVAILABLE.value == "historical_unavailable"


class TestCalendar:
    """Test calendar configuration."""
    
    def test_calendar_config_creation(self):
        cal = CalendarConfig(
            id="test-cal",
            timezone="UTC",
        )
        assert cal.id == "test-cal"
        assert cal.timezone == "UTC"
    
    def test_calendar_with_dates(self):
        cal = CalendarConfig(
            id="test-cal",
            timezone="UTC",
            dates=[
                CalendarDate(
                    business_date=BusinessDate(date(2024, 1, 8)),
                    label="D1",
                    is_calculation_day=True,
                    previous_calculation_date=None,
                ),
                CalendarDate(
                    business_date=BusinessDate(date(2024, 1, 9)),
                    label="D2",
                    is_calculation_day=True,
                    previous_calculation_date=BusinessDate(date(2024, 1, 8)),
                ),
            ],
        )
        
        assert len(cal.dates) == 2
        assert cal.get_date_label(BusinessDate(date(2024, 1, 8))) == "D1"
        assert cal.is_calculation_day(BusinessDate(date(2024, 1, 8)))
    
    def test_previous_calculation_date(self):
        cal = CalendarConfig(
            id="test-cal",
            dates=[
                CalendarDate(
                    business_date=BusinessDate(date(2024, 1, 8)),
                    label="D1",
                    is_calculation_day=True,
                    previous_calculation_date=None,
                ),
                CalendarDate(
                    business_date=BusinessDate(date(2024, 1, 9)),
                    label="D2",
                    is_calculation_day=True,
                    previous_calculation_date=BusinessDate(date(2024, 1, 8)),
                ),
            ],
        )
        
        prev = cal.get_previous_calculation_date(BusinessDate(date(2024, 1, 9)))
        assert prev == BusinessDate(date(2024, 1, 8))


class TestIssue:
    """Test Issue model."""
    
    def test_issue_creation(self, sample_issue_data):
        issue = Issue(**sample_issue_data)
        
        assert issue.title == "Test Issue"
        assert issue.state == IssueState.OPEN
        assert issue.severity == "medium"
    
    def test_issue_serialization(self, sample_issue_data):
        issue = Issue(**sample_issue_data)
        data = issue.model_dump()
        
        assert data["title"] == "Test Issue"
        assert data["state"] == IssueState.OPEN


class TestObligation:
    """Test Obligation model."""
    
    def test_obligation_creation(self, sample_issue_data, sample_obligation_data):
        obligation = Obligation(**sample_obligation_data)
        
        assert obligation.title == "Verify Calculation"
        assert obligation.state == ObligationState.PENDING
        assert obligation.action_type == "verify"


class TestExecution:
    """Test Execution model."""
    
    def test_execution_creation(self):
        now = datetime.now(timezone.utc)
        
        execution = Execution(
            id=ExecutionId("exec_001"),
            index_id=IndexId("DEMO"),
            environment="synthetic",
            business_date=BusinessDate(date(2024, 1, 8)),
            status=ExecutionStatus.SUCCEEDED,
            started_at=now,
            completed_at=now,
        )
        
        assert execution.id == "exec_001"
        assert execution.status == ExecutionStatus.SUCCEEDED
