# LLM Strategy Validation Experiments

This directory contains the infrastructure and scripts for running validation experiments
defined in [Issue #1484](https://github.com/tradestreamhq/tradestream/issues/1484).

## Overview

The experiments validate the core thesis:

> An LLM can generate novel, profitable trading strategy specifications when given
> few-shot examples of production-validated strategies, and genetic algorithms can
> effectively optimize the parameters of these LLM-generated strategies.

## Experiments

### Experiment 1: LLM Spec Generation Quality (P0)

**Hypothesis:** Given 5-10 top-performing strategy specs as examples, an LLM can generate
novel, syntactically valid, and logically coherent strategy specifications.

**Success Criteria:**

- ≥80% syntactically valid
- ≥60% logically coherent
- ≥70% novel (not direct copies)

**Run:**

```bash
cd experiments/llm_validation
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
python llm_generator.py --num-generations 50
```

### Experiment 2: LLM-Generated Strategy Backtest Performance (P0)

**Hypothesis:** LLM-generated strategies, after GA optimization, perform comparably
to human-designed strategies in backtests.

**Success Criteria:**

- Median Sharpe of LLM strategies ≥ 80% of human strategies
- At least 3 LLM strategies in top 20 overall
- No catastrophic failures (drawdown > 50%)

**Run:**

```bash
python run_backtest_experiment.py \
  --strategies-dir ./results/generated_strategies \
  --output-dir ./results/experiment_2
```

### Experiment 2.5: Walk-Forward Validation of LLM Strategies (P0)

**Hypothesis:** LLM-generated strategies, when validated using walk-forward optimization,
maintain performance on out-of-sample data.

**Success Criteria:**

- OOS Sharpe > 0.5 (mean across strategies)
- Sharpe Degradation < 50%
- Approval Rate: 5-20% of strategies pass validation

**Dependencies:**

- #1558 Backtesting Service (COMPLETED)
- #1560 Walk-Forward Validation (COMPLETED)

## Files

| File                      | Purpose                          |
| ------------------------- | -------------------------------- |
| `strategy_schema.py`      | Strategy YAML schema validation  |
| `llm_generator.py`        | LLM-based strategy generation    |
| `test_strategy_schema.py` | Unit tests for schema validation |
| `requirements.txt`        | Python dependencies              |

## Strategy YAML Schema

```yaml
name: STRATEGY_NAME
description: Brief description
complexity: SIMPLE|MEDIUM|COMPLEX

indicators:
  - id: unique_id
    type: SMA|EMA|RSI|MACD|...
    input: close|high|low|volume|<other_indicator_id>
    params:
      period: "${parameterName}"

entryConditions:
  - type: CROSSED_UP|OVER_CONSTANT|...
    indicator: indicator_id
    params:
      crosses: other_indicator_id
      threshold: 25

exitConditions:
  - type: CROSSED_DOWN|UNDER_CONSTANT|...
    indicator: indicator_id
    params:
      crosses: other_indicator_id

parameters:
  - name: parameterName
    type: INTEGER|DOUBLE
    min: 5
    max: 50
    defaultValue: 20
```

## Available Indicator Types

### Moving Averages

- `SMA`, `EMA`, `DEMA`, `TEMA`

### Oscillators

- `RSI`, `STOCHASTIC_K`, `CMO`, `WILLIAMS_R`, `CCI`, `ROC`
- `MACD`, `AWESOME_OSCILLATOR`, `CHAIKIN_OSCILLATOR`

### Volume

- `OBV`, `CMF`, `MFI`, `KLINGER_VOLUME_OSCILLATOR`

### Trend

- `ADX`, `PLUS_DI`, `MINUS_DI`, `AROON_UP`, `AROON_DOWN`, `MASS_INDEX`

### Volatility

- `ATR`, `BOLLINGER_UPPER`, `BOLLINGER_LOWER`

### Price

- `CLOSE_PRICE`, `HIGH_PRICE`, `LOW_PRICE`, `HIGHEST_HIGH`, `LOWEST_LOW`

### Utility

- `CONSTANT`, `DIFFERENCE`, `PREVIOUS`

## Available Condition Types

### Crossovers

- `CROSSED_UP`, `CROSSED_DOWN`
- `CROSSED_UP_CONSTANT`, `CROSSED_DOWN_CONSTANT`
- `CROSSES_ABOVE`, `CROSSES_BELOW`

### Comparisons

- `OVER_CONSTANT`, `UNDER_CONSTANT`
- `OVER_INDICATOR`, `UNDER_INDICATOR`
- `ABOVE`, `BELOW`, `OVER`, `UNDER`

## Results

Results are saved to `./results/` directory:

- `experiment_1_results.json` - Experiment 1 metrics and generated strategies
- `generated_strategies/` - Valid YAML strategies for Experiment 2
