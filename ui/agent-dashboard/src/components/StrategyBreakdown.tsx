import React from "react";
import type { StrategySignal } from "../types";

interface StrategyBreakdownProps {
  strategies: StrategySignal[];
}

export function StrategyBreakdown({ strategies }: StrategyBreakdownProps) {
  if (!strategies.length) return null;

  return (
    <div className="strategy-breakdown" aria-label="Strategy breakdown">
      <div className="strategy-breakdown-header">Strategy Breakdown</div>
      <div className="strategy-list" role="list">
        {strategies.map((strategy) => (
          <div
            className={`strategy-item ${strategy.agrees ? "agrees" : "disagrees"}`}
            key={strategy.name}
            role="listitem"
          >
            <span className={`strategy-icon ${strategy.agrees ? "agree" : "disagree"}`}>
              {strategy.agrees ? "\u2713" : "\u2717"}
            </span>
            <span className="strategy-name">{strategy.name}</span>
            <span className={`strategy-action ${strategy.action.toLowerCase()}`}>
              {strategy.action}
            </span>
            <span className="strategy-weight">{strategy.weight.toFixed(2)}</span>
            <span className="strategy-reasoning">{strategy.reasoning}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
