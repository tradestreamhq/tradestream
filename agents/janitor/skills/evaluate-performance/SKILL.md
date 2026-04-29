---
name: "evaluate-performance"
description: "Evaluate trading strategy performance against retirement thresholds — Sharpe ratio, accuracy, signal count, age, trend, and alternatives. Use when the janitor agent assesses strategy implementations for potential retirement."
---

# Evaluate Performance

Assess strategy implementations against retirement criteria. All thresholds must be met before a strategy is flagged as a retirement candidate.

## Retirement Thresholds

All criteria must be true simultaneously for a strategy to qualify for retirement:

| Factor | Threshold | Rationale |
|--------|-----------|-----------|
| **Signal count** | ≥ 100 forward-test signals | Ensures statistical significance |
| **Age** | ≥ 6 months since creation | Allows for market regime variation |
| **Sharpe ratio** | < 0.5 | Below acceptable risk-adjusted return |
| **Accuracy** | < 45% win rate | Below acceptable signal quality |
| **Trend** | Declining performance trajectory | Not recovering or improving |
| **Alternatives** | Better option exists (Sharpe ≥ 1.0) | Ensures replacement capacity |

## Workflow

1. **Query candidates**: Fetch all active strategy implementations with their performance metrics
2. **Filter by maturity**: Exclude strategies with < 100 signals or < 6 months age — these need more time
3. **Evaluate thresholds**: Check each remaining strategy against Sharpe ratio, accuracy, and trend criteria
4. **Verify alternatives**: For each failing strategy, confirm at least one replacement exists with Sharpe ≥ 1.0
5. **Check protections**: Exclude CANONICAL specs (the original 70 strategies) — these are never retired
6. **Generate recommendations**: Produce a retirement recommendation with per-factor reasoning for each candidate

## Safety Rules

- Never retire CANONICAL specs
- Never retire more than 50 implementations per run
- Never retire more than 10% of active strategies at once
- Respect grace periods for recently modified strategies

## Output

Return a retirement recommendation with reasoning for each candidate, including which thresholds were breached and the proposed replacement strategy.
