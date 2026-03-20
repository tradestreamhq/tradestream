"""Agent decision schema models for persisting autonomous decisions."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

MAX_TOOL_CALLS = 50
MAX_TOOL_CALL_RESULT_SIZE = 5 * 1024  # 5KB
MAX_TOOL_CALLS_TOTAL_SIZE = 100 * 1024  # 100KB
MAX_STRATEGY_BREAKDOWN_SIZE = 50 * 1024  # 50KB
MAX_OPPORTUNITY_FACTORS_SIZE = 10 * 1024  # 10KB
MAX_MARKET_CONTEXT_SIZE = 10 * 1024  # 10KB


@dataclass
class AgentDecision:
    """Structured record of an autonomous decision with full reasoning chain."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    # Signal identification
    symbol: str = ""
    action: str = ""  # BUY, SELL, HOLD

    # Confidence and scoring
    confidence: float = 0.0
    opportunity_score: float = 0.0
    opportunity_tier: str = ""  # HOT, GOOD, NEUTRAL, LOW
    opportunity_factors: dict = field(default_factory=dict)

    # Input context
    query: Optional[str] = None
    symbols_analyzed: list = field(default_factory=list)

    # Reasoning and analysis
    reasoning: str = ""
    strategy_breakdown: dict = field(default_factory=dict)
    market_context: dict = field(default_factory=dict)

    # Tool execution trace
    tool_calls: dict = field(default_factory=lambda: {"calls": [], "tools_called": []})

    # Validation
    validation_status: str = ""
    validation_warnings: list = field(default_factory=list)
    max_position_size: Optional[float] = None

    # Model and performance
    model_used: str = ""
    agent_type: str = "autonomous_runner"
    latency_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    # Risk check result
    risk_approved: bool = False
    risk_rejection_reasons: list = field(default_factory=list)
    position_size_pct: float = 0.0

    # Fusion metadata
    fusion_agreement_ratio: float = 0.0
    conflict_resolution: str = ""
    source_signals: list = field(default_factory=list)

    def validate_jsonb_sizes(self):
        """Validate JSONB field sizes and truncate if necessary."""
        self.tool_calls = _validate_tool_calls(self.tool_calls)
        self.strategy_breakdown = _truncate_if_needed(
            self.strategy_breakdown, MAX_STRATEGY_BREAKDOWN_SIZE
        )
        self.opportunity_factors = _truncate_if_needed(
            self.opportunity_factors, MAX_OPPORTUNITY_FACTORS_SIZE
        )
        self.market_context = _truncate_if_needed(
            self.market_context, MAX_MARKET_CONTEXT_SIZE
        )

    def compute_opportunity_tier(self) -> str:
        """Compute opportunity tier from score."""
        if self.opportunity_score >= 80:
            return "HOT"
        elif self.opportunity_score >= 60:
            return "GOOD"
        elif self.opportunity_score >= 40:
            return "NEUTRAL"
        return "LOW"

    def compute_opportunity_score(self) -> float:
        """Calculate opportunity score from 5 weighted factors per spec.

        Factors and weights:
        - confidence: 0.25
        - expected_return: 0.30
        - consensus: 0.20
        - volatility: 0.15
        - freshness: 0.10
        """
        factors = {}

        # Confidence factor (25%)
        conf_norm = min(1.0, self.confidence)
        factors["confidence"] = {
            "value": self.confidence,
            "normalized": conf_norm,
            "contribution": conf_norm * 25,
            "weight": 0.25,
        }

        # Expected return factor (30%) - estimated from confidence and action
        expected_return = self._estimate_expected_return()
        er_norm = (
            min(1.0, max(0.0, expected_return / 0.05)) if expected_return > 0 else 0
        )
        factors["expected_return"] = {
            "value": round(expected_return, 4),
            "normalized": round(er_norm, 4),
            "contribution": round(er_norm * 30, 2),
            "weight": 0.30,
        }

        # Consensus factor (20%)
        consensus_norm = self.fusion_agreement_ratio
        factors["consensus"] = {
            "value": self.fusion_agreement_ratio,
            "normalized": consensus_norm,
            "contribution": round(consensus_norm * 20, 2),
            "weight": 0.20,
        }

        # Volatility factor (15%) - from market context
        volatility = self._extract_volatility()
        vol_norm = min(1.0, max(0.0, volatility / 0.05)) if volatility > 0 else 0.5
        factors["volatility"] = {
            "value": round(volatility, 4),
            "normalized": round(vol_norm, 4),
            "contribution": round(vol_norm * 15, 2),
            "weight": 0.15,
        }

        # Freshness factor (10%) - always fresh for autonomous
        factors["freshness"] = {
            "value": 1.0,
            "normalized": 1.0,
            "contribution": 10.0,
            "weight": 0.10,
        }

        total = round(sum(f["contribution"] for f in factors.values()), 2)
        factors["total_score"] = total

        self.opportunity_factors = factors
        self.opportunity_score = total
        self.opportunity_tier = self.compute_opportunity_tier()
        return total

    def _estimate_expected_return(self) -> float:
        """Estimate expected return from confidence and market context."""
        if self.action == "HOLD":
            return 0.0
        # Base return proportional to confidence
        base_return = self.confidence * 0.05
        # Adjust by price momentum if available
        price_change = abs(self.market_context.get("price_change_1h", 0) or 0)
        if isinstance(price_change, (int, float)):
            base_return *= 1.0 + min(0.5, price_change / 10.0)
        return base_return

    def _extract_volatility(self) -> float:
        """Extract volatility from market context."""
        vol = self.market_context.get("volatility_1h", 0)
        if isinstance(vol, (int, float)):
            return float(vol)
        return 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "decision_id": self.decision_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "opportunity_score": self.opportunity_score,
            "opportunity_tier": self.opportunity_tier,
            "opportunity_factors": self.opportunity_factors,
            "reasoning": self.reasoning,
            "strategy_breakdown": self.strategy_breakdown,
            "market_context": self.market_context,
            "tool_calls": self.tool_calls,
            "validation_status": self.validation_status,
            "validation_warnings": self.validation_warnings,
            "max_position_size": self.max_position_size,
            "model_used": self.model_used,
            "agent_type": self.agent_type,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat(),
            "risk_approved": self.risk_approved,
            "risk_rejection_reasons": self.risk_rejection_reasons,
            "position_size_pct": self.position_size_pct,
            "fusion_agreement_ratio": self.fusion_agreement_ratio,
            "conflict_resolution": self.conflict_resolution,
            "source_signals": (
                [
                    {
                        "source": s.source,
                        "action": s.action.value,
                        "confidence": s.confidence,
                    }
                    for s in self.source_signals
                ]
                if self.source_signals
                else []
            ),
        }


def _validate_tool_calls(tool_calls: dict) -> dict:
    """Validate and truncate tool calls to fit size constraints."""
    calls = tool_calls.get("calls", [])

    if len(calls) > MAX_TOOL_CALLS:
        tool_calls["truncated"] = True
        tool_calls["original_count"] = len(calls)
        calls = calls[:MAX_TOOL_CALLS]

    for call in calls:
        result_str = json.dumps(call.get("result", {}))
        if len(result_str) > MAX_TOOL_CALL_RESULT_SIZE:
            call["result"] = {"truncated": True, "size": len(result_str)}

    tool_calls["calls"] = calls
    return tool_calls


def _truncate_if_needed(data: dict, max_size: int) -> dict:
    """Truncate a dict if its JSON representation exceeds max_size."""
    serialized = json.dumps(data)
    if len(serialized) <= max_size:
        return data
    return {"truncated": True, "original_size": len(serialized)}
