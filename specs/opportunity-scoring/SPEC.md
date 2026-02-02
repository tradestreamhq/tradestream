# Opportunity Scoring Specification

## Goal

Score and rank trading opportunities by perceived upside to surface the best opportunities first, enabling users to focus attention on the most promising signals.

## Target Behavior

Each signal receives an **opportunity score** (0-100) computed from multiple factors. Higher scores indicate higher perceived opportunity.

### Scoring Factors

| Factor | Weight | Range | Description |
|--------|--------|-------|-------------|
| **Confidence** | 25% | 0-1 | Agent's confidence in the signal |
| **Expected Return** | 30% | 0-5% | Risk-adjusted return of triggering strategies |
| **Strategy Consensus** | 20% | 0-100% | % of top strategies agreeing |
| **Volatility Factor** | 15% | 0-3% | Higher volatility = bigger opportunity (regime-adjusted) |
| **Freshness** | 10% | 0-60 min | More recent signals slightly preferred |

### Opportunity Score Formula

```python
def calculate_opportunity_score(
    confidence: float,           # 0.0 - 1.0
    expected_return: float,      # percentage, e.g., 0.032 for 3.2%
    return_stddev: float,        # standard deviation of strategy returns
    consensus_pct: float,        # 0.0 - 1.0
    volatility: float,           # hourly volatility, e.g., 0.021
    minutes_ago: int,            # signal age in minutes
    market_regime: str = "normal"  # normal, high_volatility, or extreme
) -> float:
    """
    Calculate opportunity score (0-100) for a trading signal.

    Returns:
        Float between 0 and 100
    """
    # Get regime-adjusted normalization caps
    caps = get_regime_adjusted_caps(market_regime)

    # Risk-adjusted return (Sharpe-like normalization)
    # Penalizes high-variance strategies, rewards consistency
    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = min(risk_adjusted_return / caps.max_return, 1.0)

    # Normalize volatility with regime-adjusted cap
    volatility_score = min(volatility / caps.max_volatility, 1.0)

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

### Risk-Adjusted Returns (Sharpe Adjustment)

To avoid equal treatment of high-variance and low-variance strategies, expected returns are adjusted using a Sharpe-like factor:

```python
def apply_sharpe_adjustment(expected_return: float, return_stddev: float) -> float:
    """
    Apply Sharpe-like adjustment to expected return.

    Rewards strategies with consistent returns over volatile ones.
    A strategy with 3% return and 1% stddev scores higher than
    a strategy with 3% return and 3% stddev.

    Args:
        expected_return: Historical average return (e.g., 0.032 for 3.2%)
        return_stddev: Standard deviation of returns

    Returns:
        Risk-adjusted return value
    """
    if return_stddev <= 0:
        # No variance data available - use raw return
        return expected_return

    # Calculate Sharpe-like ratio (return / risk)
    sharpe_factor = expected_return / return_stddev

    # Apply adjustment: scale return by bounded Sharpe factor
    # Cap at 2.0 to prevent extreme adjustments
    adjustment_multiplier = min(sharpe_factor, 2.0) / 2.0

    return expected_return * (0.5 + 0.5 * adjustment_multiplier)
```

**Example Impact:**

| Strategy | Avg Return | Stddev | Raw Score | Adjusted Score |
|----------|-----------|--------|-----------|----------------|
| Strategy A | 3.0% | 1.0% | 60% | 75% |
| Strategy B | 3.0% | 3.0% | 60% | 60% |
| Strategy C | 3.0% | 6.0% | 60% | 52.5% |

### Market Regime Detection and Handling

Fixed normalization caps can produce misleading scores during extreme market conditions. The system detects market regimes and adjusts caps dynamically:

```python
@dataclass
class RegimeCaps:
    max_return: float
    max_volatility: float

def get_regime_adjusted_caps(regime: str) -> RegimeCaps:
    """
    Return normalization caps based on current market regime.

    During extreme conditions (flash crashes, high volatility events),
    standard caps would cause all signals to max out volatility scores.
    Regime-adjusted caps maintain meaningful differentiation.
    """
    if regime == "extreme":
        # Flash crash / black swan event
        # Widen caps significantly to maintain score differentiation
        return RegimeCaps(
            max_return=0.15,      # 15% = full points (3x normal)
            max_volatility=0.10   # 10% hourly = full points (3.3x normal)
        )
    elif regime == "high_volatility":
        # Elevated volatility (earnings, major news)
        return RegimeCaps(
            max_return=0.08,      # 8% = full points (1.6x normal)
            max_volatility=0.05   # 5% hourly = full points (1.7x normal)
        )
    else:  # normal
        return RegimeCaps(
            max_return=0.05,      # 5% = full points
            max_volatility=0.03   # 3% hourly = full points
        )

def detect_market_regime(symbol: str) -> str:
    """
    Detect current market regime based on recent volatility.

    Uses VIX-equivalent or rolling volatility percentile.
    """
    recent_vol = get_volatility_for_scoring(symbol)
    historical_vol = get_historical_volatility_percentile(symbol, lookback_days=30)

    if historical_vol >= 0.95:  # 95th percentile
        return "extreme"
    elif historical_vol >= 0.80:  # 80th percentile
        return "high_volatility"
    else:
        return "normal"
