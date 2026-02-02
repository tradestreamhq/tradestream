package com.verlumen.tradestream.strategies.configurable;

import org.ta4j.core.Indicator;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.num.Num;

/**
 * An indicator that returns the value of another indicator from N bars ago. This is useful for
 * comparing current values with previous values.
 */
public final class PreviousValueIndicator extends CachedIndicator<Num> {

  private final Indicator<Num> indicator;
  private final int n;

  /**
   * Creates a PreviousValueIndicator.
   *
   * @param indicator the indicator to get previous values from
   * @param n the number of bars to look back (1 = previous bar)
   */
  public PreviousValueIndicator(Indicator<Num> indicator, int n) {
    super(indicator);
    this.indicator = indicator;
    this.n = n;
  }

  @Override
  protected Num calculate(int index) {
    int previousIndex = index - n;
    if (previousIndex < 0) {
      return numOf(0);
    }
    return indicator.getValue(previousIndex);
  }

  @Override
  public int getUnstableBars() {
    return n;
  }
}
