# Prediction Reasoning Specification

## Goal

Ensure credible, transparent prediction reasoning with proper validation, confidence intervals, and disclaimers. Address the reality that over 90% of academic strategies fail when implemented with real capital due to backtesting overfitting.

## The Problem

> "Over 90% of academic strategies fail when implemented with real capital"

This happens because:
- Backtests overfit to historical data
- Transaction costs and slippage are underestimated
- Market conditions change over time
- Survivorship bias in strategy selection

**We must differentiate between:**
- **Backtest performance** - What we historically simulated
- **Forward test performance** - What we observed in paper trading
- **Live trading performance** - What actually happened with real capital

## Validation Levels

```
┌─────────────────────────────────────────────────────────────┐
│  STRATEGY LIFECYCLE                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  DISCOVERY (GA)          FORWARD TEST        LIVE TRADING   │
│  ───────────────────────────────────────────────────────── │
│  Backtest data only   │  Paper trading     │  Real capital  │
│  High overfitting     │  6-month minimum   │  Proven track  │
│  risk                 │  track record      │  record        │
│                       │                    │                │
│  Status: ⚠️           │  Status: ✅        │  Status: 🏆    │
│  "Candidate"          │  "Validated"       │  "Deployed"    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Validation Status Badges

| Status | Badge | Requirements | Display |
|--------|-------|--------------|---------|
| **Candidate** | ⚠️ | Backtest only | "Backtest only - not yet validated" |
| **Validated** | ✅ | 6+ months forward test, 100+ signals | "Forward-tested (6 months)" |
| **Deployed** | 🏆 | Live trading track record | "Live-validated" |

### Validation Status Transition Rules

Strategies can only move forward through validation levels, never backward (except for demotion due to decay):

```
Candidate ──────► Validated ──────► Deployed
    │                 │                 │
    │                 │                 │
    ▼                 ▼                 ▼
 [Retire]         [Demote]          [Demote]
                  to Candidate      to Validated
```

**Promotion Criteria:**

| Transition | Requirements |
|------------|--------------|
| Candidate → Validated | 6+ months forward-test, 100+ signals, accuracy >= 55%, Sharpe >= 1.0 |
| Validated → Deployed | Manual approval + 50+ live trades, positive P&L, drawdown <= 15% |

**Demotion Criteria:**

| Condition | Action |
|-----------|--------|
| Decay trend = DECLINING for 2+ consecutive months | Demote one level |
| Accuracy drops below 50% (rolling 3-month) | Demote to Candidate |
| Max drawdown exceeds 20% in live trading | Immediately halt + Demote to Validated |

**Retirement:**
- Strategies with < 45% accuracy over 6+ months are retired (removed from signal generation)
- Retired strategies can be re-enabled for research but not user-facing signals

## Prediction Display Requirements

Every signal must show:

### 1. Expected Return with Confidence Interval

```
Expected Return: +3.2% ± 1.5% (95% CI)
```

**Never show just "+3.2%"** - always include uncertainty.

```python
def calculate_expected_return_with_ci(
    strategy_returns: list[float],
    confidence_level: float = 0.95
) -> tuple[float, float, float]:
    """
    Calculate expected return with confidence interval.

    Returns:
        (mean, lower_bound, upper_bound)
    """
    mean = statistics.mean(strategy_returns)
    std = statistics.stdev(strategy_returns)
    n = len(strategy_returns)

    # t-distribution for small samples
    t_value = scipy.stats.t.ppf((1 + confidence_level) / 2, n - 1)
    margin = t_value * (std / math.sqrt(n))

    return (mean, mean - margin, mean + margin)
