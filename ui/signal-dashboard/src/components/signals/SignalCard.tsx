import type { Signal } from "@/api/types";
import { cn, formatPrice, formatTime, formatPercent } from "@/lib/utils";

interface SignalCardProps {
  signal: Signal;
  expanded?: boolean;
  onToggle?: () => void;
}

export function SignalCard({ signal, expanded, onToggle }: SignalCardProps) {
  const actionStyles = {
    BUY: "badge-buy",
    SELL: "badge-sell",
    HOLD: "badge-hold",
  };

  const tierStyles: Record<string, string> = {
    HOT: "badge-hot",
    GOOD: "badge-good",
    NEUTRAL: "badge bg-slate-600/30 text-slate-400",
    LOW: "badge bg-slate-700/30 text-slate-500",
  };

  return (
    <article
      className="card transition-all hover:border-slate-600"
      aria-label={`${signal.action} signal for ${signal.symbol}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className={tierStyles[signal.opportunity_tier]}>
            {signal.opportunity_tier}
          </span>
          <span className="text-lg font-bold text-white">{signal.symbol}</span>
          <span className={actionStyles[signal.action]}>{signal.action}</span>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span>Score: {signal.opportunity_score}</span>
          <time dateTime={signal.timestamp}>{formatTime(signal.timestamp)}</time>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <div>
          <span className="text-slate-500">Confidence </span>
          <span className="font-medium text-white">
            {formatPercent(signal.confidence)}
          </span>
        </div>
        <div>
          <span className="text-slate-500">Entry </span>
          <span className="font-medium text-white">
            {formatPrice(signal.entry_price)}
          </span>
        </div>
        <div>
          <span className="text-slate-500">Stop Loss </span>
          <span className="font-medium text-red-400">
            {formatPrice(signal.stop_loss)}
          </span>
        </div>
        <div>
          <span className="text-slate-500">Take Profit </span>
          <span className="font-medium text-emerald-400">
            {formatPrice(signal.take_profit)}
          </span>
        </div>
      </div>

      {/* Expand toggle */}
      {onToggle && (
        <button
          onClick={onToggle}
          className="mt-3 text-sm text-brand-400 hover:text-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 focus:ring-offset-surface-card"
          aria-expanded={expanded}
        >
          {expanded ? "Hide details" : "Show details"}
        </button>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 border-t border-slate-700/50 pt-4">
          <div className="mb-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <div>
              <span className="text-slate-500">Strategies Analyzed </span>
              <span className="text-white">{signal.strategies_analyzed}</span>
            </div>
            <div>
              <span className="text-slate-500">Bullish </span>
              <span className="text-emerald-400">
                {signal.strategies_bullish}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Bearish </span>
              <span className="text-red-400">{signal.strategies_bearish}</span>
            </div>
          </div>

          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Reasoning
          </h4>
          <p className="text-sm leading-relaxed text-slate-300">
            {signal.reasoning}
          </p>

          {signal.outcome && (
            <div className="mt-3 flex items-center gap-3">
              <span
                className={cn(
                  "badge",
                  signal.outcome === "WIN" && "bg-emerald-500/20 text-emerald-400",
                  signal.outcome === "LOSS" && "bg-red-500/20 text-red-400",
                  signal.outcome === "PENDING" && "bg-amber-500/20 text-amber-400"
                )}
              >
                {signal.outcome}
              </span>
              {signal.pnl_percent != null && (
                <span
                  className={cn(
                    "text-sm font-medium",
                    signal.pnl_percent >= 0
                      ? "text-emerald-400"
                      : "text-red-400"
                  )}
                >
                  {signal.pnl_percent >= 0 ? "+" : ""}
                  {(signal.pnl_percent * 100).toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
