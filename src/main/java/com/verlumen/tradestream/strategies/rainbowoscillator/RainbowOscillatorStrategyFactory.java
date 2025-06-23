package com.verlumen.tradestream.strategies.rainbowoscillator;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.RainbowOscillatorParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class RainbowOscillatorStrategyFactory
    implements StrategyFactory<RainbowOscillatorParameters> {

  @Override
  public RainbowOscillatorParameters getDefaultParameters() {
    return RainbowOscillatorParameters.newBuilder()
        .addPeriods(10)
        .addPeriods(20)
        .addPeriods(50)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, RainbowOscillatorParameters parameters) {
    checkArgument(parameters.getPeriodsCount() >= 2, "At least 2 periods required");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);

    // Create multiple EMAs for the rainbow effect
    EMAIndicator shortEma = new EMAIndicator(closePrice, parameters.getPeriods(0));
    EMAIndicator longEma =
        new EMAIndicator(closePrice, parameters.getPeriods(parameters.getPeriodsCount() - 1));

    // Create a custom Rainbow Oscillator indicator
    RainbowOscillatorIndicator rainbowOscillator =
        new RainbowOscillatorIndicator(series, parameters);

    // Entry rule: Buy when Rainbow Oscillator crosses above zero
    Rule entryRule = new CrossedUpIndicatorRule(rainbowOscillator, new ZeroLineIndicator(series));

    // Exit rule: Sell when Rainbow Oscillator crosses below zero
    Rule exitRule = new CrossedDownIndicatorRule(rainbowOscillator, new ZeroLineIndicator(series));

    return new BaseStrategy("Rainbow Oscillator", entryRule, exitRule);
  }

  /**
   * Custom Rainbow Oscillator indicator that calculates the difference between the shortest and
   * longest moving averages, normalized by the longest average.
   */
  private static class RainbowOscillatorIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final RainbowOscillatorParameters parameters;
    private final ClosePriceIndicator closePrice;

    public RainbowOscillatorIndicator(BarSeries series, RainbowOscillatorParameters parameters) {
      super(series);
      this.parameters = parameters;
      this.closePrice = new ClosePriceIndicator(series);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      if (parameters.getPeriodsCount() < 2) {
        return numOf(0);
      }

      // Get the shortest and longest periods
      int shortPeriod = parameters.getPeriods(0);
      int longPeriod = parameters.getPeriods(parameters.getPeriodsCount() - 1);

      // Calculate EMAs
      EMAIndicator shortEma = new EMAIndicator(closePrice, shortPeriod);
      EMAIndicator longEma = new EMAIndicator(closePrice, longPeriod);

      org.ta4j.core.num.Num shortEmaValue = shortEma.getValue(index);
      org.ta4j.core.num.Num longEmaValue = longEma.getValue(index);

      // Calculate oscillator: (short EMA - long EMA) / long EMA * 100
      if (longEmaValue.isZero()) {
        return numOf(0);
      }

      return shortEmaValue.minus(longEmaValue).dividedBy(longEmaValue).multipliedBy(numOf(100));
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }

  /** Simple zero line indicator for crossover rules. */
  private static class ZeroLineIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    public ZeroLineIndicator(BarSeries series) {
      super(series);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      return numOf(0);
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