```

**Regime Indicator in UI:**

```
MARKET REGIME: EXTREME
Volatility caps adjusted to maintain score differentiation.
```

### Score Caching for Time Stability

To ensure score stability and avoid time-dependent recalculations, scores are computed and cached at signal creation time:

```python
class ScoredSignal:
    """
    Scores are immutable once computed at signal creation.

    This ensures:
    1. Deterministic behavior (same signal = same score always)
    2. No score drift as signals age
    3. Fair comparison between signals of different ages
    """

    def __init__(self, raw_signal: Signal, scoring_inputs: ScoringInputs):
        # Compute score ONCE at creation time
        self.created_at = datetime.utcnow()
        self.freshness_at_creation = 0  # Always fresh when first scored

        self.opportunity_score = calculate_opportunity_score(
            confidence=raw_signal.confidence,
            expected_return=scoring_inputs.expected_return,
            return_stddev=scoring_inputs.return_stddev,
            consensus_pct=scoring_inputs.consensus_pct,
            volatility=scoring_inputs.volatility,
            minutes_ago=self.freshness_at_creation,  # Locked at creation
            market_regime=scoring_inputs.market_regime
        )

        # Score is now immutable - never recalculated
        self._score_locked = True

    @property
    def display_age(self) -> int:
        """For UI display only - does not affect score."""
        return int((datetime.utcnow() - self.created_at).total_seconds() / 60)

    @property
    def is_stale(self) -> bool:
        """Signal is stale if older than freshness window (60 min)."""
        return self.display_age >= 60
```

**Rationale**: The freshness factor rewards prompt action on signals. By caching the score at creation, we ensure that signal rankings remain stable over time. The UI displays actual signal age for user awareness without affecting the cached score.

**UI Display of Cached Score:**

```
OPPORTUNITY SCORE: 87 (cached at creation)

Freshness:         0m      +10.0 pts  (score locked)
Signal age:        12m ago            (display only)
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
Expected Return:   +3.2% ██████████ +30.0 pts  (risk-adjusted)
Strategy Consensus: 80% ████████░░ +16.0 pts
Volatility:        2.1% ███████░░░ +10.5 pts  (regime: normal)
Freshness:         0m   ██████████ +10.0 pts  (cached)
                        ─────────────────────
                        Total: 87.0 pts
```

## Data Requirements

### Inputs per Signal

| Field | Source | Description |
|-------|--------|-------------|
| `confidence` | Signal Generator Agent | Agent's confidence in the signal |
| `expected_return` | Backtest MCP | Avg return of triggering strategies |
| `return_stddev` | Backtest MCP | Stddev of returns for Sharpe adjustment |
| `strategies_bullish` | Signal Generator | Count of bullish strategies |
| `strategies_analyzed` | Signal Generator | Total strategies checked |
| `volatility` | Market Data MCP | Recent hourly volatility |
| `volatility_percentile` | Market Data MCP | 30-day volatility percentile |
| `timestamp` | Signal Generator | When signal was generated |

### Expected Return Calculation

```python
def calculate_expected_return(
    strategies: list[StrategySignal],
    signal_action: str  # BUY or SELL
) -> tuple[float, float]:
    """
    Calculate expected return and standard deviation based on historical
    performance of the strategies that triggered this signal.

    Returns:
        Tuple of (weighted_avg_return, weighted_stddev)
    """
    agreeing_strategies = [
        s for s in strategies
        if s.signal == signal_action
    ]

    if not agreeing_strategies:
        return 0.0, 0.0

    # Weight by strategy score
    total_weight = sum(s.score for s in agreeing_strategies)

    weighted_return = sum(
        s.historical_avg_return * s.score
        for s in agreeing_strategies
    ) / total_weight

    # Calculate weighted standard deviation
    weighted_stddev = sum(
        s.historical_return_stddev * s.score
        for s in agreeing_strategies
    ) / total_weight

    return weighted_return, weighted_stddev
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

def get_historical_volatility_percentile(symbol: str, lookback_days: int = 30) -> float:
    """
    Get percentile rank of current volatility vs historical.
    Used for market regime detection.

    Returns:
        Float between 0.0 and 1.0 representing percentile
    """
    current_vol = get_volatility_for_scoring(symbol)

    historical_candles = market_data_mcp.get_candles(
        symbol=symbol,
        timeframe="1h",
        limit=lookback_days * 24
    )

    # Calculate rolling 24h volatility for each day
    daily_vols = []
    for i in range(0, len(historical_candles) - 24, 24):
        day_candles = historical_candles[i:i+24]
        day_returns = [(c.close - c.open) / c.open for c in day_candles]
        daily_vols.append(statistics.stdev(day_returns))

    # Calculate percentile
    below_current = sum(1 for v in daily_vols if v < current_vol)
    return below_current / len(daily_vols) if daily_vols else 0.5
