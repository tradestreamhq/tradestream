# Opportunity Scoring Specification

## Goal

Score and rank trading opportunities by perceived upside to surface the best opportunities first, enabling users to focus attention on the most promising signals.

## Target Behavior

Each signal receives an **opportunity score** (0-100) computed from multiple factors. Higher scores indicate higher perceived opportunity.

### Scoring Factors

| Factor | Weight | Range | Description |
|--------|--------|-------|-------------|
| **Confidence** | 25% | 0-1 | Agent's confidence in the signal |
| **Expected Return** | 30% | 0-5% | Historical avg return of triggering strategies |
| **Strategy Consensus** | 20% | 0-100% | % of top strategies agreeing |
| **Volatility Factor** | 15% | 0-3% | Higher volatility = bigger opportunity (capped) |
| **Freshness** | 10% | 0-60 min | More recent signals slightly preferred |

### Opportunity Score Formula

```python
def calculate_opportunity_score(
    confidence: float,           # 0.0 - 1.0
    expected_return: float,      # percentage, e.g., 0.032 for 3.2%
    consensus_pct: float,        # 0.0 - 1.0
    volatility: float,           # hourly volatility, e.g., 0.021
    minutes_ago: int             # signal age in minutes
) -> float:
    """
    Calculate opportunity score (0-100) for a trading signal.

    Returns:
        Float between 0 and 100
    """
    # Normalize expected return (5% return = max score)
    return_score = min(expected_return / 0.05, 1.0)

    # Normalize volatility (3% hourly vol = max score)
    volatility_score = min(volatility / 0.03, 1.0)

    # Freshness decay: 100% at 0 min, 50% at 30 min, 0% at 60 min
    freshness_score = max(0, 1 - (minutes_ago / 60))

    # Weighted sum
    opportunity_score = (
        0.25 * confidence +
        0.30 * return_score +
        0.20 * consensus_pct +
        0.15 * volatility_score +
        0.10 * freshness_score
    ) * 100

    return round(opportunity_score, 1)
```

### Score Tiers

| Tier | Score Range | Visual Indicator | Description |
|------|-------------|------------------|-------------|
| Hot | 80-100 | :fire: | Exceptional opportunity |
| Good | 60-79 | :star: | Above-average opportunity |
| Neutral | 40-59 | :white_circle: | Standard signal |
| Low | 0-39 | :small_blue_diamond: | Below-average opportunity |

### Score Breakdown Display

```
OPPORTUNITY SCORE: 87

Confidence:        82% ████████░░ +20.5 pts
Expected Return:   +3.2% ██████████ +30.0 pts
Strategy Consensus: 80% ████████░░ +16.0 pts
Volatility:        2.1% ███████░░░ +10.5 pts
Freshness:         2m ago █████████░ +10.0 pts
                         ─────────────────────
                         Total: 87.0 pts
```

## Data Requirements

### Inputs per Signal

| Field | Source | Description |
|-------|--------|-------------|
| `confidence` | Signal Generator Agent | Agent's confidence in the signal |
| `expected_return` | Backtest MCP | Avg return of triggering strategies |
| `strategies_bullish` | Signal Generator | Count of bullish strategies |
| `strategies_analyzed` | Signal Generator | Total strategies checked |
| `volatility` | Market Data MCP | Recent hourly volatility |
| `timestamp` | Signal Generator | When signal was generated |

### Expected Return Calculation

```python
def calculate_expected_return(
    strategies: list[StrategySignal],
    signal_action: str  # BUY or SELL
) -> float:
    """
    Calculate expected return based on historical performance
    of the strategies that triggered this signal.
    """
    agreeing_strategies = [
        s for s in strategies
        if s.signal == signal_action
    ]

    if not agreeing_strategies:
        return 0.0

    # Weight by strategy score
    total_weight = sum(s.score for s in agreeing_strategies)
    weighted_return = sum(
        s.historical_avg_return * s.score
        for s in agreeing_strategies
    ) / total_weight

    return weighted_return
```

### Volatility Data

```python
def get_volatility_for_scoring(symbol: str) -> float:
    """
    Get recent volatility from InfluxDB.
    Uses 1-hour timeframe, last 24 candles.
    """
    candles = market_data_mcp.get_candles(
        symbol=symbol,
        timeframe="1h",
        limit=24
    )

    returns = [
        (c.close - c.open) / c.open
        for c in candles
    ]

    return statistics.stdev(returns)
```

## Implementation

### Opportunity Scorer Agent

The Opportunity Scorer is a dedicated OpenCode agent that:
1. Subscribes to `channel:raw-signals` (from Signal Generator)
2. Enriches each signal with opportunity score
3. Publishes scored signals to `channel:scored-signals`

```
┌─────────────────────────────────────────────────────────────┐
│  OPPORTUNITY SCORER AGENT                                  │
│                                                             │
│  Input: Raw signal from Signal Generator                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MCP Tools                                            │   │
│  │  • backtest-mcp: get_historical_performance         │   │
│  │  • market-data-mcp: get_volatility                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Skills                                               │   │
│  │  • score-opportunity: Apply scoring formula          │   │
│  │  • calculate-expected-return: Weight by performance │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Output: Scored signal → Redis channel:scored-signals      │
└─────────────────────────────────────────────────────────────┘
```

