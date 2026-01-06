package com.verlumen.tradestream.strategies.regressionchannel;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.RegressionChannelParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class RegressionChannelStrategyFactory
    implements StrategyFactory<RegressionChannelParameters> {
  @Override
  public RegressionChannelParameters getDefaultParameters() {
    return RegressionChannelParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, RegressionChannelParameters params) {
    checkArgument(params.getPeriod() > 0, "Period must be positive");
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    RegressionChannelIndicator regression =
        new RegressionChannelIndicator(series, params.getPeriod());
    Rule entryRule = new CrossedUpIndicatorRule(closePrice, regression);
    Rule exitRule = new CrossedDownIndicatorRule(closePrice, regression);
    return new BaseStrategy(
        String.format("%s (Period: %d)", "REGRESSION_CHANNEL", params.getPeriod()),
        entryRule,
        exitRule,
        params.getPeriod());
  }

  /** Custom indicator for Regression Channel (linear regression line only). */
  private static class RegressionChannelIndicator extends CachedIndicator<Num> {
    private final int period;
    private final ClosePriceIndicator closePrice;

    public RegressionChannelIndicator(BarSeries series, int period) {
      super(series);
      this.period = period;
      this.closePrice = new ClosePriceIndicator(series);
    }

    @Override
    protected Num calculate(int index) {
      if (index < period - 1) {
        return numOf(0);
      }
      double sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
      for (int i = 0; i < period; i++) {
        int barIndex = index - period + 1 + i;
        double x = i;
        double y = closePrice.getValue(barIndex).doubleValue();
        sumX += x;
        sumY += y;
        sumXY += x * y;
        sumX2 += x * x;
      }
      double n = period;
      double slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
      double intercept = (sumY - slope * sumX) / n;
      double x = period - 1;
      return numOf(slope * x + intercept);
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }
}
