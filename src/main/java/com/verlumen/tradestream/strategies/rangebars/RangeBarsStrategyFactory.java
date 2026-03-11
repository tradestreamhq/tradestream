package com.verlumen.tradestream.strategies.rangebars;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.RangeBarsParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class RangeBarsStrategyFactory implements StrategyFactory<RangeBarsParameters> {
  @Override
  public RangeBarsParameters getDefaultParameters() {
    return RangeBarsParameters.newBuilder().setRangeSize(1.0).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, RangeBarsParameters parameters) {
    checkArgument(parameters.getRangeSize() > 0, "Range size must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    RangeMidpointIndicator midpoint = new RangeMidpointIndicator(series, parameters.getRangeSize());

    // Entry: price breaks above the range midpoint + half range (upper breakout)
    Rule entryRule = new OverIndicatorRule(closePrice, midpoint);

    // Exit: price breaks below the range midpoint (lower breakout)
    Rule exitRule = new UnderIndicatorRule(closePrice, midpoint);

    return new BaseStrategy(
        String.format("%s (Range: %.2f)", "RANGE_BARS", parameters.getRangeSize()),
        entryRule,
        exitRule,
        1);
  }

  /**
   * Calculates the midpoint of recent price range, adjusted by the configured range size.
   * When price is above the midpoint, it indicates an upward breakout.
   */
  private static class RangeMidpointIndicator extends CachedIndicator<Num> {
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final double rangeSize;

    RangeMidpointIndicator(BarSeries series, double rangeSize) {
      super(series);
      this.highPrice = new HighPriceIndicator(series);
      this.lowPrice = new LowPriceIndicator(series);
      this.rangeSize = rangeSize;
    }

    @Override
    protected Num calculate(int index) {
      Num high = highPrice.getValue(index);
      Num low = lowPrice.getValue(index);
      Num range = high.minus(low);
      Num scaledRange = range.multipliedBy(numOf(rangeSize));
      return low.plus(scaledRange.dividedBy(numOf(2)));
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
