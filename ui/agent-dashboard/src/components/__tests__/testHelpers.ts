import type { AgentEvent, Signal, OpportunityFactors, StrategySignal } from "../../types";

export function createMockSignal(overrides: Partial<Signal> = {}): Signal {
  const factors: OpportunityFactors = {
    confidence: { value: 0.82, contribution: 20.5 },
    expected_return: { value: 0.032, contribution: 30.0 },
    consensus: { value: 0.8, contribution: 16.0 },
    volatility: { value: 0.021, contribution: 10.5 },
    freshness: { value: 2, contribution: 10.0 },
  };

  const strategies: StrategySignal[] = [
    { name: "RSI_REVERSAL", action: "BUY", weight: 0.89, reasoning: "RSI oversold recovery", agrees: true },
    { name: "MACD_CROSS", action: "BUY", weight: 0.85, reasoning: "Bullish crossover", agrees: true },
    { name: "VOLUME_BREAKOUT", action: "SELL", weight: 0.65, reasoning: "Volume declining", agrees: false },
  ];

  return {
    signal_id: "sig-1",
    symbol: "ETH/USD",
    action: "BUY",
    confidence: 0.82,
    opportunity_score: 87,
    opportunity_tier: "HOT",
    opportunity_factors: factors,
    reasoning: "Strong consensus among top strategies.",
    timestamp: "2026-03-20T12:34:56Z",
    strategies_bullish: 4,
    strategies_analyzed: 5,
    strategy_breakdown: strategies,
    ...overrides,
  };
}

export function createMockEvent(overrides: Partial<AgentEvent> = {}): AgentEvent {
  return {
    event_type: "signal",
    id: "ev-1",
    signal_id: "sig-1",
    agent_name: "signal-generator",
    decision_type: null,
    score: 0.87,
    tier: "high",
    reasoning: "Bullish setup detected",
    tool_calls: null,
    model_used: null,
    latency_ms: null,
    tokens_used: null,
    success: true,
    error_message: null,
    created_at: "2026-03-20T12:34:56Z",
    ...overrides,
  };
}
