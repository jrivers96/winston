"""Unit tests for synthetic calculator - verifies golden values from spec."""

import pytest

from winston.evaluation.calculator import (
    SyntheticCalculator,
    CalculatorState,
    CalculatorInputs,
    DependentCalculator,
    StateResetCalculator,
)
from winston.evaluation.fixtures import GOLDEN_VALUES, verify_golden_values


class TestSyntheticCalculator:
    """Test the synthetic calculator implementation."""
    
    def test_initial_state(self):
        """Test initial state is (100, 0)."""
        state = CalculatorState.initial()
        assert state.level == 100
        assert state.carry == 0
    
    def test_single_step_d1(self):
        """Test D1 calculation: 100 + 1 + 0 = 101."""
        calc = SyntheticCalculator()
        inputs = CalculatorInputs(x=1, q=0)
        
        result = calc.calculate(None, inputs)
        
        assert result.level == 101
        assert result.carry == 0
    
    def test_chain_original_sequence(self):
        """Test original sequence D1-D5 matches golden values."""
        calc = SyntheticCalculator()
        inputs = [CalculatorInputs(x=1, q=0) for _ in range(5)]
        
        states = calc.calculate_chain(inputs)
        
        expected = [101, 102, 103, 104, 105]
        actual = [s.level for s in states]
        assert actual == expected
        
        # All carries should be 0
        carries = [s.carry for s in states]
        assert carries == [0, 0, 0, 0, 0]
    
    def test_chain_with_d2_correction(self):
        """Test D2 q correction: q=5 affects D3-D5."""
        calc = SyntheticCalculator()
        inputs = [
            CalculatorInputs(x=1, q=0),  # D1
            CalculatorInputs(x=1, q=5),  # D2 - corrected
            CalculatorInputs(x=1, q=0),  # D3
            CalculatorInputs(x=1, q=0),  # D4
            CalculatorInputs(x=1, q=0),  # D5
        ]
        
        states = calc.calculate_chain(inputs)
        
        # D1: 100 + 1 + 0 = 101, carry=0
        assert states[0].level == 101
        assert states[0].carry == 0
        
        # D2: 101 + 1 + 0 = 102, carry=5 (from q=5)
        assert states[1].level == 102
        assert states[1].carry == 5
        
        # D3: 102 + 1 + 5 = 108, carry=0
        assert states[2].level == 108
        assert states[2].carry == 0
        
        # D4: 108 + 1 + 0 = 109
        assert states[3].level == 109
        
        # D5: 109 + 1 + 0 = 110
        assert states[4].level == 110
    
    def test_d2_level_unchanged_after_correction(self):
        """Test that D2's level is unchanged, only carry changes."""
        calc = SyntheticCalculator()
        
        # Original
        original = calc.calculate_chain([
            CalculatorInputs(x=1, q=0),  # D1
            CalculatorInputs(x=1, q=0),  # D2
        ])
        
        # Corrected
        corrected = calc.calculate_chain([
            CalculatorInputs(x=1, q=0),  # D1
            CalculatorInputs(x=1, q=5),  # D2 - corrected
        ])
        
        # D2 level should be same
        assert original[1].level == corrected[1].level == 102
        
        # But carry differs
        assert original[1].carry == 0
        assert corrected[1].carry == 5
    
    def test_calculate_with_correction_method(self):
        """Test the calculate_with_correction helper method."""
        calc = SyntheticCalculator()
        inputs = [CalculatorInputs(x=1, q=0) for _ in range(5)]
        corrected_input = CalculatorInputs(x=1, q=5)
        
        original, corrected = calc.calculate_with_correction(
            inputs,
            correction_index=1,  # D2
            corrected_inputs=corrected_input,
        )
        
        # Original should be 101-105
        assert [s.level for s in original] == [101, 102, 103, 104, 105]
        
        # Corrected should be 101, 102, 108, 109, 110
        assert [s.level for s in corrected] == [101, 102, 108, 109, 110]


