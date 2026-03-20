import type { Signal } from "@/api/types";
import { useMemo } from "react";
import { cn, formatPercent } from "@/utils/utils";

interface PerformanceSidebarProps {
  signals: Signal[];
}

export function PerformanceSidebar({ signals }: PerformanceSidebarProps) {
  const stats = useMemo(() => computeStats(signals), [signals]);

  return (
    <aside
      className="w-full shrink-0 space-y-4 lg:w-72"
      aria-label="Strategy performance"
    >
      {/* Today's P&L */}
      <div className="card">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Today&apos;s P&amp;L
        </h3>
        <p
          className={cn(
            "text-2xl font-bold",
            stats.todayPnl >= 0 ? "text-emerald-400" : "text-red-400"
          )}
        >
          {stats.todayPnl >= 0 ? "+" : ""}
          {(stats.todayPnl * 100).toFixed(2)}%
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {stats.closedToday} closed signal{stats.closedToday !== 1 ? "s" : ""} today
        </p>
      </div>

      {/* Win Rate */}
      <div className="card">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Win Rate
        </h3>
        <p className="text-2xl font-bold text-white">
          {stats.totalResolved > 0
            ? formatPercent(stats.wins / stats.totalResolved)
            : "N/A"}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {stats.wins}W / {stats.losses}L of {stats.totalResolved} resolved
        </p>
      </div>

      {/* Current Streak */}
      <div className="card">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Current Streak
        </h3>
        <p
          className={cn(
            "text-2xl font-bold",
            stats.streak > 0 ? "text-emerald-400" : stats.streak < 0 ? "text-red-400" : "text-slate-400"
          )}
        >
          {stats.streak > 0 ? `${stats.streak}W` : stats.streak < 0 ? `${Math.abs(stats.streak)}L` : "--"}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          consecutive {stats.streak >= 0 ? "wins" : "losses"}
        </p>
      </div>

      {/* Open Positions */}
      <div className="card">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Open Positions
        </h3>
        <p className="text-2xl font-bold text-white">{stats.openPositions}</p>
        <div className="mt-2 flex gap-3 text-xs">
          <span className="text-emerald-400">{stats.openBuys} buys</span>
          <span className="text-red-400">{stats.openSells} sells</span>
        </div>
      </div>

      {/* Signal Count */}
      <div className="card">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Total Signals
        </h3>
        <p className="text-2xl font-bold text-white">{signals.length}</p>
        <div className="mt-2 flex gap-3 text-xs text-slate-500">
          <span>{stats.buyCount} BUY</span>
          <span>{stats.sellCount} SELL</span>
          <span>{stats.holdCount} HOLD</span>
        </div>
      </div>
    </aside>
  );
}

interface Stats {
  todayPnl: number;
  closedToday: number;
  wins: number;
  losses: number;
  totalResolved: number;
  streak: number;
  openPositions: number;
  openBuys: number;
  openSells: number;
  buyCount: number;
  sellCount: number;
  holdCount: number;
}

function computeStats(signals: Signal[]): Stats {
  const today = new Date().toISOString().slice(0, 10);

  let todayPnl = 0;
  let closedToday = 0;
  let wins = 0;
  let losses = 0;
  let openBuys = 0;
  let openSells = 0;
  let buyCount = 0;
  let sellCount = 0;
  let holdCount = 0;

  // Sort by timestamp desc for streak calculation
  const sorted = [...signals].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  for (const s of signals) {
    if (s.action === "BUY") buyCount++;
    else if (s.action === "SELL") sellCount++;
    else holdCount++;

    if (s.outcome === "WIN") wins++;
    else if (s.outcome === "LOSS") losses++;

    if (!s.outcome || s.outcome === "PENDING") {
      if (s.action === "BUY") openBuys++;
      else if (s.action === "SELL") openSells++;
    }

    if (s.outcome && s.outcome !== "PENDING" && s.timestamp.startsWith(today)) {
      closedToday++;
      todayPnl += s.pnl_percent ?? 0;
    }
  }

  // Streak: count consecutive same outcomes from most recent
  let streak = 0;
  for (const s of sorted) {
    if (!s.outcome || s.outcome === "PENDING") continue;
    if (streak === 0) {
      streak = s.outcome === "WIN" ? 1 : -1;
    } else if (
      (streak > 0 && s.outcome === "WIN") ||
      (streak < 0 && s.outcome === "LOSS")
    ) {
      streak += streak > 0 ? 1 : -1;
    } else {
      break;
    }
  }

  return {
    todayPnl,
    closedToday,
    wins,
    losses,
    totalResolved: wins + losses,
    streak,
    openPositions: openBuys + openSells,
    openBuys,
    openSells,
    buyCount,
    sellCount,
    holdCount,
  };
}
