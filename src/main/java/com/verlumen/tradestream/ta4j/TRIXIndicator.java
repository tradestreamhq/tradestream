package com.verlumen.tradestream.ta4j;

import org.ta4j.core.BarSeries;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

/**
 * TRIX (Triple Exponential Average) indicator.
 *
 * <p>TRIX is a momentum oscillator that shows the percentage rate of change of a triple
 * exponentially smoothed moving average. It is designed to filter out insignificant price
 * movements.
 */
public class TRIXIndicator extends CachedIndicator<Num> {

  private final EMAIndicator ema1;
  private final EMAIndicator ema2;
  private final EMAIndicator ema3;
  private final int barCount;

  /**
   * Constructor.
   *
   * @param series the bar series
   * @param barCount the number of bars for the EMA calculation
   */
  public TRIXIndicator(BarSeries series, int barCount) {
    super(series);
    this.barCount = barCount;

    // First EMA
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    this.ema1 = new EMAIndicator(closePrice, barCount);

    // Second EMA (of the first EMA)
    this.ema2 = new EMAIndicator(ema1, barCount);

    // Third EMA (of the second EMA)
    this.ema3 = new EMAIndicator(ema2, barCount);
  }

  @Override
  protected Num calculate(int index) {
    if (index < barCount * 3 - 1) {
      return numOf(0);
    }

    Num currentValue = ema3.getValue(index);
    Num previousValue = ema3.getValue(index - 1);

    if (previousValue.isZero()) {
      return numOf(0);
    }

    // TRIX = (current - previous) / previous * 100
    return currentValue.minus(previousValue).dividedBy(previousValue).multipliedBy(numOf(100));
  }

  @Override
  public int getUnstableBars() {
    return barCount * 3;
  }
}
