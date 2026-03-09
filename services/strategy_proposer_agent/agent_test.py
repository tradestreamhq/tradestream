"""
Tests for the Strategy Proposer Agent.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.strategy_proposer_agent.agent import StrategyProposerAgent


VALID_SPEC = {
    "name": "ema_rsi_momentum",
    "indicators": {
        "EMA": {"period": 20},
        "RSI": {"period": 14},
    },
    "entry_conditions": {
        "ema_rising": "EMA is rising over last 3 bars",
        "rsi_oversold": "RSI crosses above 30",
    },
    "exit_conditions": {
        "rsi_overbought": "RSI crosses above 70",
        "ema_falling": "EMA is falling over last 3 bars",
    },
    "parameters": {
        "ema_period": 20,
        "rsi_period": 14,
    },
    "description": "Momentum strategy combining EMA trend with RSI oversold entries.",
}


class TestStrategyProposerAgent:
    """Test cases for the Strategy Proposer Agent."""

    @pytest.fixture
    def agent(self):
        """Create a StrategyProposerAgent with mocked OpenAI client."""
        return StrategyProposerAgent(
            openrouter_api_key="test-key",
            mcp_strategy_url="http://localhost:8080",
        )

    @pytest.fixture
    def mock_session(self):
        """Create a mock MCP ClientSession."""
        session = AsyncMock()
        return session

    def _mock_mcp_response(self, data):
        """Create a mock MCP tool call response."""
        mock_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = json.dumps(data, default=str)
        mock_result.content = [mock_content]
        return mock_result

    @pytest.mark.asyncio
    async def test_get_existing_strategies(self, agent, mock_session):
        """Test fetching existing strategy types."""
        mock_session.call_tool.return_value = self._mock_mcp_response(
            ["macd", "rsi", "bollinger"]
        )

        result = await agent._get_existing_strategies(mock_session)

        assert result == ["macd", "rsi", "bollinger"]
        mock_session.call_tool.assert_called_once_with(
            "list_strategy_types", {}
        )

    @pytest.mark.asyncio
    async def test_get_performance_context(self, agent, mock_session):
        """Test fetching performance context."""
        top_strategies = [
            {"spec_name": "macd", "impl_id": "abc", "score": 2.0}
        ]
        bottom_strategies = [
            {"spec_name": "rsi_basic", "impl_id": "def", "score": -0.5}
        ]

        mock_session.call_tool.side_effect = [
            self._mock_mcp_response(top_strategies),
            self._mock_mcp_response(bottom_strategies),
        ]

        result = await agent._get_performance_context(mock_session)

        assert len(result["top"]) == 1
        assert len(result["bottom"]) == 1
        assert result["top"][0]["spec_name"] == "macd"

    def test_validate_spec_valid(self, agent):
        """Test validation with a valid spec."""
        assert agent._validate_spec(VALID_SPEC) is True

    def test_validate_spec_missing_field(self, agent):
        """Test validation with missing required field."""
        invalid = {k: v for k, v in VALID_SPEC.items() if k != "name"}
        assert agent._validate_spec(invalid) is False

    def test_validate_spec_empty_name(self, agent):
        """Test validation with empty name."""
        invalid = {**VALID_SPEC, "name": ""}
        assert agent._validate_spec(invalid) is False

    def test_validate_spec_bad_indicators(self, agent):
        """Test validation with non-dict indicators."""
        invalid = {**VALID_SPEC, "indicators": "not a dict"}
        assert agent._validate_spec(invalid) is False

    def test_validate_spec_bad_entry_conditions(self, agent):
        """Test validation with non-dict entry_conditions."""
        invalid = {**VALID_SPEC, "entry_conditions": "not a dict"}
        assert agent._validate_spec(invalid) is False

    def test_validate_spec_bad_exit_conditions(self, agent):
        """Test validation with non-dict exit_conditions."""
        invalid = {**VALID_SPEC, "exit_conditions": ["not", "a", "dict"]}
        assert agent._validate_spec(invalid) is False

    @patch.object(StrategyProposerAgent, "_generate_strategy_spec")
    @patch.object(StrategyProposerAgent, "_check_novelty")
    @pytest.mark.asyncio
    async def test_run_success(
        self, mock_novelty, mock_generate, agent, mock_session
    ):
        """Test full successful run cycle."""
        # Mock MCP calls
        mock_session.call_tool.side_effect = [
            # list_strategy_types
            self._mock_mcp_response(["macd", "rsi"]),
            # get_top_strategies (top)
            self._mock_mcp_response([{"spec_name": "macd", "impl_id": "a", "score": 2.0}]),
            # get_top_strategies (bottom)
            self._mock_mcp_response([{"spec_name": "rsi", "impl_id": "b", "score": -0.5}]),
            # create_spec
            self._mock_mcp_response({"spec_id": "new-uuid"}),
        ]

        mock_generate.return_value = VALID_SPEC
        mock_novelty.return_value = {
            "similarity_score": 30,
            "reason": "Novel combination",
            "is_novel": True,
        }

        result = await agent.run(mock_session)

        assert result is not None
        assert result["spec_id"] == "new-uuid"

    @patch.object(StrategyProposerAgent, "_generate_strategy_spec")
    @pytest.mark.asyncio
    async def test_run_generation_fails(
        self, mock_generate, agent, mock_session
    ):
        """Test run when LLM fails to generate spec."""
        mock_session.call_tool.side_effect = [
            self._mock_mcp_response(["macd"]),
            self._mock_mcp_response([]),
            self._mock_mcp_response([]),
        ]

        mock_generate.return_value = None

        result = await agent.run(mock_session)
        assert result is None

    @patch.object(StrategyProposerAgent, "_generate_strategy_spec")
    @patch.object(StrategyProposerAgent, "_check_novelty")
    @pytest.mark.asyncio
    async def test_run_rejected_not_novel(
        self, mock_novelty, mock_generate, agent, mock_session
    ):
        """Test run when spec is rejected for being too similar."""
        mock_session.call_tool.side_effect = [
            self._mock_mcp_response(["macd", "rsi"]),
            self._mock_mcp_response([]),
            self._mock_mcp_response([]),
        ]

        mock_generate.return_value = VALID_SPEC
        mock_novelty.return_value = {
            "similarity_score": 85,
            "reason": "Very similar to existing RSI strategy",
            "is_novel": False,
        }

        result = await agent.run(mock_session)
        assert result is None

    @patch.object(StrategyProposerAgent, "_generate_strategy_spec")
    @pytest.mark.asyncio
    async def test_run_invalid_spec(
        self, mock_generate, agent, mock_session
    ):
        """Test run when generated spec fails validation."""
        mock_session.call_tool.side_effect = [
            self._mock_mcp_response(["macd"]),
            self._mock_mcp_response([]),
            self._mock_mcp_response([]),
        ]

        mock_generate.return_value = {"name": "", "indicators": {}}

        result = await agent.run(mock_session)
        assert result is None

    def test_generate_strategy_spec(self, agent):
        """Test LLM strategy spec generation."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(VALID_SPEC)
        mock_response.choices = [mock_choice]
        agent.client = MagicMock()
        agent.client.chat.completions.create.return_value = mock_response

        result = agent._generate_strategy_spec(["macd", "rsi"], {"top": [], "bottom": []})

        assert result is not None
        assert result["name"] == "ema_rsi_momentum"
        agent.client.chat.completions.create.assert_called_once()
        call_kwargs = agent.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-3-5-sonnet"
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_check_novelty(self, agent):
        """Test LLM novelty check."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "similarity_score": 25,
            "reason": "Unique combination",
            "is_novel": True,
        })
        mock_response.choices = [mock_choice]
        agent.client = MagicMock()
        agent.client.chat.completions.create.return_value = mock_response

        result = agent._check_novelty(VALID_SPEC, ["macd", "rsi"])

        assert result["is_novel"] is True
        assert result["similarity_score"] == 25

    def test_check_novelty_failure(self, agent):
        """Test novelty check when LLM returns empty."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response.choices = [mock_choice]
        agent.client = MagicMock()
        agent.client.chat.completions.create.return_value = mock_response

        result = agent._check_novelty(VALID_SPEC, ["macd"])

        assert result["is_novel"] is False
        assert result["similarity_score"] == 100
