export interface Signal {
  signal_id: string;
  symbol: string;
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  opportunity_score: number;
  opportunity_tier: "HOT" | "GOOD" | "NEUTRAL" | "LOW";
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  strategies_analyzed: number;
  strategies_bullish: number;
  strategies_bearish: number;
  reasoning: string;
  outcome?: "WIN" | "LOSS" | "PENDING";
  pnl_percent?: number;
  timestamp: string;
}

export interface Strategy {
  strategy_id: string;
  name: string;
  description: string;
  win_rate: number;
  total_signals: number;
  sharpe_ratio: number;
  total_return: number;
  max_drawdown: number;
  avg_return_per_trade: number;
  active: boolean;
}

export interface User {
  user_id: string;
  email: string;
  name: string;
  plan: "free" | "starter" | "pro" | "enterprise";
  signals_used: number;
  signals_limit: number;
  subscription_status: "active" | "cancelled" | "past_due";
  current_period_end: string;
}

export interface PricingPlan {
  id: string;
  name: string;
  price: number;
  interval: "month" | "year";
  signals_limit: number;
  features: string[];
  highlighted?: boolean;
}

export interface SignalFilters {
  symbols?: string[];
  actions?: ("BUY" | "SELL" | "HOLD")[];
  outcomes?: ("WIN" | "LOSS" | "PENDING")[];
  minConfidence?: number;
  dateFrom?: string;
  dateTo?: string;
}

export interface PerformanceStats {
  total_signals: number;
  win_rate: number;
  avg_return: number;
  total_return: number;
  active_strategies: number;
  subscribers: number;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}
