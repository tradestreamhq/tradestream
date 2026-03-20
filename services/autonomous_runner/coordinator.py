"""Signal generation coordinator: orchestrates the autonomous pipeline.

Runs the full cycle: fetch sources -> fuse signals -> risk check -> emit.
Integrates retry logic, adaptive scheduling, metrics, and DB persistence.
"""

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from services.autonomous_runner.adaptive_scheduler import AdaptiveScheduler
from services.autonomous_runner.config import Config
from services.autonomous_runner.db_persistence import DecisionPersistence
from services.autonomous_runner.decision_models import AgentDecision
from services.autonomous_runner.metrics import pipeline_metrics
from services.autonomous_runner.retry import RetryConfig, retry_with_backoff
from services.autonomous_runner.risk_manager import RiskManager
from services.autonomous_runner.signal_fusion import (
    FusedSignal,
    SignalAction,
    SourceSignal,
    fuse_signals,
)
from services.shared.circuit_breaker import CircuitBreaker
from services.shared.mcp_client import resolve_and_call

logger = logging.getLogger(__name__)


TOOL_TO_SERVER = {
    "get_top_strategies": "strategy",
    "get_spec": "strategy",
    "get_performance": "strategy",
    "list_strategy_types": "strategy",
    "get_walk_forward": "strategy",
    "get_candles": "market",
    "get_latest_price": "market",
    "get_volatility": "market",
    "get_symbols": "market",
    "get_market_summary": "market",
    "emit_signal": "signal",
    "log_decision": "signal",
    "get_recent_signals": "signal",
    "get_paper_pnl": "signal",
    "get_signal_accuracy": "signal",
}


# Retry config for MCP tool calls (per spec)
MCP_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay_ms=500,
    max_delay_ms=5000,
    backoff_multiplier=2.0,
    jitter_pct=0.10,
)


