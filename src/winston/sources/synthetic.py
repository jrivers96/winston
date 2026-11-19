"""Synthetic source adapter for offline testing."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Dict
from uuid import uuid4

from winston.domain import (
    BusinessDate,
    CollectionReceipt,
    CompletionStatus,
    ExecutionId,
    IndexId,
)
from winston.sources.base import SourceAdapter, SourceResult


class SyntheticAdapter(SourceAdapter[dict]):
    """Synthetic adapter for offline testing with fixture data.
    
    Implements the synthetic calculator formula from the spec:
        L[d] = L[parent] + x[d] + carry[parent]
        carry[d] = q[d]
        state[d] = (L[d], carry[d])
        Initial state: (100, 0)
    """
    
    def __init__(self, profile_data: dict[str, Any]):
        """Initialize with profile data.
        
        Args:
            profile_data: Loaded profile YAML data
        """
        self._profile = profile_data
        self._indices = {idx["id"]: idx for idx in profile_data.get("indices", [])}
        self._calendars = {cal["id"]: cal for cal in profile_data.get("calendars", [])}
        self._golden = profile_data.get("golden_values", {})
    
    @property
    def source_type(self) -> str:
        return "synthetic"
    
    def is_available(self) -> bool:
        return True
    
    def query(self, **kwargs: Any) -> SourceResult:
        """Execute a synthetic query.
        
        Supported query types:
        - get_execution: Get execution for index/date
        - get_state: Get state artifact for execution
        - calculate: Run synthetic calculation
        """
        query_type = kwargs.get("query_type")
        
        if query_type == "get_execution":
            return self._get_execution(**kwargs)
        elif query_type == "get_state":
            return self._get_state(**kwargs)
        elif query_type == "calculate":
            return self._calculate(**kwargs)
        else:
            return self._error_result(f"Unknown query type: {query_type}")
    
    def _get_execution(
        self,
        index_id: str,
        business_date: str,
        scenario: str = "original",
        **kwargs: Any,
    ) -> SourceResult:
        """Get execution data for an index and date."""
        golden = self._golden.get(scenario, self._golden.get("original", {}))
        index_golden = golden.get(index_id, {})
        date_data = index_golden.get(business_date)
        
        if date_data is None:
            return self._error_result(f"No data for {index_id}/{business_date}")
        
        execution_id = f"{index_id}_{business_date}_{scenario}"
        
        return self._success_result({
            "execution_id": execution_id,
            "index_id": index_id,
            "business_date": business_date,
            "scenario": scenario,
            "status": "succeeded",
            "state": date_data,
        })
    
    def _get_state(
        self,
        execution_id: str,
        **kwargs: Any,
    ) -> SourceResult:
        """Get state artifact for an execution."""
        # Parse execution_id to get index/date/scenario
        parts = execution_id.rsplit("_", 2)
        if len(parts) != 3:
            return self._error_result(f"Invalid execution_id: {execution_id}")
        
        index_id, business_date, scenario = parts
        
        golden = self._golden.get(scenario, self._golden.get("original", {}))
        index_golden = golden.get(index_id, {})
        date_data = index_golden.get(business_date)
        
        if date_data is None:
            return self._error_result(f"No state for execution: {execution_id}")
        
        return self._success_result({
            "execution_id": execution_id,
            "state": {
                "level": date_data.get("level"),
                "carry": date_data.get("carry", 0),
            },
        })
    
    def _calculate(
        self,
        index_id: str,
        business_date: str,
        parent_state: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SourceResult:
        """Run synthetic calculation.
        
        Formula:
            L[d] = L[parent] + x[d] + carry[parent]
            carry[d] = q[d]
        """
        index_def = self._indices.get(index_id)
        if index_def is None:
            return self._error_result(f"Unknown index: {index_id}")
        
        formula = index_def.get("formula", {})
        formula_type = formula.get("type")
        
        if formula_type == "synthetic_additive":
            return self._calculate_additive(
                index_id, business_date, parent_state, inputs, formula
            )
        elif formula_type == "synthetic_multiplier":
            return self._calculate_multiplier(
                index_id, business_date, inputs, formula
            )
        elif formula_type == "synthetic_constant":
            return self._success_result({
                "level": formula.get("value"),
                "carry": 0,
            })
        else:
            return self._error_result(f"Unknown formula type: {formula_type}")
    
    def _calculate_additive(
        self,
        index_id: str,
        business_date: str,
        parent_state: dict[str, Any] | None,
        inputs: dict[str, Any] | None,
        formula: dict[str, Any],
    ) -> SourceResult:
        """Calculate using additive formula."""
        # Get initial state if no parent
        if parent_state is None:
            initial = formula.get("initial_state", {})
            parent_level = initial.get("level", 100)
            parent_carry = initial.get("carry", 0)
        else:
            parent_level = parent_state.get("level", 100)
            parent_carry = parent_state.get("carry", 0)
        
        # Get inputs
        inputs = inputs or {}
        x = inputs.get("x", 1)
        q = inputs.get("q", 0)
        
        # Calculate
        level = parent_level + x + parent_carry
        carry = q
        
        return self._success_result({
            "level": level,
            "carry": carry,
            "inputs": {"x": x, "q": q},
            "parent": {"level": parent_level, "carry": parent_carry},
        })
    
    def _calculate_multiplier(
        self,
        index_id: str,
        business_date: str,
        inputs: dict[str, Any] | None,
        formula: dict[str, Any],
    ) -> SourceResult:
        """Calculate using multiplier formula (dependent index)."""
        source_level = (inputs or {}).get("source_level")
        if source_level is None:
            return self._error_result("Missing source_level input")
        
        multiplier = formula.get("multiplier", 2)
        level = source_level * multiplier
        
        return self._success_result({
            "level": level,
            "carry": 0,
            "inputs": {"source_level": source_level, "multiplier": multiplier},
        })
    
    def _success_result(self, data: Any) -> SourceResult:
        """Create a successful result."""
        return SourceResult(
            data=data,
            receipt=CollectionReceipt(
                source_type="synthetic",
                source_scope="synthetic_profile",
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.COMPLETE,
            ),
        )
    
    def _error_result(self, message: str) -> SourceResult:
        """Create an error result."""
        return SourceResult(
            data={"error": message},
            receipt=CollectionReceipt(
                source_type="synthetic",
                source_scope="synthetic_profile",
                local_request_id=uuid4().hex,
                collection_started_at=datetime.now(timezone.utc),
                collection_completed_at=datetime.now(timezone.utc),
                status=CompletionStatus.FAILED,
                warnings=[message],
            ),
        )