```

### 2. Timeframe

```
Timeframe: Based on 1-hour candles, expected within 24 hours
```

Users need to know when to expect the predicted return.

### 3. Validation Status

```
Validation: ✅ Forward-tested (6 months)
```

Prominently display validation level.

### 4. Historical Accuracy

```
Strategy Accuracy: 62% over 847 signals (6-month forward test)
```

**Critical:** Show accuracy from forward-test period only, not backtest.

### 5. Strategy Age

```
Strategy discovered: 2025-08-15 (6 months ago)
Signals since discovery: 847 | Accuracy: 62%
```

Recent discoveries have less validation.

## Signal Card with Validation

```
┌─────────────────────────────────────────────────────────────┐
│ 🔥 OPPORTUNITY SCORE: 87                                   │
│ 🟢 BUY ETH/USD                                             │
├─────────────────────────────────────────────────────────────┤
│ Expected Return: +3.2% ± 1.5% (95% CI)                     │
│ Timeframe: 24 hours (based on 1-hour candles)              │
│ Validation: ✅ Forward-tested (6 months)                   │
│                                                             │
│ Strategy: RSI_REVERSAL                                     │
│ Track Record: 62% accuracy | 847 signals | Sharpe 1.8      │
│ Discovered: 2025-08-15                                     │
├─────────────────────────────────────────────────────────────┤
│ ⚠️ Past performance does not guarantee future results.     │
│ Trading involves risk. This is not financial advice.       │
└─────────────────────────────────────────────────────────────┘
```

## Required Disclaimers

Every signal must include appropriate disclaimers:

### Always Shown (Prominently Displayed)

Disclaimers must be prominently displayed, not hidden in fine print. They should:
- Appear in a visible location (not collapsed or scrolled out of view)
- Use readable font size (minimum 12px)
- Have sufficient contrast with background
- Be shown before any "Buy" or "Sell" action buttons

```
⚠️ Past performance does not guarantee future results.
Trading involves risk of loss. This is not financial advice.
Maximum historical drawdown: -XX.X% (based on forward-test data).
```

### Registered Investment Advisor (RIA) Disclaimer

If providing signals that could be construed as investment advice:

```
TradeStream is not a registered investment advisor. Signals provided are
for informational purposes only and do not constitute investment advice.
Consult a licensed financial advisor before making investment decisions.
```

### For Candidate Strategies (Backtest Only)

```
⚠️ BACKTEST ONLY: This strategy has not been forward-tested.
Backtest results often do not reflect real-world performance.
Proceed with extreme caution.
```

### For High Volatility

```
⚠️ HIGH VOLATILITY: This asset is experiencing elevated volatility.
Position sizing should account for increased risk.
```

### For New Strategies

```
⚠️ NEW STRATEGY: Discovered less than 3 months ago.
Limited track record available.
```

## Confidence Interval Calculation

### Per-Strategy CI

```python
def strategy_return_ci(
    strategy_id: str,
    period: str = "6m"
) -> ReturnEstimate:
    """
    Calculate return estimate with confidence interval for a strategy.
    """
    # Get forward-test signals only
    signals = db.query("""
        SELECT actual_return
        FROM signal_outcomes
        WHERE strategy_id = $1
          AND signal_type = 'forward_test'
          AND outcome_timestamp >= NOW() - INTERVAL $2
    """, strategy_id, period)

    if len(signals) < 30:
        return ReturnEstimate(
            mean=None,
            ci_lower=None,
            ci_upper=None,
            sample_size=len(signals),
            warning="Insufficient data for reliable estimate"
        )

    returns = [s.actual_return for s in signals]
    mean, lower, upper = calculate_expected_return_with_ci(returns)

    return ReturnEstimate(
        mean=mean,
        ci_lower=lower,
        ci_upper=upper,
        sample_size=len(signals),
        warning=None
    )