class TestDependentCalculator:
    """Test the dependent index calculator."""
    
    def test_multiplier_original(self):
        """Test 2x multiplier on original D3 (103) = 206."""
        calc = DependentCalculator(multiplier=2)
        
        result = calc.calculate(103)
        
        assert result == 206
    
    def test_multiplier_corrected(self):
        """Test 2x multiplier on corrected D3 (108) = 216."""
        calc = DependentCalculator(multiplier=2)
        
        result = calc.calculate(108)
        
        assert result == 216


class TestStateResetCalculator:
    """Test the state reset calculator for the reset fixture."""
    
    def test_reset_at_d4_original(self):
        """Test D4 resets to (200, 0), D5 uses q[D2]=0."""
        calc = StateResetCalculator()
        
        # D1-D3 are normal
        d1 = calc.calculate_with_reset(None, CalculatorInputs(x=1, q=0))
        d2 = calc.calculate_with_reset(d1, CalculatorInputs(x=1, q=0))
        d3 = calc.calculate_with_reset(d2, CalculatorInputs(x=1, q=0))
        
        assert d1.level == 101
        assert d2.level == 102
        assert d3.level == 103
        
        # D4 resets
        d4 = calc.calculate_with_reset(
            d3,
            CalculatorInputs(x=1, q=0),
            reset_state=CalculatorState(level=200, carry=0),
        )
        assert d4.level == 200
        assert d4.carry == 0
        
        # D5 uses D4 as parent but lookback to D2 for q
        # q[D2] = 0 in original, so: 200 + 1 + 0 = 201
        d5 = calc.calculate_with_reset(
            d4,
            CalculatorInputs(x=1, q=0),
            lookback_q=d2.carry,  # q[D2] = 0
        )
        assert d5.level == 201
    
    def test_reset_at_d4_corrected(self):
        """Test with D2 q=5, D5 should use lookback q[D2]=5."""
        calc = StateResetCalculator()
        
        d1 = calc.calculate_with_reset(None, CalculatorInputs(x=1, q=0))
        d2 = calc.calculate_with_reset(d1, CalculatorInputs(x=1, q=5))  # q=5
        d3 = calc.calculate_with_reset(d2, CalculatorInputs(x=1, q=0))
        
        assert d2.carry == 5  # q[D2] = 5
        assert d3.level == 108  # 102 + 1 + 5
        
        # D4 resets (unchanged)
        d4 = calc.calculate_with_reset(
            d3,
            CalculatorInputs(x=1, q=0),
            reset_state=CalculatorState(level=200, carry=0),
        )
        assert d4.level == 200
        
        # D5 uses lookback q[D2]=5: 200 + 1 + 5 = 206
        d5 = calc.calculate_with_reset(
            d4,
            CalculatorInputs(x=1, q=0),
            lookback_q=d2.carry,  # q[D2] = 5
        )
        assert d5.level == 206


class TestGoldenValues:
    """Test that all golden values are verified."""
    
    def test_verify_all_golden_values(self):
        """Run the golden value verification."""
        results = verify_golden_values()
        
        # All tests should pass
        for test_name, passed in results.items():
            assert passed, f"Golden value test '{test_name}' failed"
    
    def test_golden_values_original(self):
        """Verify GOLDEN_VALUES dict has expected original values."""
        original = GOLDEN_VALUES["original"]["DEMO"]
        
        assert original["D1"]["level"] == 101
        assert original["D2"]["level"] == 102
        assert original["D3"]["level"] == 103
        assert original["D4"]["level"] == 104
        assert original["D5"]["level"] == 105
    
    def test_golden_values_corrected(self):
        """Verify GOLDEN_VALUES dict has expected corrected values."""
        corrected = GOLDEN_VALUES["corrected"]["DEMO"]
        
        assert corrected["D1"]["level"] == 101
        assert corrected["D2"]["level"] == 102
        assert corrected["D2"]["carry"] == 5
        assert corrected["D3"]["level"] == 108
        assert corrected["D4"]["level"] == 109
        assert corrected["D5"]["level"] == 110
    
    def test_dependent_golden_values(self):
        """Verify dependent index golden values."""
        original = GOLDEN_VALUES["original"]["DEMO_DEPENDENT"]
        corrected = GOLDEN_VALUES["corrected"]["DEMO_DEPENDENT"]
        
        assert original["D3"]["level"] == 206  # 2 * 103
        assert corrected["D3"]["level"] == 216  # 2 * 108
