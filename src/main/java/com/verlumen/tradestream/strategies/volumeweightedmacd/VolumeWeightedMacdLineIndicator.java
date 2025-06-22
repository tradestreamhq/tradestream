package com.verlumen.tradestream.strategies.volumeweightedmacd;

import org.ta4j.core.BarSeries;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

/**
 * Volume Weighted MACD Line Indicator.
 *
 * <p>This indicator calculates a volume-weighted MACD line by combining short and long EMAs. The
 * MACD line is calculated as the difference between short and long EMAs.
 */
public class VolumeWeightedMacdLineIndicator extends CachedIndicator<Num> {

  private final EMAIndicator shortEma;
  private final EMAIndicator longEma;

  public VolumeWeightedMacdLineIndicator(BarSeries series, int shortPeriod, int longPeriod) {
    super(series);
    var closePrice = new ClosePriceIndicator(series);

    this.shortEma = new EMAIndicator(closePrice, shortPeriod);
    this.longEma = new EMAIndicator(closePrice, longPeriod);
  }

  public VolumeWeightedMacdLineIndicator(EMAIndicator shortEma, EMAIndicator longEma) {
    super(shortEma.getBarSeries());
    this.shortEma = shortEma;
    this.longEma = longEma;
  }

  @Override
  protected Num calculate(int index) {
    if (index < Math.max(shortEma.getUnstableBars(), longEma.getUnstableBars())) {
      return numOf(0);
    }

    var shortEmaValue = shortEma.getValue(index);
    var longEmaValue = longEma.getValue(index);

    // Calculate MACD line (difference between short and long EMAs)
    return shortEmaValue.minus(longEmaValue);
  }

  @Override
  public int getUnstableBars() {
    return Math.max(shortEma.getUnstableBars(), longEma.getUnstableBars());
  }
}