```

### Aggregated CI for Multi-Strategy Signals

```python
def aggregate_return_ci(
    strategy_returns: list[ReturnEstimate],
    weights: list[float]
) -> ReturnEstimate:
    """
    Aggregate return estimates from multiple strategies.
    Uses weighted average and propagated uncertainty.
    """
    # Weighted mean
    total_weight = sum(weights)
    weighted_mean = sum(
        r.mean * w for r, w in zip(strategy_returns, weights)
        if r.mean is not None
    ) / total_weight

    # Propagate uncertainty (simplified)
    weighted_variance = sum(
        ((r.ci_upper - r.ci_lower) / 4) ** 2 * (w / total_weight) ** 2
        for r, w in zip(strategy_returns, weights)
        if r.ci_upper is not None
    )
    ci_margin = 2 * math.sqrt(weighted_variance)

    return ReturnEstimate(
        mean=weighted_mean,
        ci_lower=weighted_mean - ci_margin,
        ci_upper=weighted_mean + ci_margin,
        sample_size=sum(r.sample_size for r in strategy_returns),
        warning=None
    )
```

## Prediction Tracking

### Database Schema

```sql
CREATE TABLE signal_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL REFERENCES agent_decisions(decision_id),
    strategy_id UUID NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    predicted_action VARCHAR(10) NOT NULL,  -- BUY, SELL
    predicted_return DECIMAL(8,4),
    predicted_return_ci_lower DECIMAL(8,4),
    predicted_return_ci_upper DECIMAL(8,4),
    predicted_timeframe_hours INTEGER,
    -- Actual outcomes
    actual_return DECIMAL(8,4),
    actual_duration_hours INTEGER,
    hit_target BOOLEAN,
    max_drawdown DECIMAL(8,4),
    -- Metadata
    signal_type VARCHAR(20) NOT NULL,  -- backtest, forward_test, live
    signal_timestamp TIMESTAMP NOT NULL,
    outcome_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_outcomes_strategy ON signal_outcomes(strategy_id);
CREATE INDEX idx_outcomes_symbol ON signal_outcomes(symbol);
CREATE INDEX idx_outcomes_type ON signal_outcomes(signal_type);
```

### Outcome Recording

```python
async def record_signal_outcome(signal_id: str):
    """
    Record actual outcome for a signal after timeframe elapses.
    Called by scheduled job.

    Edge Case Handling:
    - Early target hit then reversal: We use "final return at timeframe" not "peak return"
      to avoid overstating success. A trade that hit +5% then reversed to -2% is recorded as -2%.
    - This conservative approach better reflects realistic trading outcomes where
      perfect exit timing is not always possible.

    80% Threshold Rationale:
    - The 80% threshold for hit_target accounts for slippage, fees, and execution costs
    - A prediction of +5% that achieves +4% is considered successful (4% >= 5% * 0.8)
    - This tolerance prevents penalizing strategies for minor execution differences
    - The threshold is configurable via settings for different risk profiles
    """
    signal = await get_signal(signal_id)

    # Get price history during signal timeframe for drawdown calculation
    price_history = await get_price_history(
        signal.symbol,
        start=signal.signal_timestamp,
        end=signal.signal_timestamp + timedelta(hours=signal.predicted_timeframe_hours)
    )

    # Calculate actual return at timeframe end (not peak)
    entry_price = signal.market_context.current_price
    current_price = await get_current_price(signal.symbol)
    actual_return = (current_price - entry_price) / entry_price

    # Calculate maximum drawdown during holding period
    if signal.action == "BUY":
        max_adverse = min(p.low for p in price_history)
        max_drawdown = (max_adverse - entry_price) / entry_price
    else:
        max_adverse = max(p.high for p in price_history)
        max_drawdown = (entry_price - max_adverse) / entry_price

    # Adjust for direction
    if signal.action == "SELL":
        actual_return = -actual_return

    # Did it hit target?
    # 80% threshold accounts for slippage/fees (configurable)
    target_threshold = settings.get("target_hit_threshold", 0.8)
    hit_target = actual_return >= signal.predicted_return * target_threshold

    await db.execute("""
        UPDATE signal_outcomes
        SET actual_return = $1,
            actual_duration_hours = $2,
            hit_target = $3,
            max_drawdown = $4,
            outcome_timestamp = NOW()
        WHERE signal_id = $5
    """, actual_return, hours_elapsed, hit_target, max_drawdown, signal_id)