```

## Implementation

### Opportunity Scorer Agent

The Opportunity Scorer is a dedicated OpenCode agent that:
1. Subscribes to `agent-signals-raw` (from Signal Generator)
2. Enriches each signal with opportunity score
3. Publishes scored signals to `agent-signals-scored`

```
┌─────────────────────────────────────────────────────────────┐
│  OPPORTUNITY SCORER AGENT                                  │
│                                                             │
│  Input: Raw signal from Signal Generator                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MCP Tools                                            │   │
│  │  - backtest-mcp: get_historical_performance         │   │
│  │  - backtest-mcp: get_return_statistics              │   │
│  │  - market-data-mcp: get_volatility                  │   │
│  │  - market-data-mcp: get_volatility_percentile       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Skills                                               │   │
│  │  - score-opportunity: Apply scoring formula          │   │
│  │  - calculate-expected-return: Weight by performance │   │
│  │  - detect-market-regime: Adjust caps dynamically    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Output: Scored signal -> Kafka agent-signals-scored     │
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
  "opportunity_score_cached_at": "2025-02-01T12:34:56Z",
  "opportunity_tier": "HOT",
  "market_regime": "normal",
  "opportunity_factors": {
    "confidence": { "value": 0.82, "contribution": 20.5 },
    "expected_return": {
      "value": 0.032,
      "stddev": 0.015,
      "risk_adjusted": 0.028,
      "contribution": 30.0
    },
    "consensus": { "value": 0.80, "contribution": 16.0 },
    "volatility": {
      "value": 0.021,
      "percentile": 0.65,
      "contribution": 10.5
    },
    "freshness": { "value": 0, "contribution": 10.0, "cached": true }
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

### Market Regime Indicator

```tsx
function MarketRegimeIndicator({ regime }: { regime: string }) {
  if (regime === "extreme") {
    return <Badge variant="warning">⚠️ Extreme Volatility</Badge>;
  }
  if (regime === "high_volatility") {
    return <Badge variant="caution">📊 High Volatility</Badge>;
  }
  return null; // Don't show indicator for normal regime
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
│   └─ Risk-adjusted: +2.8% (stddev: 1.5%)                   │
│ Strategy Consensus 80%    ████████░░    +16.0 pts         │
│ Volatility         2.1%   ███████░░░    +10.5 pts         │
│   └─ Regime: normal (65th percentile)                      │
│ Freshness          0m     ██████████    +10.0 pts         │
│   └─ Score cached at creation (signal age: 12m)            │
│                           ─────────────────────           │
│                           Total: 87.0 pts                 │
│                                                             │
│ WHY THIS SCORE?                                            │
│ This signal scores high because:                           │
│ - Strong strategy consensus (4/5 strategies agree)        │
│ - Top strategies have consistent, low-variance returns     │
│ - Current volatility offers meaningful upside potential   │
│ - Score was locked at creation for ranking stability      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Constraints

- Score must be deterministic (same inputs = same score)
- Scores are cached at signal creation and never recalculated
- Must handle missing data gracefully (use defaults)
  - Missing expected_return -> use 0.01 (1%)
  - Missing return_stddev -> skip Sharpe adjustment
  - Missing volatility -> use 0.015 (1.5%)
  - Missing volatility_percentile -> assume "normal" regime
  - Missing timestamp -> use current time
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
    # Normal regime caps
    max_return: 0.05        # 5% = full points
    max_volatility: 0.03    # 3% hourly = full points
    freshness_window_min: 60 # Decay over 60 minutes
  regime_detection:
    extreme_percentile: 0.95    # 95th percentile = extreme
    high_vol_percentile: 0.80   # 80th percentile = high volatility
    lookback_days: 30           # Days for percentile calculation
  regime_caps:
    high_volatility:
      max_return: 0.08
      max_volatility: 0.05
    extreme:
      max_return: 0.15
      max_volatility: 0.10
  sharpe_adjustment:
    enabled: true
    max_factor: 2.0           # Cap Sharpe factor at 2.0
  score_caching:
    enabled: true             # Cache scores at creation
    show_age_in_ui: true      # Display actual signal age
  tiers:
    hot: 80
    good: 60
    neutral: 40
  defaults:
    expected_return: 0.01
    return_stddev: 0.0        # Disables Sharpe adjustment if missing
    volatility: 0.015
    market_regime: "normal"
```

## Acceptance Criteria

- [ ] Opportunity score computed for every signal
- [ ] Signals sorted by opportunity score in UI
- [ ] Score breakdown visible in expanded reasoning
- [ ] Filter by minimum opportunity score works
- [ ] Hot opportunities (score > 80) have visual emphasis (🔥)
- [ ] Score calculation is deterministic
- [ ] Scores cached at creation (no time-dependent drift)
- [ ] Risk-adjusted returns using Sharpe-like adjustment
- [ ] Market regime detection adjusts normalization caps
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
│   ├── calculate-expected-return/
│   │   └── SKILL.md
│   └── detect-market-regime/
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
- `sharpe_adjustment_applied` - Count of signals with Sharpe adjustment
- `market_regime_distribution` - Count of signals by regime
- `extreme_regime_events` - Count of extreme regime detections
