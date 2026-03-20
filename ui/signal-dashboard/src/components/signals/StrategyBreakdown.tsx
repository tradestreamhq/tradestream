import type { StrategySignal } from "@/api/types";
import { cn } from "@/utils/utils";

interface StrategyBreakdownProps {
  strategies: StrategySignal[];
}

export function StrategyBreakdown({ strategies }: StrategyBreakdownProps) {
  if (strategies.length === 0) return null;

  return (
    <section aria-labelledby="strategy-breakdown-heading">
      <h4
        id="strategy-breakdown-heading"
        className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500"
      >
        Strategy Breakdown
      </h4>
      <div className="space-y-1.5">
        {strategies.map((s) => (
          <div
            key={s.strategy_name}
            className="flex items-center gap-3 rounded-lg bg-slate-800/30 px-3 py-2 text-sm"
          >
            <span
              className={cn(
                "text-base",
                s.action === "BUY" && "text-emerald-400",
                s.action === "SELL" && "text-red-400",
                s.action === "HOLD" && "text-slate-400"
              )}
              aria-label={s.action === "BUY" ? "Bullish" : s.action === "SELL" ? "Bearish" : "Neutral"}
            >
              {s.action === "BUY" ? "\u2713" : s.action === "SELL" ? "\u2717" : "\u2014"}
            </span>
            <span className="w-36 shrink-0 font-medium text-white">
              {s.strategy_name}
            </span>
            <span
              className={cn(
                "w-10 shrink-0 text-center font-medium",
                s.action === "BUY" ? "text-emerald-400" : s.action === "SELL" ? "text-red-400" : "text-slate-400"
              )}
            >
              {s.action}
            </span>
            <span className="w-10 shrink-0 text-center text-slate-400">
              {s.score.toFixed(2)}
            </span>
            <span className="truncate text-slate-500">{s.reason}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
