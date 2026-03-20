import type { Signal, ToolCallEvent, ToolResultEvent } from "@/api/types";
import { cn, formatPrice, formatTime, formatPercent } from "@/utils/utils";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { ToolCallLog } from "./ToolCallLog";
import { StrategyBreakdown } from "./StrategyBreakdown";

interface SignalCardProps {
  signal: Signal;
  expanded?: boolean;
  isFocused?: boolean;
  onToggle?: () => void;
  toolEvents?: (ToolCallEvent | ToolResultEvent)[];
}

const actionStyles: Record<string, string> = {
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

const actionBorderColor: Record<string, string> = {
  BUY: "border-l-emerald-500",
  SELL: "border-l-red-500",
  HOLD: "border-l-amber-500",
};

export function SignalCard({
  signal,
  expanded,
  isFocused = false,
  onToggle,
  toolEvents = [],
}: SignalCardProps) {
  return (
    <article
      className={cn(
        "card animate-signal-enter border-l-4 transition-all hover:border-slate-600",
        actionBorderColor[signal.action] || "border-l-slate-500",
        isFocused && "ring-2 ring-brand-400 ring-offset-2 ring-offset-surface"
      )}
      aria-label={`${signal.action} signal for ${signal.symbol} with opportunity score ${signal.opportunity_score}`}
      aria-expanded={expanded}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className={tierStyles[signal.opportunity_tier]}>
            {signal.opportunity_tier}
          </span>
          <span className="text-sm font-bold text-slate-400">
            {signal.opportunity_score}
          </span>
          <span className="text-lg font-bold text-white">{signal.symbol}</span>
          <span className={actionStyles[signal.action]}>{signal.action}</span>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span>Confidence: {formatPercent(signal.confidence)}</span>
          <time dateTime={signal.timestamp}>{formatTime(signal.timestamp)}</time>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
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
        <div>
          <span className="text-slate-500">Strategies </span>
          <span className="font-medium text-white">
            {signal.strategies_bullish}/{signal.strategies_analyzed} bullish
          </span>
        </div>
      </div>

      {/* Expand toggle */}
      {onToggle && (
        <button
          onClick={onToggle}
          className="mt-3 flex items-center gap-1 text-sm text-brand-400 hover:text-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 focus:ring-offset-surface-card"
          aria-expanded={expanded}
          aria-controls={`signal-details-${signal.signal_id}`}
        >
          {expanded ? "\u25B2 Hide reasoning" : "\u25BC Show reasoning"}
        </button>
      )}

      {/* Expanded details */}
      {expanded && (
        <div
          id={`signal-details-${signal.signal_id}`}
          className="mt-4 animate-expand-in space-y-5 border-t border-slate-700/50 pt-4"
        >
          {/* Score Breakdown */}
          {signal.opportunity_factors && (
            <ScoreBreakdown
              factors={signal.opportunity_factors}
              totalScore={signal.opportunity_score}
            />
          )}

          {/* Tool Calls */}
          {toolEvents.length > 0 && <ToolCallLog events={toolEvents} />}

          {/* Analysis */}
          <section aria-labelledby={`analysis-${signal.signal_id}`}>
            <h4
              id={`analysis-${signal.signal_id}`}
              className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500"
            >
              Analysis
            </h4>
            <p className="text-sm leading-relaxed text-slate-300">
              {signal.reasoning}
            </p>
          </section>

          {/* Strategy Breakdown */}
          {signal.strategy_breakdown && signal.strategy_breakdown.length > 0 && (
            <StrategyBreakdown strategies={signal.strategy_breakdown} />
          )}

          {/* Outcome */}
          {signal.outcome && (
            <div className="flex items-center gap-3">
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
