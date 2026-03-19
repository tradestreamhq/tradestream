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

export type StrategyCategory =
  | "trend_following"
  | "mean_reversion"
  | "momentum"
  | "breakout"
  | "multi_indicator"
  | "volatility"
  | "statistical";

export interface MarketplaceListing {
  id: string;
  strategy_id: string;
  name: string;
  author: string;
  description: string;
  category: StrategyCategory;
  tags: string[];
  performance_stats: Record<string, number>;
  price: number;
  subscribers_count: number;
  avg_rating: number;
  rating_count: number;
  created_at: string;
  live_metrics?: {
    total_return_pct: number;
    sharpe_ratio: number;
    win_rate: number;
    max_drawdown_pct: number;
    trade_count: number;
    consistency_score: number;
  };
}

export interface LeaderboardEntry {
  strategy_id: string;
  period: string;
  rank: number;
  total_return_pct: number;
  sharpe_ratio: number;
  win_rate: number;
  max_drawdown_pct: number;
  trade_count: number;
  consistency_score: number;
  snapshot_date: string;
  name?: string;
  category?: string;
  author?: string;
}

export interface CategoryInfo {
  name: string;
  label: string;
  description: string;
}

export interface MarketplaceFilters {
  category?: string;
  search?: string;
  order_by?: string;
}