```

## Metrics to Track

### Prediction Accuracy

```python
def calculate_accuracy_by_validation_level():
    """Track accuracy separately by validation level."""
    return db.query("""
        SELECT
            signal_type,
            COUNT(*) as total_signals,
            AVG(CASE WHEN hit_target THEN 1.0 ELSE 0.0 END) as accuracy,
            AVG(actual_return) as avg_return,
            STDDEV(actual_return) as return_stddev
        FROM signal_outcomes
        WHERE outcome_timestamp IS NOT NULL
        GROUP BY signal_type
    """)
```

### Strategy Decay

```python
def measure_strategy_decay(strategy_id: str) -> DecayMetrics:
    """
    Measure how strategy performance changes over time.
    Early detection of strategy degradation.

    Uses confidence bounds on slope to avoid false positives from noise.
    A decay signal is only raised when the slope is significantly negative
    (i.e., the 95% confidence interval excludes zero).
    """
    # Performance by month since discovery
    monthly_perf = db.query("""
        SELECT
            DATE_TRUNC('month', signal_timestamp) as month,
            AVG(CASE WHEN hit_target THEN 1.0 ELSE 0.0 END) as accuracy,
            AVG(actual_return) as avg_return,
            COUNT(*) as signal_count
        FROM signal_outcomes
        WHERE strategy_id = $1
          AND outcome_timestamp IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """, strategy_id)

    # Calculate decay trend with confidence bounds
    accuracies = [m.accuracy for m in monthly_perf]
    if len(accuracies) >= 3:
        # Fit linear regression with confidence interval on slope
        x = numpy.array(range(len(accuracies)))
        y = numpy.array(accuracies)

        # Calculate slope and standard error
        n = len(accuracies)
        slope, intercept = numpy.polyfit(x, y, 1)
        y_pred = slope * x + intercept
        residuals = y - y_pred
        mse = numpy.sum(residuals ** 2) / (n - 2)
        se_slope = numpy.sqrt(mse / numpy.sum((x - x.mean()) ** 2))

        # 95% confidence interval on slope
        t_value = scipy.stats.t.ppf(0.975, n - 2)
        slope_ci_lower = slope - t_value * se_slope
        slope_ci_upper = slope + t_value * se_slope

        # Only flag declining if confidence interval excludes zero
        # This prevents false alarms from random noise
        if slope_ci_upper < 0:  # Entire CI is negative
            trend = "DECLINING"
        elif slope_ci_lower > 0:  # Entire CI is positive
            trend = "IMPROVING"
        else:  # CI includes zero - no significant trend
            trend = "STABLE"
    else:
        trend = "INSUFFICIENT_DATA"
        slope = None
        slope_ci_lower = None
        slope_ci_upper = None

    return DecayMetrics(
        monthly_performance=monthly_perf,
        trend=trend,
        slope=slope,
        slope_ci_lower=slope_ci_lower,
        slope_ci_upper=slope_ci_upper
    )
```

## UI Components

### Return Display Component

```tsx
// components/ReturnDisplay/ReturnDisplay.tsx

interface ReturnDisplayProps {
  expectedReturn: number;
  ciLower: number;
  ciUpper: number;
  timeframeHours: number;
}

export function ReturnDisplay({
  expectedReturn,
  ciLower,
  ciUpper,
  timeframeHours
}: ReturnDisplayProps) {
  const margin = ((expectedReturn - ciLower) * 100).toFixed(1);

  return (
    <div className="return-display">
      <div className="return-value">
        <span className="expected">
          {expectedReturn > 0 ? '+' : ''}{(expectedReturn * 100).toFixed(1)}%
        </span>
        <span className="ci">
          ± {margin}%
        </span>
        <span className="ci-label">(95% CI)</span>
      </div>
      <div className="timeframe">
        Timeframe: {timeframeHours} hours
      </div>
    </div>
  );
}
```

### Validation Badge Component

```tsx
// components/ValidationBadge/ValidationBadge.tsx

