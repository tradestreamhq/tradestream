import React, { useMemo } from "react";
import type { Signal } from "../types";

interface PerformanceSidebarProps {
  signals: Signal[];
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

  const sorted = [...signals].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  for (const s of signals) {
    if (s.action === "BUY") buyCount++;
    else if (s.action === "SELL") sellCount++;
    else holdCount++;

    const hasPnl = s.entry_price != null && s.current_price != null;
    const pnlPercent = hasPnl
      ? s.action === "SELL"
        ? ((s.entry_price! - s.current_price!) / s.entry_price!) * 100
        : ((s.current_price! - s.entry_price!) / s.entry_price!) * 100
      : 0;

    if (hasPnl && pnlPercent > 0) wins++;
    else if (hasPnl && pnlPercent < 0) losses++;

    if (!hasPnl) {
      if (s.action === "BUY") openBuys++;
      else if (s.action === "SELL") openSells++;
    }

    if (hasPnl && s.timestamp.startsWith(today)) {
      closedToday++;
      todayPnl += pnlPercent;
    }
  }

  // Streak: count consecutive same outcomes from most recent
  let streak = 0;
  for (const s of sorted) {
    const hasPnl = s.entry_price != null && s.current_price != null;
    if (!hasPnl) continue;
    const pnl = s.action === "SELL"
      ? ((s.entry_price! - s.current_price!) / s.entry_price!) * 100
      : ((s.current_price! - s.entry_price!) / s.entry_price!) * 100;
    const isWin = pnl > 0;
    if (streak === 0) {
      streak = isWin ? 1 : -1;
    } else if ((streak > 0 && isWin) || (streak < 0 && !isWin)) {
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

export function PerformanceSidebar({ signals }: PerformanceSidebarProps) {
  const stats = useMemo(() => computeStats(signals), [signals]);

  return (
    <aside className="performance-sidebar" aria-label="Strategy performance">
      {/* Today's P&L */}
      <div className="perf-card">
        <div className="perf-card-label">Today&apos;s P&amp;L</div>
        <div className={`perf-card-value ${stats.todayPnl >= 0 ? "positive" : "negative"}`}>
          {stats.todayPnl >= 0 ? "+" : ""}{stats.todayPnl.toFixed(2)}%
        </div>
        <div className="perf-card-sub">
          {stats.closedToday} closed signal{stats.closedToday !== 1 ? "s" : ""} today
        </div>
      </div>

      {/* Win Rate */}
      <div className="perf-card">
        <div className="perf-card-label">Win Rate</div>
        <div className="perf-card-value">
          {stats.totalResolved > 0
            ? `${((stats.wins / stats.totalResolved) * 100).toFixed(1)}%`
            : "N/A"}
        </div>
        <div className="perf-card-sub">
          {stats.wins}W / {stats.losses}L of {stats.totalResolved} resolved
        </div>
      </div>

      {/* Current Streak */}
      <div className="perf-card">
        <div className="perf-card-label">Current Streak</div>
        <div className={`perf-card-value ${stats.streak > 0 ? "positive" : stats.streak < 0 ? "negative" : ""}`}>
          {stats.streak > 0 ? `${stats.streak}W` : stats.streak < 0 ? `${Math.abs(stats.streak)}L` : "--"}
        </div>
        <div className="perf-card-sub">
          consecutive {stats.streak >= 0 ? "wins" : "losses"}
        </div>
      </div>

      {/* Open Positions */}
      <div className="perf-card">
        <div className="perf-card-label">Open Positions</div>
        <div className="perf-card-value">{stats.openPositions}</div>
        <div className="perf-card-sub">
          <span className="text-green">{stats.openBuys} buys</span>{" "}
          <span className="text-red">{stats.openSells} sells</span>
        </div>
      </div>

      {/* Total Signals */}
      <div className="perf-card">
        <div className="perf-card-label">Total Signals</div>
        <div className="perf-card-value">{signals.length}</div>
        <div className="perf-card-sub">
          {stats.buyCount} BUY · {stats.sellCount} SELL · {stats.holdCount} HOLD
        </div>
      </div>
    </aside>
  );
}
