package com.verlumen.tradestream.strategies.volumespreadanalysis;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.VolumeSpreadAnalysisParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class VolumeSpreadAnalysisStrategyFactory implements StrategyFactory<VolumeSpreadAnalysisParameters> {

  @Override
  public VolumeSpreadAnalysisParameters getDefaultParameters() {
    return VolumeSpreadAnalysisParameters.newBuilder().setVolumePeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, VolumeSpreadAnalysisParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    HighPriceIndicator highPrice = new HighPriceIndicator(series);
    LowPriceIndicator lowPrice = new LowPriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);
    
    // Calculate Volume Spread Analysis (VSA) indicator
    VolumeSpreadAnalysisIndicator vsa = new VolumeSpreadAnalysisIndicator(closePrice, highPrice, lowPrice, volume);
    
    // Calculate SMA of VSA for signal line
    SMAIndicator vsaSMA = new SMAIndicator(vsa, parameters.getVolumePeriod());
    
    // Entry rules: VSA crosses above its SMA (bullish volume spread)
    var entryRule = new CrossedUpIndicatorRule(vsa, vsaSMA);
    
    // Exit rules: VSA crosses below its SMA (bearish volume spread)
    var exitRule = new CrossedDownIndicatorRule(vsa, vsaSMA);
    
    return new org.ta4j.core.BaseStrategy(
        "VolumeSpreadAnalysis", entryRule, exitRule, parameters.getVolumePeriod());
  }

  /**
   * Custom indicator that calculates Volume Spread Analysis (VSA).
   * VSA combines volume, price spread, and closing position to identify market sentiment.
   */
  private static class VolumeSpreadAnalysisIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final VolumeIndicator volume;

    public VolumeSpreadAnalysisIndicator(ClosePriceIndicator closePrice, HighPriceIndicator highPrice, 
                                       LowPriceIndicator lowPrice, VolumeIndicator volume) {
      super(closePrice);
      this.closePrice = closePrice;
      this.highPrice = highPrice;
      this.lowPrice = lowPrice;
      this.volume = volume;
    }

    @Override
    protected Num calculate(int index) {
      if (index == 0) {
        return numOf(0);
      }
      
      Num currentClose = closePrice.getValue(index);
      Num currentHigh = highPrice.getValue(index);
      Num currentLow = lowPrice.getValue(index);
      Num currentVolume = volume.getValue(index);
      
      Num previousClose = closePrice.getValue(index - 1);
      Num previousVolume = volume.getValue(index - 1);
      
      // Calculate price spread (range)
      Num priceSpread = currentHigh.minus(currentLow);
      
      // Calculate closing position (where close is within the range)
      Num range = currentHigh.minus(currentLow);
      Num closePosition = currentClose.minus(currentLow).dividedBy(range);
      
      // Calculate volume ratio
      Num volumeRatio = currentVolume.dividedBy(previousVolume);
      
      // VSA score: combines volume, spread, and closing position
      // Higher values indicate bullish sentiment, lower values indicate bearish sentiment
      Num vsaScore = volumeRatio.multipliedBy(closePosition).multipliedBy(priceSpread);
      return vsaScore;
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
} 