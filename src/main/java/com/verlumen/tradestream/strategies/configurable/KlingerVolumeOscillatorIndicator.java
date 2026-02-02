package com.verlumen.tradestream.strategies.configurable;

import org.ta4j.core.BarSeries;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;

/**
 * Klinger Volume Oscillator indicator. The KVO is a volume-based indicator that combines price and
 * volume to identify trend changes.
 */
public final class KlingerVolumeOscillatorIndicator extends CachedIndicator<Num> {
  private final ClosePriceIndicator closePrice;
  private final HighPriceIndicator highPrice;
  private final LowPriceIndicator lowPrice;
  private final VolumeIndicator volume;
  private final int shortPeriod;
  private final int longPeriod;

  public KlingerVolumeOscillatorIndicator(BarSeries series, int shortPeriod, int longPeriod) {
    super(series);
    this.closePrice = new ClosePriceIndicator(series);
    this.highPrice = new HighPriceIndicator(series);
    this.lowPrice = new LowPriceIndicator(series);
    this.volume = new VolumeIndicator(series);
    this.shortPeriod = shortPeriod;
    this.longPeriod = longPeriod;
  }

  @Override
  protected Num calculate(int index) {
    if (index < Math.max(shortPeriod, longPeriod)) {
      return numOf(0);
    }

    // Calculate trend direction
    Num trend = numOf(0);
    if (index > 0) {
      Num currentClose = closePrice.getValue(index);
      Num previousClose = closePrice.getValue(index - 1);
      if (currentClose.isGreaterThan(previousClose)) {
        trend = numOf(1); // Upward trend
      } else if (currentClose.isLessThan(previousClose)) {
        trend = numOf(-1); // Downward trend
      }
    }

    // Calculate daily force
    Num dailyForce = numOf(0);
    if (index > 0) {
      Num high = highPrice.getValue(index);
      Num low = lowPrice.getValue(index);
      Num close = closePrice.getValue(index);
      Num prevClose = closePrice.getValue(index - 1);
      Num vol = volume.getValue(index);

      Num range = high.minus(low);
      if (!range.isZero()) {
        Num priceChange = close.minus(prevClose);

        // Daily force calculation
        if (trend.isGreaterThan(numOf(0))) {
          dailyForce = vol.multipliedBy(priceChange).dividedBy(range);
        } else if (trend.isLessThan(numOf(0))) {
          dailyForce = vol.multipliedBy(numOf(0).minus(priceChange)).dividedBy(range);
        }
      }
    }

    // Calculate KVO as difference between short and long EMAs of daily force
    Num shortEMA = calculateEMA(index, shortPeriod, dailyForce);
    Num longEMA = calculateEMA(index, longPeriod, dailyForce);

    return shortEMA.minus(longEMA);
  }

  private Num calculateEMA(int index, int period, Num value) {
    if (index < period) {
      return value;
    }

    Num multiplier = numOf(2.0 / (period + 1));
    Num prevEMA = getValue(index - 1);

    return value.multipliedBy(multiplier).plus(prevEMA.multipliedBy(numOf(1).minus(multiplier)));
  }

  @Override
  public int getUnstableBars() {
    return Math.max(shortPeriod, longPeriod);
  }
}