### Scored Signal Format

```json
{
  "signal_id": "sig-abc123",
  "symbol": "ETH/USD",
  "action": "BUY",
  "confidence": 0.82,
  "opportunity_score": 87.0,
  "opportunity_tier": "HOT",
  "opportunity_factors": {
    "confidence": { "value": 0.82, "contribution": 20.5 },
    "expected_return": { "value": 0.032, "contribution": 30.0 },
    "consensus": { "value": 0.80, "contribution": 16.0 },
    "volatility": { "value": 0.021, "contribution": 10.5 },
    "freshness": { "value": 2, "contribution": 10.0 }
  },
  "strategies_analyzed": 5,
  "strategies_bullish": 4,
  "top_strategy": "RSI_REVERSAL",
  "reasoning": "Strong consensus among top strategies...",
  "timestamp": "2025-02-01T12:34:56Z"
}
```

## UI Behavior

### Signal List Sorting

Signals are sorted by opportunity score (highest first) by default.

```tsx
const sortedSignals = useMemo(
  () => [...signals].sort((a, b) =>
    b.opportunity_score - a.opportunity_score
  ),
  [signals]
);
```

### Visual Indicators

```tsx
function OpportunityBadge({ score }: { score: number }) {
  if (score >= 80) return <Badge variant="hot">🔥 {score}</Badge>;
  if (score >= 60) return <Badge variant="good">⭐ {score}</Badge>;
  if (score >= 40) return <Badge variant="neutral">⚪ {score}</Badge>;
  return <Badge variant="low">🔹 {score}</Badge>;
}
```

### Filter Controls

```tsx
<FilterBar>
  <Select
    label="Min Score"
    options={[
      { value: 0, label: "All signals" },
      { value: 60, label: "Good+ (60+)" },
      { value: 80, label: "Hot only (80+)" }
    ]}
    onChange={setMinScore}
  />
  <Checkbox
    label="Show only hot opportunities"
    checked={hotOnly}
    onChange={setHotOnly}
  />
</FilterBar>
```

### Expanded Reasoning Panel

```
┌─────────────────────────────────────────────────────────────┐
│ 🔥 OPPORTUNITY SCORE: 87                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ SCORE BREAKDOWN                                            │
│                                                             │
│ Confidence         82%    ████████░░    +20.5 pts         │
│ Expected Return    +3.2%  ██████████    +30.0 pts         │
│ Strategy Consensus 80%    ████████░░    +16.0 pts         │
│ Volatility         2.1%   ███████░░░    +10.5 pts         │
│ Freshness          2m     █████████░    +10.0 pts         │
│                           ─────────────────────           │
│                           Total: 87.0 pts                 │
│                                                             │
│ WHY THIS SCORE?                                            │
│ This signal scores high because:                           │
│ • Strong strategy consensus (4/5 strategies agree)        │
│ • Top strategies have excellent historical returns         │
│ • Current volatility offers meaningful upside potential   │
│ • Signal is fresh (generated 2 minutes ago)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Constraints

- Score must be deterministic (same inputs = same score)
- Must handle missing data gracefully (use defaults)
  - Missing expected_return → use 0.01 (1%)
  - Missing volatility → use 0.015 (1.5%)
  - Missing timestamp → use current time
- Volatility data from InfluxDB (recent candles)
- Historical return data from strategy backtest results
- Score calculation must complete in < 100ms

## Configuration

```yaml
opportunity_scoring:
  weights:
    confidence: 0.25
    expected_return: 0.30
    consensus: 0.20
    volatility: 0.15
    freshness: 0.10
  normalization:
    max_return: 0.05        # 5% = full points
    max_volatility: 0.03    # 3% hourly = full points
    freshness_window_min: 60 # Decay over 60 minutes
  tiers:
    hot: 80
    good: 60
    neutral: 40
  defaults:
    expected_return: 0.01
    volatility: 0.015
```

## Acceptance Criteria

- [ ] Opportunity score computed for every signal
- [ ] Signals sorted by opportunity score in UI
- [ ] Score breakdown visible in expanded reasoning
- [ ] Filter by minimum opportunity score works
- [ ] Hot opportunities (score > 80) have visual emphasis (🔥)
- [ ] Score calculation is deterministic
- [ ] Missing data handled gracefully with defaults
- [ ] Score calculation completes in < 100ms

## File Structure

```
agents/opportunity-scorer/
├── .opencode/
│   └── config.json
├── skills/
│   ├── score-opportunity/
│   │   └── SKILL.md
│   └── calculate-expected-return/
│       └── SKILL.md
├── prompts/
│   └── system.md
└── tests/
    └── test_opportunity_scoring.py
```

## Metrics

- `opportunity_score_distribution` - Histogram of scores
- `opportunity_score_calculation_ms` - Scoring latency
- `hot_opportunities_total` - Count of hot signals
- `scoring_factor_contributions` - Average contribution by factor
