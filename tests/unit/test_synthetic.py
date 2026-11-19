"""Unit tests for synthetic source adapter."""

import pytest

from winston.sources.synthetic import SyntheticAdapter
from winston.domain import CompletionStatus


@pytest.fixture
def synthetic_profile() -> dict:
    """Sample synthetic profile data."""
    return {
        "profile_id": "synthetic",
        "indices": [
            {
                "id": "DEMO",
                "environment": "synthetic",
                "formula": {
                    "type": "synthetic_additive",
                    "initial_state": {"level": 100, "carry": 0},
                },
            },
            {
                "id": "DEMO_DEPENDENT",
                "formula": {
                    "type": "synthetic_multiplier",
                    "source_index": "DEMO",
                    "source_date": "D3",
                    "multiplier": 2,
                },
            },
            {
                "id": "DEMO_CONSTANT",
                "formula": {
                    "type": "synthetic_constant",
                    "value": 500,
                },
            },
        ],
        "golden_values": {
            "original": {
                "DEMO": {
                    "D1": {"level": 101, "carry": 0, "x": 1, "q": 0},
                    "D2": {"level": 102, "carry": 0, "x": 1, "q": 0},
                    "D3": {"level": 103, "carry": 0, "x": 1, "q": 0},
                    "D4": {"level": 104, "carry": 0, "x": 1, "q": 0},
                    "D5": {"level": 105, "carry": 0, "x": 1, "q": 0},
                },
                "DEMO_DEPENDENT": {
                    "D3": {"level": 206},
                },
            },
            "corrected": {
                "DEMO": {
                    "D1": {"level": 101, "carry": 0},
                    "D2": {"level": 102, "carry": 5},
                    "D3": {"level": 108, "carry": 0},
                    "D4": {"level": 109, "carry": 0},
                    "D5": {"level": 110, "carry": 0},
                },
                "DEMO_DEPENDENT": {
                    "D3": {"level": 216},
                },
            },
        },
    }


class TestSyntheticAdapter:
    """Test SyntheticAdapter functionality."""
    
    def test_source_type(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        assert adapter.source_type == "synthetic"
    
    def test_is_available(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        assert adapter.is_available()
    
    def test_get_execution_original(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        result = adapter.query(
            query_type="get_execution",
            index_id="DEMO",
            business_date="D1",
            scenario="original",
        )
        
        assert result.is_complete
        assert result.data["state"]["level"] == 101
        assert result.data["state"]["carry"] == 0
    
    def test_get_execution_corrected(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        result = adapter.query(
            query_type="get_execution",
            index_id="DEMO",
            business_date="D3",
            scenario="corrected",
        )
        
        assert result.is_complete
        assert result.data["state"]["level"] == 108  # Corrected value
    
    def test_get_execution_not_found(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        result = adapter.query(
            query_type="get_execution",
            index_id="DEMO",
            business_date="D99",
            scenario="original",
        )
        
        assert not result.is_complete
        assert result.receipt.status == CompletionStatus.FAILED
    
    def test_calculate_additive(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        # D1 calculation (no parent)
        result = adapter.query(
            query_type="calculate",
            index_id="DEMO",
            business_date="D1",
            inputs={"x": 1, "q": 0},
        )
        
        assert result.is_complete
        # L = 100 (initial) + 1 (x) + 0 (carry) = 101
        assert result.data["level"] == 101
        assert result.data["carry"] == 0
    
    def test_calculate_additive_with_parent(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        # D2 calculation with D1 as parent
        result = adapter.query(
            query_type="calculate",
            index_id="DEMO",
            business_date="D2",
            parent_state={"level": 101, "carry": 0},
            inputs={"x": 1, "q": 0},
        )
        
        assert result.is_complete
        # L = 101 + 1 + 0 = 102
        assert result.data["level"] == 102
        assert result.data["carry"] == 0
    
    def test_calculate_with_carry(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        # D3 calculation with D2 having carry=5 (corrected scenario)
        result = adapter.query(
            query_type="calculate",
            index_id="DEMO",
            business_date="D3",
            parent_state={"level": 102, "carry": 5},
            inputs={"x": 1, "q": 0},
        )
        
        assert result.is_complete
        # L = 102 + 1 + 5 = 108
        assert result.data["level"] == 108
        assert result.data["carry"] == 0
    
    def test_calculate_multiplier(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        result = adapter.query(
            query_type="calculate",
            index_id="DEMO_DEPENDENT",
            business_date="D3",
            inputs={"source_level": 103},
        )
        
        assert result.is_complete
        # Level = 103 * 2 = 206
        assert result.data["level"] == 206
    
    def test_calculate_constant(self, synthetic_profile):
        adapter = SyntheticAdapter(synthetic_profile)
        
        result = adapter.query(
            query_type="calculate",
            index_id="DEMO_CONSTANT",
            business_date="D1",
        )
        
        assert result.is_complete
        assert result.data["level"] == 500
    
    def test_golden_values_original(self, synthetic_profile):
        """Verify golden values match spec for original scenario."""
        adapter = SyntheticAdapter(synthetic_profile)
        
        expected = {
            "D1": 101,
            "D2": 102,
            "D3": 103,
            "D4": 104,
            "D5": 105,
        }
        
        for date, expected_level in expected.items():
            result = adapter.query(
                query_type="get_execution",
                index_id="DEMO",
                business_date=date,
                scenario="original",
            )
            assert result.data["state"]["level"] == expected_level, f"D{date} mismatch"
    
    def test_golden_values_corrected(self, synthetic_profile):
        """Verify golden values match spec for corrected scenario."""
        adapter = SyntheticAdapter(synthetic_profile)
        
        expected = {
            "D1": 101,
            "D2": 102,  # Level unchanged
            "D3": 108,  # 102 + 1 + 5 = 108
            "D4": 109,  # 108 + 1 + 0 = 109
            "D5": 110,  # 109 + 1 + 0 = 110
        }
        
        for date, expected_level in expected.items():
            result = adapter.query(
                query_type="get_execution",
                index_id="DEMO",
                business_date=date,
                scenario="corrected",
            )
            assert result.data["state"]["level"] == expected_level, f"{date} mismatch"
    
    def test_dependent_index_golden(self, synthetic_profile):
        """Verify dependent index golden values."""
        adapter = SyntheticAdapter(synthetic_profile)
        
        # Original: 2 * 103 = 206
        result = adapter.query(
            query_type="get_execution",
            index_id="DEMO_DEPENDENT",
            business_date="D3",
            scenario="original",
        )
        assert result.data["state"]["level"] == 206
        
        # Corrected: 2 * 108 = 216
        result = adapter.query(
            query_type="get_execution",
            index_id="DEMO_DEPENDENT",
            business_date="D3",
            scenario="corrected",
        )
        assert result.data["state"]["level"] == 216
