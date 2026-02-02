package com.verlumen.tradestream.strategies.configurable;

import org.ta4j.core.BarSeries;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.num.Num;

/**
 * Mass Index indicator implementation. The Mass Index is designed to identify trend reversals based
 * on changes in the High-Low range. It looks for a "reversal bulge" where the Mass Index rises
 * above 27 and then falls below 26.5.
 *
 * <p>Calculation: 1. High-Low range 2. EMA of High-Low range 3. Double EMA of High-Low range 4.
 * Sum of EMA/Double EMA ratios over the specified period
 */
public final class MassIndexIndicator extends CachedIndicator<Num> {

  private final HighLowRangeIndicator highLow;
  private final EMAIndicator ema;
  private final EMAIndicator doubleEma;
  private final int sumPeriod;

  public MassIndexIndicator(BarSeries series, int emaPeriod, int sumPeriod) {
    super(series);
    this.highLow = new HighLowRangeIndicator(series);
    this.ema = new EMAIndicator(highLow, emaPeriod);
    this.doubleEma = new EMAIndicator(ema, emaPeriod);
    this.sumPeriod = sumPeriod;
  }

  @Override
  protected Num calculate(int index) {
    if (index < sumPeriod - 1) {
      return numOf(0);
    }

    // Sum the EMA/Double EMA ratios over sumPeriod
    Num sum = numOf(0);
    for (int i = 0; i < sumPeriod; i++) {
      int idx = index - i;
      if (idx >= 0) {
        Num emaValue = ema.getValue(idx);
        Num doubleEmaValue = doubleEma.getValue(idx);
        if (!doubleEmaValue.isZero()) {
          sum = sum.plus(emaValue.dividedBy(doubleEmaValue));
        }
      }
    }
    return sum;
  }

  @Override
  public int getUnstableBars() {
    return sumPeriod + ema.getUnstableBars() * 2;
  }

  /** Custom High-Low Range indicator. */
  private static class HighLowRangeIndicator extends CachedIndicator<Num> {

    public HighLowRangeIndicator(BarSeries series) {
      super(series);
    }

    @Override
    protected Num calculate(int index) {
      var bar = getBarSeries().getBar(index);
      return bar.getHighPrice().minus(bar.getLowPrice());
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
