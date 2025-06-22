package com.verlumen.tradestream.strategies.klingervolume;

import com.verlumen.tradestream.strategies.KlingerVolumeParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class KlingerVolumeStrategyFactory implements StrategyFactory<KlingerVolumeParameters> {

  @Override
  public KlingerVolumeParameters getDefaultParameters() {
    return KlingerVolumeParameters.newBuilder()
        .setShortPeriod(10)
        .setLongPeriod(35)
        .setSignalPeriod(10)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, KlingerVolumeParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    HighPriceIndicator highPrice = new HighPriceIndicator(series);
    LowPriceIndicator lowPrice = new LowPriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);
    
    // Custom Klinger Volume Oscillator
    KlingerVolumeOscillator kvo = new KlingerVolumeOscillator(closePrice, highPrice, lowPrice, volume, parameters.getShortPeriod(), parameters.getLongPeriod());
    
    // Signal line (EMA of KVO)
    EMAIndicator signalLine = new EMAIndicator(kvo, parameters.getSignalPeriod());
    
    // Entry rules: KVO crosses above signal line (bullish) or below signal line (bearish)
    var entryRule = 
        new CrossedUpIndicatorRule(kvo, signalLine)
            .or(new CrossedDownIndicatorRule(kvo, signalLine));
    
    // Exit rules: KVO crosses back to signal line in the opposite direction
    var exitRule = 
        new CrossedDownIndicatorRule(kvo, signalLine)
            .or(new CrossedUpIndicatorRule(kvo, signalLine));
    
    return new org.ta4j.core.BaseStrategy(
        "KLINGER_VOLUME", entryRule, exitRule, Math.max(parameters.getLongPeriod(), parameters.getSignalPeriod()));
  }

  /**
   * Custom Klinger Volume Oscillator indicator.
   * The KVO is a volume-based indicator that combines price and volume to identify trend changes.
   */
  private static class KlingerVolumeOscillator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final VolumeIndicator volume;
    private final int shortPeriod;
    private final int longPeriod;

    public KlingerVolumeOscillator(ClosePriceIndicator closePrice, HighPriceIndicator highPrice, 
                                  LowPriceIndicator lowPrice, VolumeIndicator volume, 
                                  int shortPeriod, int longPeriod) {
      super(closePrice);
      this.closePrice = closePrice;
      this.highPrice = highPrice;
      this.lowPrice = lowPrice;
      this.volume = volume;
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
        Num priceChange = close.minus(prevClose);
        
        // Daily force calculation
        if (trend.isGreaterThan(numOf(0))) {
          dailyForce = vol.multipliedBy(priceChange).dividedBy(range);
        } else if (trend.isLessThan(numOf(0))) {
          dailyForce = vol.multipliedBy(numOf(0).minus(priceChange)).dividedBy(range);
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
} 