package com.verlumen.tradestream.strategies.linearregressionchannels;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.LinearRegressionChannelsParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class LinearRegressionChannelsStrategyFactory
    implements StrategyFactory<LinearRegressionChannelsParameters> {

  @Override
  public Strategy createStrategy(BarSeries series, LinearRegressionChannelsParameters params) {
    checkArgument(params.getPeriod() > 0, "Period must be positive");
    checkArgument(params.getMultiplier() > 0, "Multiplier must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    LinearRegressionChannelsIndicator lrcIndicator =
        new LinearRegressionChannelsIndicator(series, params.getPeriod(), params.getMultiplier());

    // Entry: Price crosses above upper channel (breakout)
    Rule entryRule = new CrossedUpIndicatorRule(closePrice, lrcIndicator.getUpperChannel());

    // Exit: Price crosses below lower channel (breakdown)
    Rule exitRule = new CrossedDownIndicatorRule(closePrice, lrcIndicator.getLowerChannel());

    return new BaseStrategy(
        String.format(
            "%s (Period: %d, Multiplier: %.2f)",
            StrategyType.LINEAR_REGRESSION_CHANNELS.name(),
            params.getPeriod(),
            params.getMultiplier()),
        entryRule,
        exitRule,
        params.getPeriod());
  }

  @Override
  public LinearRegressionChannelsParameters getDefaultParameters() {
    return LinearRegressionChannelsParameters.newBuilder().setPeriod(20).setMultiplier(2.0).build();
  }

  /**
   * Custom indicator for Linear Regression Channels. Calculates upper and lower channels based on
   * linear regression with standard deviation bands.
   */
  private static class LinearRegressionChannelsIndicator extends CachedIndicator<Num> {
    private final int period;
    private final double multiplier;
    private final ClosePriceIndicator closePrice;
    private final UpperChannelIndicator upperChannel;
    private final LowerChannelIndicator lowerChannel;

    public LinearRegressionChannelsIndicator(BarSeries series, int period, double multiplier) {
      super(series);
      this.period = period;
      this.multiplier = multiplier;
      this.closePrice = new ClosePriceIndicator(series);
      this.upperChannel = new UpperChannelIndicator(series, period, multiplier);
      this.lowerChannel = new LowerChannelIndicator(series, period, multiplier);
    }

    @Override
    protected Num calculate(int index) {
      // Return the middle line (linear regression)
      return calculateLinearRegression(index);
    }

    @Override
    public int getUnstableBars() {
      return period;
    }

    public UpperChannelIndicator getUpperChannel() {
      return upperChannel;
    }

    public LowerChannelIndicator getLowerChannel() {
      return lowerChannel;
    }

    private Num calculateLinearRegression(int index) {
      if (index < period - 1) {
        return numOf(0);
      }

      // Calculate linear regression using least squares method
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

      // Calculate the value at the current position
      double x = period - 1;
      return numOf(slope * x + intercept);
    }
  }

  private static class UpperChannelIndicator extends CachedIndicator<Num> {
    private final int period;
    private final double multiplier;
    private final ClosePriceIndicator closePrice;

    public UpperChannelIndicator(BarSeries series, int period, double multiplier) {
      super(series);
      this.period = period;
      this.multiplier = multiplier;
      this.closePrice = new ClosePriceIndicator(series);
    }

    @Override
    protected Num calculate(int index) {
      if (index < period - 1) {
        return numOf(0);
      }

      // Calculate standard deviation of residuals
      double sumResiduals = 0, sumResidualsSquared = 0;
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

      // Calculate residuals
      for (int i = 0; i < period; i++) {
        int barIndex = index - period + 1 + i;
        double x = i;
        double y = closePrice.getValue(barIndex).doubleValue();
        double predicted = slope * x + intercept;
        double residual = y - predicted;
        sumResiduals += residual;
        sumResidualsSquared += residual * residual;
      }

      double stdDev =
          Math.sqrt((sumResidualsSquared - (sumResiduals * sumResiduals) / n) / (n - 1));

      // Calculate upper channel
      double x = period - 1;
      double middleLine = slope * x + intercept;
      return numOf(middleLine + multiplier * stdDev);
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }

  private static class LowerChannelIndicator extends CachedIndicator<Num> {
    private final int period;
    private final double multiplier;
    private final ClosePriceIndicator closePrice;

    public LowerChannelIndicator(BarSeries series, int period, double multiplier) {
      super(series);
      this.period = period;
      this.multiplier = multiplier;
      this.closePrice = new ClosePriceIndicator(series);
    }

    @Override
    protected Num calculate(int index) {
      if (index < period - 1) {
        return numOf(0);
      }

      // Calculate standard deviation of residuals
      double sumResiduals = 0, sumResidualsSquared = 0;
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

      // Calculate residuals
      for (int i = 0; i < period; i++) {
        int barIndex = index - period + 1 + i;
        double x = i;
        double y = closePrice.getValue(barIndex).doubleValue();
        double predicted = slope * x + intercept;
        double residual = y - predicted;
        sumResiduals += residual;
        sumResidualsSquared += residual * residual;
      }

      double stdDev =
          Math.sqrt((sumResidualsSquared - (sumResiduals * sumResiduals) / n) / (n - 1));

      // Calculate lower channel
      double x = period - 1;
      double middleLine = slope * x + intercept;
      return numOf(middleLine - multiplier * stdDev);
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }
}
