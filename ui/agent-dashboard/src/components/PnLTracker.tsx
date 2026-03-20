import React, { useMemo } from "react";
import type { Signal } from "../types";

interface PnLTrackerProps {
  signals: Signal[];
}

export function PnLTracker({ signals }: PnLTrackerProps) {
  const pnlData = useMemo(() => {
    const withPnl = signals.filter((s) => s.entry_price != null && s.current_price != null);
    let totalPnl = 0;
    let winners = 0;
    let losers = 0;

    const entries = withPnl.map((s) => {
      const entry = s.entry_price!;
      const current = s.current_price!;
      const pnlPercent = s.action === "SELL"
        ? ((entry - current) / entry) * 100
        : ((current - entry) / entry) * 100;
      const pnlAbsolute = s.action === "SELL" ? entry - current : current - entry;

      totalPnl += pnlPercent;
      if (pnlPercent > 0) winners++;
      else if (pnlPercent < 0) losers++;

      return { signal: s, pnlPercent, pnlAbsolute };
    });

    const winRate = entries.length > 0 ? (winners / entries.length) * 100 : 0;

    return { entries, totalPnl, winners, losers, winRate };
  }, [signals]);

  return (
    <div className="pnl-tracker" aria-label="P&L Tracker">
      <div className="pnl-header">
        <span className="pnl-title">Live P&L</span>
        <span className={`pnl-total ${pnlData.totalPnl >= 0 ? "positive" : "negative"}`}>
          {pnlData.totalPnl >= 0 ? "+" : ""}{pnlData.totalPnl.toFixed(2)}%
        </span>
      </div>
      <div className="pnl-stats">
        <div className="pnl-stat">
          <span className="pnl-stat-label">Win Rate</span>
          <span className="pnl-stat-value">{pnlData.winRate.toFixed(1)}%</span>
        </div>
        <div className="pnl-stat">
          <span className="pnl-stat-label positive">Winners</span>
          <span className="pnl-stat-value">{pnlData.winners}</span>
        </div>
        <div className="pnl-stat">
          <span className="pnl-stat-label negative">Losers</span>
          <span className="pnl-stat-value">{pnlData.losers}</span>
        </div>
      </div>
      {pnlData.entries.length > 0 && (
        <div className="pnl-entries" role="list" aria-label="P&L entries">
          {pnlData.entries.slice(0, 10).map(({ signal, pnlPercent }) => (
            <div className="pnl-entry" key={signal.signal_id} role="listitem">
              <span className={`pnl-action ${signal.action.toLowerCase()}`}>{signal.action}</span>
              <span className="pnl-symbol">{signal.symbol}</span>
              <span className={`pnl-value ${pnlPercent >= 0 ? "positive" : "negative"}`}>
                {pnlPercent >= 0 ? "+" : ""}{pnlPercent.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
