"""
Tests for the main strategy consumer application.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.strategy_consumer.main import StrategyConsumerService


class TestStrategyConsumerService:
    """Test cases for StrategyConsumerService."""

    @pytest.fixture
    def service(self):
        """Create a StrategyConsumerService instance for testing."""
        return StrategyConsumerService()

    def test_init(self, service):
        """Test service initialization."""
        assert service.kafka_consumer is None
        assert service.postgres_client is None
        assert service.is_running is False
        assert service.processed_count == 0
        assert service.start_time is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, service):
        """Test successful service initialization."""
        with patch('services.strategy_consumer.main.PostgresClient') as mock_postgres_class, \
             patch('services.strategy_consumer.main.StrategyKafkaConsumer') as mock_kafka_class:
            
            # Mock PostgreSQL client
            mock_postgres = AsyncMock()
            mock_postgres_class.return_value = mock_postgres
            
            # Mock Kafka consumer
            mock_kafka = MagicMock()
            mock_kafka_class.return_value = mock_kafka
            
            await service.initialize()
            
            assert service.postgres_client is not None
            assert service.kafka_consumer is not None
            mock_postgres.connect.assert_called_once()
            mock_postgres.ensure_table_exists.assert_called_once()
            mock_kafka.connect.assert_called_once()
            mock_kafka.set_processor_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_strategies_success(self, service):
        """Test successful strategy processing."""
        mock_postgres = AsyncMock()
        mock_postgres.insert_strategies.return_value = 5
        service.postgres_client = mock_postgres
        
        strategies = [
            {'symbol': 'BTC/USD', 'strategy_type': 'MACD_CROSSOVER'},
            {'symbol': 'ETH/USD', 'strategy_type': 'RSI_EMA_CROSSOVER'},
        ]
        
        await service._process_strategies(strategies)
        
        assert service.processed_count == 5
        mock_postgres.insert_strategies.assert_called_once_with(strategies)

    @pytest.mark.asyncio
    async def test_process_strategies_no_postgres_client(self, service):
        """Test strategy processing without PostgreSQL client."""
        service.postgres_client = None
        
        strategies = [{'symbol': 'BTC/USD'}]
        
        # Should not raise an exception, just log an error
        await service._process_strategies(strategies)
        
        assert service.processed_count == 0

    @pytest.mark.asyncio
    async def test_process_strategies_exception(self, service):
        """Test strategy processing with exception."""
        mock_postgres = AsyncMock()
        mock_postgres.insert_strategies.side_effect = Exception("Database error")
        service.postgres_client = mock_postgres
        
        strategies = [{'symbol': 'BTC/USD'}]
        
        # Should not raise an exception, just log an error
        await service._process_strategies(strategies)
        
        assert service.processed_count == 0

    @pytest.mark.asyncio
    async def test_cleanup(self, service):
        """Test service cleanup."""
        # Mock components
        mock_kafka = MagicMock()
        mock_postgres = AsyncMock()
        
        service.kafka_consumer = mock_kafka
        service.postgres_client = mock_postgres
        service.start_time = 1000.0
        
        with patch('time.time', return_value=1100.0):
            await service.cleanup()
        
        assert service.is_running is False
        mock_kafka.stop.assert_called_once()
        mock_kafka.close.assert_called_once()
        mock_postgres.close.assert_called_once()

    def test_stop(self, service):
        """Test service stop."""
        mock_kafka = MagicMock()
        service.kafka_consumer = mock_kafka
        service.is_running = True
        
        service.stop()
        
        assert service.is_running is False
        mock_kafka.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_not_initialized(self, service):
        """Test running service without initialization."""
        with pytest.raises(RuntimeError, match="Service not properly initialized"):
            await service.run()

    @pytest.mark.asyncio
    async def test_run_success(self, service):
        """Test successful service run."""
        # Mock components
        mock_kafka = AsyncMock()
        mock_postgres = AsyncMock()
        
        service.kafka_consumer = mock_kafka
        service.postgres_client = mock_postgres
        
        # Mock the consume_messages to return immediately
        mock_kafka.consume_messages.return_value = None
        
        with patch('time.time', return_value=1000.0):
            await service.run()
        
        assert service.is_running is False
        mock_kafka.consume_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(self, service):
        """Test service run with keyboard interrupt."""
        # Mock components
        mock_kafka = AsyncMock()
        mock_postgres = AsyncMock()
        
        service.kafka_consumer = mock_kafka
        service.postgres_client = mock_postgres
        
        # Mock the consume_messages to raise KeyboardInterrupt
        mock_kafka.consume_messages.side_effect = KeyboardInterrupt()
        
        with patch('time.time', return_value=1000.0):
            await service.run()
        
        assert service.is_running is False
        mock_kafka.consume_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_exception(self, service):
        """Test service run with exception."""
        # Mock components
        mock_kafka = AsyncMock()
        mock_postgres = AsyncMock()
        
        service.kafka_consumer = mock_kafka
        service.postgres_client = mock_postgres
        
        # Mock the consume_messages to raise an exception
        mock_kafka.consume_messages.side_effect = Exception("Test error")
        
        with patch('time.time', return_value=1000.0):
            with pytest.raises(Exception, match="Test error"):
                await service.run()
        
        assert service.is_running is False
        mock_kafka.consume_messages.assert_called_once() 