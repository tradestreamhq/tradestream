#!/usr/bin/env python3
"""
Tests for Strategy Confidence Scorer.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add the current directory to the Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import StrategyConfidenceScorer, StrategyConfidenceScore


class TestStrategyConfidenceScorer:
    """Test cases for StrategyConfidenceScorer."""
    
    @pytest.fixture
    def scorer(self):
        """Create a scorer instance with mock database."""
        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "user": "test",
            "password": "test"
        }
        return StrategyConfidenceScorer(db_config)
    
    @pytest.fixture
    def mock_pool(self):
        """Create a mock connection pool."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        return pool, conn
    
    def test_calculate_confidence_score_performance_dominant(self, scorer):
        """Test that performance score dominates the calculation."""
        result = scorer._calculate_confidence_score(
            performance_score=0.9,
            discovery_count=10,
            days_since_discovery=5,
            max_discovery_count=100,
            recency_days=30
        )
        
        # Performance should be 0.9 * 0.6 = 0.54
        assert result['performance'] == pytest.approx(0.54, abs=0.01)
        assert result['total'] > 0.5  # Performance should dominate
        
    def test_calculate_confidence_score_frequency_component(self, scorer):
        """Test frequency component calculation."""
        result = scorer._calculate_confidence_score(
            performance_score=0.5,
            discovery_count=50,
            days_since_discovery=10,
            max_discovery_count=100,
            recency_days=30
        )
        
        # Frequency should be (50/100) * 0.25 = 0.125
        assert result['frequency'] == pytest.approx(0.125, abs=0.01)
        
    def test_calculate_confidence_score_recency_component(self, scorer):
        """Test recency component calculation."""
        result = scorer._calculate_confidence_score(
            performance_score=0.5,
            discovery_count=10,
            days_since_discovery=5,
            max_discovery_count=100,
            recency_days=30
        )
        
        # Recency should be (1 - 5/30) * 0.15 = 0.125
        assert result['recency'] == pytest.approx(0.125, abs=0.01)
        
    def test_calculate_confidence_score_old_strategy(self, scorer):
        """Test that old strategies get lower recency scores."""
        result = scorer._calculate_confidence_score(
            performance_score=0.8,
            discovery_count=20,
            days_since_discovery=40,  # Older than recency_days
            max_discovery_count=100,
            recency_days=30
        )
        
        # Recency should be 0 for old strategies
        assert result['recency'] == 0.0
        
    def test_calculate_confidence_score_zero_max_discovery(self, scorer):
        """Test handling of zero max discovery count."""
        result = scorer._calculate_confidence_score(
            performance_score=0.7,
            discovery_count=5,
            days_since_discovery=10,
            max_discovery_count=0,  # Edge case
            recency_days=30
        )
        
        # Frequency should be 0 when max_discovery_count is 0
        assert result['frequency'] == 0.0
        
    @pytest.mark.asyncio
    async def test_get_strategy_statistics(self, scorer, mock_pool):
        """Test getting strategy statistics."""
        pool, conn = mock_pool
        scorer.pool = pool
        
        # Mock the database response
        mock_row = {
            'total_strategies': 100,
            'max_discovery_count': 50,
            'oldest_strategy': '2024-01-01',
            'newest_strategy': '2024-07-01'
        }
        conn.fetchrow.return_value = mock_row
        
        stats = await scorer.get_strategy_statistics()
        
        assert stats['total_strategies'] == 100
        assert stats['max_discovery_count'] == 50
        assert stats['oldest_strategy'] == '2024-01-01'
        assert stats['newest_strategy'] == '2024-07-01'
        
    def test_strategy_confidence_score_dataclass(self):
        """Test StrategyConfidenceScore dataclass."""
        score = StrategyConfidenceScore(
            strategy_id="test-id",
            symbol="BTC/USD",
            strategy_type="SMA_RSI",
            current_score=0.85,
            confidence_score=0.72,
            performance_component=0.51,
            frequency_component=0.125,
            recency_component=0.085,
            discovery_count=25,
            days_since_discovery=10
        )
        
        assert score.strategy_id == "test-id"
        assert score.symbol == "BTC/USD"
        assert score.strategy_type == "SMA_RSI"
        assert score.current_score == 0.85
        assert score.confidence_score == 0.72
        assert score.performance_component == 0.51
        assert score.frequency_component == 0.125
        assert score.recency_component == 0.085
        assert score.discovery_count == 25
        assert score.days_since_discovery == 10


if __name__ == "__main__":
    pytest.main([__file__]) 