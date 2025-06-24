package com.verlumen.tradestream.strategies.pivot;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.PivotParameters;
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

public final class PivotStrategyFactory implements StrategyFactory<PivotParameters> {

  @Override
  public PivotParameters getDefaultParameters() {
    return PivotParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, PivotParameters parameters) {
    checkArgument(parameters.getPeriod() > 0, "Period must be positive");
    ClosePriceIndicator close = new ClosePriceIndicator(series);
    PivotPointsIndicator pivot = new PivotPointsIndicator(series, parameters.getPeriod());
    Rule entryRule = new CrossedUpIndicatorRule(close, pivot);
    Rule exitRule = new CrossedDownIndicatorRule(close, pivot);
    return new BaseStrategy("Pivot", entryRule, exitRule, parameters.getPeriod());
  }

  /**
   * Custom indicator to calculate the main pivot point over a lookback period. Pivot = (High + Low
   * + Close) / 3 (classic formula)
   */
  private static class PivotPointsIndicator extends CachedIndicator<Num> {
    private final BarSeries series;
    private final int period;

    public PivotPointsIndicator(BarSeries series, int period) {
      super(series);
      this.series = series;
      this.period = period;
    }

    @Override
    protected Num calculate(int index) {
      int start = Math.max(0, index - period + 1);
      Num high = series.getBar(start).getHighPrice();
      Num low = series.getBar(start).getLowPrice();
      Num close = series.getBar(start).getClosePrice();
      for (int i = start + 1; i <= index; i++) {
        high = high.max(series.getBar(i).getHighPrice());
        low = low.min(series.getBar(i).getLowPrice());
        close = series.getBar(i).getClosePrice();
      }
      return high.plus(low).plus(close).dividedBy(numOf(3));
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }
}