class SignalCoordinator:
    """Orchestrates the autonomous signal generation pipeline.

    For each symbol:
    1. Polls strategy consensus from strategy MCP
    2. Polls market context from market MCP
    3. Fetches sentiment & prediction market signals
    4. Fuses all signals
    5. Runs risk checks
    6. Emits approved signals
    7. Records all decisions (in-memory + database)
    """

    def __init__(self, config: Config, instance_id: str, db_url: str = ""):
        self.config = config
        self.instance_id = instance_id
        self.risk_manager = RiskManager(config.risk)
        self.llm_circuit_breaker = CircuitBreaker(
            "llm_service",
            failure_threshold=config.circuit_breaker.llm_service.failure_threshold,
            recovery_timeout=config.circuit_breaker.llm_service.recovery_timeout,
        )
        self.mcp_urls = {
            "strategy": config.mcp_strategy_url,
            "market": config.mcp_market_url,
            "signal": config.mcp_signal_url,
        }
        self._executor = ThreadPoolExecutor(max_workers=config.parallel.max_concurrent)
        self._decisions = []  # in-memory log for dashboard
        self._db = DecisionPersistence(db_url)
        self.adaptive = AdaptiveScheduler(
            window_size=config.adaptive.latency_window_size,
            p95_threshold_ms=config.adaptive.p95_threshold_ms,
            p99_threshold_ms=config.adaptive.p99_threshold_ms,
            default_batch_size=config.parallel.max_concurrent,
            reduced_batch_size=config.parallel.min_concurrent,
            default_timeout=config.timeouts.symbol_timeout_seconds,
            extended_timeout=config.timeouts.symbol_timeout_max_seconds,
        )

    def _call_mcp_with_retry(
        self, tool: str, params: dict, tool_calls: list
    ) -> Optional[dict]:
        """Call an MCP tool with retry and metrics tracking."""
        server = TOOL_TO_SERVER.get(tool, "unknown")
        call_start = time.time()

        def on_retry(attempt, error, delay_ms):
            pipeline_metrics.record_tool_retry(tool, server)

        try:
            result = retry_with_backoff(
                resolve_and_call,
                args=(tool, params, TOOL_TO_SERVER, self.mcp_urls),
                kwargs={"return_type": "parsed"},
                config=MCP_RETRY_CONFIG,
                on_retry=on_retry,
            )
        except Exception as e:
            call_ms = int((time.time() - call_start) * 1000)
            pipeline_metrics.record_tool_call(tool, server, call_ms / 1000.0)
            tool_calls.append(
                {
                    "tool": tool,
                    "server": server,
                    "parameters": params,
                    "result": {"error": str(e)},
                    "latency_ms": call_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            raise

        call_ms = int((time.time() - call_start) * 1000)
        pipeline_metrics.record_tool_call(tool, server, call_ms / 1000.0)
        tool_calls.append(
            {
                "tool": tool,
                "server": server,
                "parameters": params,
                "result": (
                    result
                    if not isinstance(result, dict) or "error" not in result
                    else result
                ),
                "latency_ms": call_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return result

    def process_all_symbols(
        self,
        symbols: list,
        batch_size: int = 10,
        symbol_timeout: float = 10.0,
    ) -> list:
        """Process all symbols and return generated signals.

        Uses adaptive scheduling to adjust batch size and timeouts.
        """
        adaptive_state = self.adaptive.get_state()
        if adaptive_state.should_skip_cycle:
            logger.warning("Adaptive scheduler recommends skipping cycle")
            pipeline_metrics.record_signal_skipped("adaptive_p99")
            return []

        effective_batch = min(batch_size, adaptive_state.batch_size)
        effective_timeout = adaptive_state.symbol_timeout_seconds
        pipeline_metrics.set_batch_size(effective_batch)

        all_signals = []
        for i in range(0, len(symbols), effective_batch):
            batch = symbols[i : i + effective_batch]
            for symbol in batch:
                try:
                    result = self._process_symbol(symbol, effective_timeout)
                    if result:
                        all_signals.append(result)
                except Exception as e:
                    logger.error("Failed to process %s: %s", symbol, e)

        return all_signals

    def _process_symbol(self, symbol: str, timeout: float) -> Optional[AgentDecision]:
        """Process a single symbol through the full pipeline."""
        start_time = time.time()
        tool_calls = []

        # Step 1: Gather source signals
        source_signals = []

        # 1a. Strategy consensus
        strategy_signal = self._fetch_strategy_signal(symbol, tool_calls)
        if strategy_signal:
            source_signals.append(strategy_signal)

        # 1b. Market context for regime detection
        market_context, regime_signal = self._fetch_market_regime(symbol, tool_calls)
        if regime_signal:
            source_signals.append(regime_signal)

        # 1c. Sentiment (from market summary)
        sentiment_signal = self._fetch_sentiment_signal(symbol, tool_calls)
        if sentiment_signal:
            source_signals.append(sentiment_signal)

        # Step 2: Fuse signals
        fused = fuse_signals(symbol, source_signals)

        # Step 3: Risk check
        risk_result = self.risk_manager.check_signal(fused)

        # Step 4: Build decision record
        latency_ms = int((time.time() - start_time) * 1000)
        self.adaptive.record_latency(latency_ms)
        pipeline_metrics.record_symbol_processing(symbol, latency_ms / 1000.0)

        decision = AgentDecision(
            symbol=symbol,
            action=fused.action.value,
            confidence=fused.confidence,
            reasoning=fused.reasoning,
            strategy_breakdown=self._build_strategy_breakdown(source_signals),
            market_context=market_context or {},
            tool_calls={
                "calls": tool_calls,
                "tools_called": list({c.get("tool", "") for c in tool_calls}),
                "total_latency_ms": latency_ms,
            },
            latency_ms=latency_ms,
            risk_approved=risk_result.approved,
            risk_rejection_reasons=risk_result.rejection_reasons,
            position_size_pct=risk_result.position_size_pct,
            fusion_agreement_ratio=fused.agreement_ratio,
            conflict_resolution=fused.conflict_resolution_applied,
            source_signals=fused.source_signals,
            validation_status="approved" if risk_result.approved else "rejected",
            validation_warnings=risk_result.warnings,
        )
        decision.compute_opportunity_score()
        decision.validate_jsonb_sizes()

        # Record metrics
        pipeline_metrics.record_signal_generated(symbol, fused.action.value)
        pipeline_metrics.record_confidence(fused.confidence)

        # Step 5: Emit if approved
        if risk_result.approved and fused.action != SignalAction.HOLD:
            self._emit_signal(decision, tool_calls)
            self.risk_manager.record_signal_emitted(symbol)
            pipeline_metrics.record_signal_emitted(symbol, fused.action.value)
        elif not risk_result.approved:
            reason = (
                risk_result.rejection_reasons[0]
                if risk_result.rejection_reasons
                else "unknown"
            )
            pipeline_metrics.record_signal_rejected(symbol, reason[:50])

        # Persist to DB
        db_ok = self._db.persist_decision(decision)
        pipeline_metrics.record_db_persistence(db_ok)

        # In-memory log
        self._decisions.append(decision)
        if len(self._decisions) > 1000:
            self._decisions = self._decisions[-500:]

        logger.info(
            "Symbol %s: %s (conf=%.2f, approved=%s) in %dms",
            symbol,
            fused.action.value,
            fused.confidence,
            risk_result.approved,
            latency_ms,
        )

        return decision

    def _fetch_strategy_signal(
        self, symbol: str, tool_calls: list
    ) -> Optional[SourceSignal]:
        """Fetch strategy consensus signal from strategy MCP."""
        try:
            result = self._call_mcp_with_retry(
                "get_top_strategies",
                {"symbol": symbol, "limit": 10},
                tool_calls,
            )

            if isinstance(result, dict) and "error" in result:
                self.llm_circuit_breaker.record_failure()
                return None

            self.llm_circuit_breaker.record_success()

            # Parse strategy signals
            strategies = (
                result if isinstance(result, list) else result.get("strategies", [])
            )
            if not strategies:
                return None

            buy_count = 0
            sell_count = 0
            total_score = 0.0
            for s in strategies:
                signal_dir = s.get("signal", s.get("direction", "HOLD"))
                if signal_dir == "BUY":
                    buy_count += 1
                elif signal_dir == "SELL":
                    sell_count += 1
                total_score += s.get("score", s.get("confidence", 0.5))

            total = len(strategies)
            avg_score = total_score / total if total > 0 else 0

            if buy_count > sell_count:
                action = SignalAction.BUY
            elif sell_count > buy_count:
                action = SignalAction.SELL
            else:
                action = SignalAction.HOLD

            consensus_ratio = (
                max(buy_count, sell_count, total - buy_count - sell_count) / total
            )
            confidence = min(0.95, max(0.30, consensus_ratio * (0.8 + 0.2 * avg_score)))

            return SourceSignal(
                source="strategy_consensus",
                action=action,
                confidence=confidence,
                metadata={
                    "strategies_count": total,
                    "buy": buy_count,
                    "sell": sell_count,
                },
            )
        except Exception as e:
            logger.warning("Strategy fetch failed for %s: %s", symbol, e)
            self.llm_circuit_breaker.record_failure()
            return None

    def _fetch_market_regime(self, symbol: str, tool_calls: list) -> tuple:
        """Fetch market data and detect regime."""
        market_context = {}
        try:
            result = self._call_mcp_with_retry(
                "get_market_summary",
                {"symbol": symbol},
                tool_calls,
            )

            if isinstance(result, dict) and "error" not in result:
                market_context = result

                # Simple regime detection from market data
                price_change = result.get(
                    "price_change_1h", result.get("change_pct", 0)
                )
                volatility = result.get("volatility", result.get("volatility_1h", 0))
                volume_ratio = result.get("volume_ratio", 1.0)

                # Determine regime signal
                if isinstance(price_change, (int, float)):
                    if price_change > 2 and volume_ratio > 1.5:
                        regime_action = SignalAction.BUY
                        regime_conf = min(0.80, 0.5 + abs(price_change) / 20)
                    elif price_change < -2 and volume_ratio > 1.5:
                        regime_action = SignalAction.SELL
                        regime_conf = min(0.80, 0.5 + abs(price_change) / 20)
                    else:
                        regime_action = SignalAction.HOLD
                        regime_conf = 0.40
                else:
                    regime_action = SignalAction.HOLD
                    regime_conf = 0.30

                return market_context, SourceSignal(
                    source="regime_detection",
                    action=regime_action,
                    confidence=regime_conf,
                    metadata={"price_change": price_change, "volatility": volatility},
                )

        except Exception as e:
            logger.warning("Market fetch failed for %s: %s", symbol, e)

        return market_context, None

    def _fetch_sentiment_signal(
        self, symbol: str, tool_calls: list
    ) -> Optional[SourceSignal]:
        """Derive a basic sentiment signal from recent signal accuracy."""
        try:
            result = self._call_mcp_with_retry(
                "get_recent_signals",
                {"symbol": symbol, "limit": 10},
                tool_calls,
            )

            if isinstance(result, dict) and "error" in result:
                return None

            signals = result if isinstance(result, list) else result.get("signals", [])
            if not signals:
                return None

            # Derive sentiment from recent signal flow
            buy_count = sum(1 for s in signals if s.get("action") == "BUY")
            sell_count = sum(1 for s in signals if s.get("action") == "SELL")
            total = len(signals)

            if buy_count > sell_count:
                action = SignalAction.BUY
            elif sell_count > buy_count:
                action = SignalAction.SELL
            else:
                action = SignalAction.HOLD

            confidence = max(buy_count, sell_count) / total if total > 0 else 0.30
            confidence = min(0.70, max(0.30, confidence))

            return SourceSignal(
                source="sentiment",
                action=action,
                confidence=confidence,
                metadata={"recent_buy": buy_count, "recent_sell": sell_count},
            )
        except Exception as e:
            logger.warning("Sentiment fetch failed for %s: %s", symbol, e)
            return None

    def _build_strategy_breakdown(self, source_signals: list) -> dict:
        """Build strategy breakdown JSONB from source signals."""
        breakdown = {
            "strategies_analyzed": len(source_signals),
            "strategies_bullish": sum(
                1 for s in source_signals if s.action == SignalAction.BUY
            ),
            "strategies_bearish": sum(
                1 for s in source_signals if s.action == SignalAction.SELL
            ),
            "strategies_neutral": sum(
                1 for s in source_signals if s.action == SignalAction.HOLD
            ),
            "breakdown": [
                {
                    "source": s.source,
                    "signal": s.action.value,
                    "confidence": s.confidence,
                    "metadata": s.metadata,
                }
                for s in source_signals
            ],
        }
        return breakdown

    def _emit_signal(self, decision: AgentDecision, tool_calls: list):
        """Emit the approved signal via signal MCP."""
        try:
            self._call_mcp_with_retry(
                "emit_signal",
                {
                    "symbol": decision.symbol,
                    "action": decision.action,
                    "confidence": decision.confidence,
                    "reasoning": decision.reasoning,
                    "strategy_breakdown": decision.strategy_breakdown.get(
                        "breakdown", []
                    ),
                },
                tool_calls,
            )
        except Exception as e:
            logger.error("Failed to emit signal for %s: %s", decision.symbol, e)

    def get_recent_decisions(self, limit: int = 50) -> list:
        """Return recent decisions for the dashboard."""
        return [d.to_dict() for d in self._decisions[-limit:]]

    def get_pipeline_status(self) -> dict:
        """Return pipeline status for the dashboard."""
        adaptive_state = self.adaptive.get_state()
        return {
            "instance_id": self.instance_id,
            "risk_status": self.risk_manager.get_status(),
            "circuit_breaker": self.llm_circuit_breaker.to_dict(),
            "total_decisions": len(self._decisions),
            "recent_decisions_count": min(50, len(self._decisions)),
            "adaptive": {
                "batch_size": adaptive_state.batch_size,
                "symbol_timeout": adaptive_state.symbol_timeout_seconds,
                "p95_ms": adaptive_state.p95_ms,
                "p99_ms": adaptive_state.p99_ms,
                "sample_count": adaptive_state.sample_count,
                "should_skip": adaptive_state.should_skip_cycle,
            },
            "db_persistence": self._db.is_available,
            "metrics": pipeline_metrics.get_summary(),
        }
