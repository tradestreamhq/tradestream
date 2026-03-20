import React from "react";
import type { OpportunityFactors } from "../types";

interface ScoreBreakdownProps {
  factors: OpportunityFactors;
  totalScore: number;
}

const FACTOR_CONFIG = [
  { key: "confidence" as const, label: "Confidence", maxContribution: 25, format: (v: number) => `${(v * 100).toFixed(0)}%` },
  { key: "expected_return" as const, label: "Expected Return", maxContribution: 30, format: (v: number) => `+${(v * 100).toFixed(1)}%` },
  { key: "consensus" as const, label: "Strategy Consensus", maxContribution: 20, format: (v: number) => `${(v * 100).toFixed(0)}%` },
  { key: "volatility" as const, label: "Volatility", maxContribution: 15, format: (v: number) => `${(v * 100).toFixed(1)}%` },
  { key: "freshness" as const, label: "Freshness", maxContribution: 10, format: (v: number) => `${v}m ago` },
];

export function ScoreBreakdown({ factors, totalScore }: ScoreBreakdownProps) {
  return (
    <div className="score-breakdown" aria-label="Score breakdown" role="list">
      <div className="score-breakdown-header">Score Breakdown</div>
      {FACTOR_CONFIG.map(({ key, label, maxContribution, format }) => {
        const factor = factors[key];
        const percentage = Math.min(100, (factor.contribution / maxContribution) * 100);
        return (
          <div
            className="score-factor"
            key={key}
            role="listitem"
            aria-label={`${label}: ${format(factor.value)}, contributing ${factor.contribution.toFixed(1)} points`}
          >
            <span className="factor-label">{label}</span>
            <span className="factor-value">{format(factor.value)}</span>
            <div
              className="score-bar-container"
              role="progressbar"
              aria-valuenow={percentage}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${label} contribution`}
            >
              <div className="score-bar" style={{ width: `${percentage}%` }} />
            </div>
            <span className="score-contribution">+{factor.contribution.toFixed(1)} pts</span>
          </div>
        );
      })}
      <div className="score-total">Total: {totalScore.toFixed(1)} pts</div>
    </div>
  );
}