type ValidationLevel = 'candidate' | 'validated' | 'deployed';

interface ValidationBadgeProps {
  level: ValidationLevel;
  forwardTestMonths?: number;
  signalCount?: number;
}

export function ValidationBadge({
  level,
  forwardTestMonths,
  signalCount
}: ValidationBadgeProps) {
  const badges = {
    candidate: {
      icon: '⚠️',
      label: 'Backtest only',
      color: 'yellow',
      tooltip: 'This strategy has not been forward-tested. Backtest results may not reflect real-world performance.'
    },
    validated: {
      icon: '✅',
      label: `Forward-tested (${forwardTestMonths}mo)`,
      color: 'green',
      tooltip: `Validated with ${signalCount} signals over ${forwardTestMonths} months of paper trading.`
    },
    deployed: {
      icon: '🏆',
      label: 'Live-validated',
      color: 'gold',
      tooltip: 'This strategy has been validated with real capital.'
    }
  };

  const badge = badges[level];

  return (
    <Tooltip content={badge.tooltip}>
      <Badge color={badge.color}>
        {badge.icon} {badge.label}
      </Badge>
    </Tooltip>
  );
}
```

### Disclaimer Component

```tsx
// components/Disclaimer/Disclaimer.tsx

interface DisclaimerProps {
  validationLevel: ValidationLevel;
  isHighVolatility?: boolean;
  strategyAgeMonths?: number;
}

export function Disclaimer({
  validationLevel,
  isHighVolatility,
  strategyAgeMonths
}: DisclaimerProps) {
  return (
    <div className="disclaimer">
      <p className="standard">
        ⚠️ Past performance does not guarantee future results.
        Trading involves risk of loss. This is not financial advice.
      </p>

      {validationLevel === 'candidate' && (
        <p className="warning">
          ⚠️ <strong>BACKTEST ONLY:</strong> This strategy has not been forward-tested.
          Backtest results often do not reflect real-world performance.
        </p>
      )}

      {isHighVolatility && (
        <p className="warning">
          ⚠️ <strong>HIGH VOLATILITY:</strong> Position sizing should account for increased risk.
        </p>
      )}

      {strategyAgeMonths && strategyAgeMonths < 3 && (
        <p className="warning">
          ⚠️ <strong>NEW STRATEGY:</strong> Limited track record ({strategyAgeMonths} months).
        </p>
      )}
    </div>
  );
}
```

## Constraints

- Never show expected return without confidence interval
- Always show validation status prominently
- Include standard disclaimers on every signal
- Track all predictions for ongoing accuracy measurement
- Historical accuracy calculated from forward-test period only
- Strategy decay monitoring to detect degradation

## Acceptance Criteria

- [ ] Every signal shows expected return with 95% CI
- [ ] Every signal shows validation status (candidate/validated/deployed)
- [ ] Historical accuracy calculated from forward-test period only
- [ ] Standard disclaimers displayed prominently on all signal cards
- [ ] RIA disclaimer included where applicable
- [ ] Maximum drawdown disclosed in signal information
- [ ] Additional warnings for candidate/high-volatility/new strategies
- [ ] Prediction tracking database records all outcomes including max_drawdown
- [ ] Strategy decay metrics calculated with confidence bounds on slope
- [ ] Validation status transitions follow defined rules
- [ ] UI components display all required information

## File Structure

```
services/prediction_tracking/
├── __init__.py
├── main.py
├── confidence_interval.py
├── outcome_recorder.py
├── decay_monitor.py
└── tests/
    └── test_confidence_interval.py

ui/agent-dashboard/src/components/
├── ReturnDisplay/
│   └── ReturnDisplay.tsx
├── ValidationBadge/
│   └── ValidationBadge.tsx
└── Disclaimer/
    └── Disclaimer.tsx
```
