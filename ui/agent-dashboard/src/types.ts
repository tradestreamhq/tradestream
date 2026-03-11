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
