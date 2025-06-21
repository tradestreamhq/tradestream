package com.verlumen.tradestream.strategies.rvi;

import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.OpenPriceIndicator;
import org.ta4j.core.num.Num;

/**
 * Relative Vigor Index (RVI) indicator.
 *
 * <p>The RVI is calculated as a simple moving average of the ratio: (Close - Open) / (High - Low)
 */
public class RviIndicator extends CachedIndicator<Num> {
  private final ClosePriceIndicator closePrice;
  private final OpenPriceIndicator openPrice;
  private final HighPriceIndicator highPrice;
  private final LowPriceIndicator lowPrice;
  private final int period;

  public RviIndicator(
      ClosePriceIndicator closePrice,
      OpenPriceIndicator openPrice,
      HighPriceIndicator highPrice,
      LowPriceIndicator lowPrice,
      int period) {
    super(closePrice);
    this.closePrice = closePrice;
    this.openPrice = openPrice;
    this.highPrice = highPrice;
    this.lowPrice = lowPrice;
    this.period = period;
  }

  @Override
  protected Num calculate(int index) {
    if (index < period - 1) {
      return numOf(0);
    }

    Num sum = numOf(0);
    int count = 0;

    for (int i = index - period + 1; i <= index; i++) {
      Num close = closePrice.getValue(i);
      Num open = openPrice.getValue(i);
      Num high = highPrice.getValue(i);
      Num low = lowPrice.getValue(i);

      Num range = high.minus(low);

      // Avoid division by zero
      if (range.isZero()) {
        continue;
      }

      Num rviValue = close.minus(open).dividedBy(range);
      sum = sum.plus(rviValue);
      count++;
    }

    if (count == 0) {
      return numOf(0);
    }

    return sum.dividedBy(numOf(count));
  }

  @Override
  public int getCountOfUnstableBars() {
    return period;
  }
}
