"""Synthetic calculator for demonstration and testing.

Implements the formula from the spec:
    L[d] = L[parent] + x[d] + carry[parent]
    carry[d] = q[d]
    state[d] = (L[d], carry[d])
    Initial state: (100, 0)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class CalculatorState:
    """State produced by the synthetic calculator."""
    
    level: int
    carry: int
    
    def to_dict(self) -> Dict[str, int]:
        return {"level": self.level, "carry": self.carry}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalculatorState":
        return cls(
            level=int(data.get("level", 0)),
            carry=int(data.get("carry", 0)),
        )
    
    @classmethod
    def initial(cls) -> "CalculatorState":
        """Initial state: (100, 0)"""
        return cls(level=100, carry=0)


@dataclass
class CalculatorInputs:
    """Inputs for a single calculation step."""
    
    x: int = 1  # Additive input
    q: int = 0  # Carry input (becomes next carry)
    
    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "q": self.q}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalculatorInputs":
        return cls(
            x=int(data.get("x", 1)),
            q=int(data.get("q", 0)),
        )


class SyntheticCalculator:
    """Calculator implementing the synthetic DEMO index formula.
    
    Formula:
        L[d] = L[parent] + x[d] + carry[parent]
        carry[d] = q[d]
        
    Initial state: (level=100, carry=0)
    """
    
    def calculate(
        self,
        parent_state: Optional[CalculatorState],
        inputs: CalculatorInputs,
    ) -> CalculatorState:
        """Calculate the next state.
        
        Args:
            parent_state: State from previous calculation, or None for initial
            inputs: Inputs for this calculation
            
        Returns:
            New state
        """
        if parent_state is None:
            parent_state = CalculatorState.initial()
        
        # L[d] = L[parent] + x[d] + carry[parent]
        new_level = parent_state.level + inputs.x + parent_state.carry
        
        # carry[d] = q[d]
        new_carry = inputs.q
        
        return CalculatorState(level=new_level, carry=new_carry)
    
    def calculate_chain(
        self,
        input_sequence: list[CalculatorInputs],
        initial_state: Optional[CalculatorState] = None,
    ) -> list[CalculatorState]:
        """Calculate a chain of states.
        
        Args:
            input_sequence: Inputs for each step (D1, D2, ...)
            initial_state: Optional initial state (defaults to (100, 0))
            
        Returns:
            List of states for each step
        """
        states = []
        parent = initial_state
        
        for inputs in input_sequence:
            state = self.calculate(parent, inputs)
            states.append(state)
            parent = state
        
        return states
    
    def calculate_with_correction(
        self,
        input_sequence: list[CalculatorInputs],
        correction_index: int,
        corrected_inputs: CalculatorInputs,
        initial_state: Optional[CalculatorState] = None,
    ) -> Tuple[list[CalculatorState], list[CalculatorState]]:
        """Calculate original and corrected chains.
        
        Args:
            input_sequence: Original inputs
            correction_index: Which step to correct (0-indexed)
            corrected_inputs: Corrected inputs for that step
            initial_state: Optional initial state
            
        Returns:
            Tuple of (original_states, corrected_states)
        """
        # Original calculation
        original = self.calculate_chain(input_sequence, initial_state)
        
        # Corrected calculation
        corrected_sequence = list(input_sequence)
        corrected_sequence[correction_index] = corrected_inputs
        corrected = self.calculate_chain(corrected_sequence, initial_state)
        
        return original, corrected


class DependentCalculator:
    """Calculator for the dependent index (2x source level)."""
    
    def __init__(self, multiplier: int = 2):
        self.multiplier = multiplier
    
    def calculate(self, source_level: int) -> int:
        """Calculate dependent index level.
        
        Args:
            source_level: Level from source index
            
        Returns:
            Dependent index level
        """
        return source_level * self.multiplier


class StateResetCalculator:
    """Calculator with state reset capability.
    
    For the state reset fixture where D4 unconditionally resets
    but D5 still uses q[D2] via lookback.
    """
    
    def calculate_with_reset(
        self,
        parent_state: Optional[CalculatorState],
        inputs: CalculatorInputs,
        reset_state: Optional[CalculatorState] = None,
        lookback_q: Optional[int] = None,
    ) -> CalculatorState:
        """Calculate with optional reset and lookback.
        
        Args:
            parent_state: Normal parent state
            inputs: Inputs for this step
            reset_state: If provided, use this instead of calculating
            lookback_q: If provided, use this q value instead of parent carry
            
        Returns:
            New state
        """
        if reset_state is not None:
            return reset_state
        
        if parent_state is None:
            parent_state = CalculatorState.initial()
        
        # Use lookback_q if provided, otherwise use parent carry
        carry_to_use = lookback_q if lookback_q is not None else parent_state.carry
        
        # L[d] = L[parent] + x[d] + carry
        new_level = parent_state.level + inputs.x + carry_to_use
        new_carry = inputs.q
        
        return CalculatorState(level=new_level, carry=new_carry)
