"""Check runner for executing multiple checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from winston.checks.base import Check, CheckResult, CheckStatus


@dataclass
class CheckRunResult:
    """Result of running multiple checks."""
    
    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Results
    results: List[CheckResult] = field(default_factory=list)
    
    # Summary
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    unknown: int = 0
    not_applicable: int = 0
    
    @property
    def all_passed(self) -> bool:
        """Check if all checks passed."""
        return self.failed == 0 and self.unknown == 0
    
    def add_result(self, result: CheckResult) -> None:
        """Add a check result and update counts."""
        self.results.append(result)
        self.total_checks += 1
        
        if result.status == CheckStatus.PASS:
            self.passed += 1
        elif result.status == CheckStatus.FAIL:
            self.failed += 1
        elif result.status == CheckStatus.UNKNOWN:
            self.unknown += 1
        else:
            self.not_applicable += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "unknown": self.unknown,
            "not_applicable": self.not_applicable,
            "all_passed": self.all_passed,
            "results": [r.to_dict() for r in self.results],
        }


class CheckRunner:
    """Runner for executing checks."""
    
    def __init__(self):
        self.checks: List[Check] = []
    
    def register(self, check: Check) -> None:
        """Register a check."""
        self.checks.append(check)
    
    def register_all(self, checks: List[Check]) -> None:
        """Register multiple checks."""
        self.checks.extend(checks)
    
    def run_all(self, context: Dict[str, Any]) -> CheckRunResult:
        """Run all registered checks.
        
        Args:
            context: Context data for checks
            
        Returns:
            CheckRunResult with all results
        """
        result = CheckRunResult()
        
        for check in self.checks:
            try:
                check_result = check.run(context)
                result.add_result(check_result)
            except Exception as e:
                # Create an error result for failed checks
                error_result = CheckResult(
                    check_id=check.check_id,
                    check_version=check.version,
                    status=CheckStatus.UNKNOWN,
                    message=f"Check failed with error: {str(e)}",
                    is_complete=False,
                    incomplete_reason=str(e),
                )
                result.add_result(error_result)
        
        result.completed_at = datetime.utcnow()
        return result
    
    def run_check(self, check_id: str, context: Dict[str, Any]) -> Optional[CheckResult]:
        """Run a specific check by ID.
        
        Args:
            check_id: Check to run
            context: Context data
            
        Returns:
            CheckResult or None if check not found
        """
        for check in self.checks:
            if check.check_id == check_id:
                return check.run(context)
        return None
