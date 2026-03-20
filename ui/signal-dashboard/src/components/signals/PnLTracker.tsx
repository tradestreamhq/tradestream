import type { Signal } from "@/api/types";
import { useMemo } from "react";
import { cn } from "@/utils/utils";

interface PnLTrackerProps {
  signals: Signal[];
}

export function PnLTracker({ signals }: PnLTrackerProps) {
  const { realizedPnl, unrealizedCount } = useMemo(() => {
    let realized = 0;
    let unrealized = 0;
    for (const s of signals) {
      if (s.outcome && s.outcome !== "PENDING" && s.pnl_percent != null) {
        realized += s.pnl_percent;
      } else if (!s.outcome || s.outcome === "PENDING") {
        unrealized++;
      }
    }
    return { realizedPnl: realized, unrealizedCount: unrealized };
  }, [signals]);

  return (
    <div
      className="flex items-center gap-4 rounded-lg border border-slate-700/50 bg-surface-card px-4 py-2"
      aria-label="P&L tracker"
    >
      <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
        P&amp;L
      </span>
      <span
        className={cn(
          "text-sm font-bold",
          realizedPnl >= 0 ? "text-emerald-400" : "text-red-400"
        )}
      >
        {realizedPnl >= 0 ? "+" : ""}
        {(realizedPnl * 100).toFixed(2)}%
      </span>
      <span className="text-xs text-slate-500">
        {unrealizedCount} open
      </span>
    </div>
  );
}
