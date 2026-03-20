export interface AgentEvent {
  event_type: "signal" | "reasoning" | "tool_call" | "decision";
  id: string;
  signal_id: string | null;
  agent_name: string | null;
  decision_type: string | null;
  score: number | null;
  tier: string | null;
  reasoning: string | null;
  tool_calls: ToolCall[] | null;
  model_used: string | null;
  latency_ms: number | null;
  tokens_used: number | null;
  success: boolean | null;
  error_message: string | null;
  created_at: string;
}

export interface ToolCall {
  name: string;
  args?: Record<string, unknown>;
  result?: unknown;
}

export interface ActiveAgent {
  agent_name: string;
  decision_count: number;
  last_active: string;
  avg_latency_ms: number;
  success_count: number;
  failure_count: number;
}

export interface Stats24h {
  total_decisions: number;
  unique_agents: number;
  avg_latency_ms: number;
  successes: number;
  failures: number;
  signals_generated: number;
}

export interface DashboardSummary {
  active_agents: ActiveAgent[];
  stats_24h: Stats24h;
  tier_distribution: Record<string, number>;
  recent_signals: Record<string, unknown>[];
}

export interface AgentDetail {
  agent_name: string;
  decision_types: DecisionTypeDetail[];
  total_decisions: number;
  first_seen: string;
  last_seen: string;
}

export interface DecisionTypeDetail {
  agent_name: string;
  decision_type: string;
  total_decisions: number;
  avg_latency_ms: number;
  min_latency_ms: number;
  max_latency_ms: number;
  avg_tokens: number;
  successes: number;
  failures: number;
  first_seen: string;
  last_seen: string;
}

export type ConnectionStatus = "connected" | "connecting" | "disconnected";

// Signal Stream types (spec-compliant)

export type SignalAction = "BUY" | "SELL" | "HOLD";
export type OpportunityTier = "HOT" | "GOOD" | "NEUTRAL";

export interface OpportunityFactor {
  value: number;
  contribution: number;
}

export interface OpportunityFactors {
  confidence: OpportunityFactor;
  expected_return: OpportunityFactor;
  consensus: OpportunityFactor;
  volatility: OpportunityFactor;
  freshness: OpportunityFactor;
}

export interface StrategySignal {
  name: string;
  action: SignalAction;
  weight: number;
  reasoning: string;
  agrees: boolean;
}

export interface Signal {
  signal_id: string;
  symbol: string;
  action: SignalAction;
  confidence: number;
  opportunity_score: number;
  opportunity_tier: OpportunityTier;
  opportunity_factors: OpportunityFactors;
  reasoning: string;
  timestamp: string;
  strategies_bullish: number;
  strategies_analyzed: number;
  strategy_breakdown: StrategySignal[];
  entry_price?: number;
  current_price?: number;
  pnl?: number;
}

export interface SignalFilters {
  symbols?: string[];
  actions?: SignalAction[];
  minConfidence?: number;
  minOpportunityScore?: number;
}

export interface PnLEntry {
  signal_id: string;
  symbol: string;
  action: SignalAction;
  entry_price: number;
  current_price: number;
  pnl_percent: number;
  pnl_absolute: number;
  timestamp: string;
}
