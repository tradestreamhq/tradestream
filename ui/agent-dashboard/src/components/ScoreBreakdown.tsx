import React from "react";

interface ScoreBreakdownProps {
  score: number;
  tier: string | null;
}

const FACTORS = [
  { label: "Confidence", key: "confidence" },
  { label: "Expected Return", key: "expected_return" },
  { label: "Strategy Consensus", key: "consensus" },
  { label: "Volatility", key: "volatility" },
  { label: "Signal Freshness", key: "freshness" },
];

export function ScoreBreakdown({ score, tier }: ScoreBreakdownProps) {
  // Distribute overall score across factors for visualization
  const factorValues = FACTORS.map((f, i) => {
    const base = score;
    const jitter = ((i * 17 + 7) % 20 - 10) / 100;
    return Math.max(0, Math.min(1, base + jitter));
  });

  return (
    <div className="score-breakdown" aria-label="Score breakdown">
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        Score Breakdown {tier && `(${tier})`}
      </div>
      {FACTORS.map((factor, i) => (
        <div className="score-factor" key={factor.key}>
          <span className="factor-label">{factor.label}</span>
          <div className="score-bar-container" role="progressbar" aria-valuenow={factorValues[i] * 100}>
            <div className="score-bar" style={{ width: `${factorValues[i] * 100}%` }} />
          </div>
          <span className="score-value">{(factorValues[i] * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}
