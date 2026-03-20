import type { OpportunityFactors } from "@/api/types";

interface ScoreBreakdownProps {
  factors: OpportunityFactors;
  totalScore: number;
}

const FACTOR_CONFIG = [
  { key: "confidence" as const, label: "Confidence", max: 25, fmt: pctFmt },
  { key: "expected_return" as const, label: "Expected Return", max: 30, fmt: returnFmt },
  { key: "consensus" as const, label: "Strategy Consensus", max: 20, fmt: pctFmt },
  { key: "volatility" as const, label: "Volatility", max: 15, fmt: pctDecFmt },
  { key: "freshness" as const, label: "Freshness", max: 10, fmt: freshFmt },
] as const;

function pctDecFmt(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function pctFmt(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

function returnFmt(v: number): string {
  return `+${(v * 100).toFixed(1)}%`;
}

function freshFmt(v: number): string {
  return `${v}m ago`;
}

export function ScoreBreakdown({ factors, totalScore }: ScoreBreakdownProps) {
  return (
    <section aria-labelledby="score-breakdown-heading">
      <h4
        id="score-breakdown-heading"
        className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500"
      >
        Score Breakdown
      </h4>
      <div className="space-y-2" role="list" aria-label="Score factors">
        {FACTOR_CONFIG.map(({ key, label, max, fmt }) => {
          const factor = factors[key];
          const pct = Math.min((factor.contribution / max) * 100, 100);
          return (
            <div
              key={key}
              className="flex items-center gap-3 text-sm"
              role="listitem"
              aria-label={`${label}: ${fmt(factor.value)}, contributing ${factor.contribution.toFixed(1)} points`}
            >
              <span className="w-32 shrink-0 text-slate-400">{label}</span>
              <span className="w-14 shrink-0 text-right font-medium text-white">
                {fmt(factor.value)}
              </span>
              <div className="flex-1">
                <div
                  className="h-1.5 rounded-full bg-slate-700"
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="h-1.5 rounded-full bg-brand-500 transition-all duration-300"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
              <span className="w-16 shrink-0 text-right text-xs text-slate-500">
                +{factor.contribution.toFixed(1)} pts
              </span>
            </div>
          );
        })}
        <div className="mt-2 border-t border-slate-700/50 pt-2 text-right text-sm font-semibold text-white">
          Total: {totalScore.toFixed(1)} pts
        </div>
      </div>
    </section>
  );
}
