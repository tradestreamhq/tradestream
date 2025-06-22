package com.verlumen.tradestream.strategies.tickvolumeanalysis;

import com.verlumen.tradestream.strategies.TickVolumeAnalysisParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class TickVolumeAnalysisStrategyFactory implements StrategyFactory<TickVolumeAnalysisParameters> {

  @Override
  public TickVolumeAnalysisParameters getDefaultParameters() {
    return TickVolumeAnalysisParameters.newBuilder()
        .setTickPeriod(20)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, TickVolumeAnalysisParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);
    
    // Calculate Tick Volume Analysis indicator
    TickVolumeAnalysisIndicator tickVolume = new TickVolumeAnalysisIndicator(closePrice, volume);
    
    // Calculate SMA of tick volume for signal line
    SMAIndicator tickVolumeSMA = new SMAIndicator(tickVolume, parameters.getTickPeriod());
    
    // Entry rules: Tick volume crosses above its SMA (increasing tick activity)
    var entryRule = new CrossedUpIndicatorRule(tickVolume, tickVolumeSMA);
    
    // Exit rules: Tick volume crosses below its SMA (decreasing tick activity)
    var exitRule = new CrossedDownIndicatorRule(tickVolume, tickVolumeSMA);
    
    return new org.ta4j.core.BaseStrategy(
        "TickVolumeAnalysis", entryRule, exitRule, parameters.getTickPeriod());
  }

  /**
   * Custom indicator that calculates Tick Volume Analysis.
   * Analyzes the relationship between price ticks and volume to identify market activity.
   */
  private static class TickVolumeAnalysisIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final VolumeIndicator volume;

    public TickVolumeAnalysisIndicator(ClosePriceIndicator closePrice, VolumeIndicator volume) {
      super(closePrice);
      this.closePrice = closePrice;
      this.volume = volume;
    }

    @Override
    protected Num calculate(int index) {
      if (index == 0) {
        return numOf(0);
      }
      
      Num currentClose = closePrice.getValue(index);
      Num currentVolume = volume.getValue(index);
      
      Num previousClose = closePrice.getValue(index - 1);
      Num previousVolume = volume.getValue(index - 1);
      
      // Calculate price tick (change)
      Num priceTick = currentClose.minus(previousClose);
      
      // Calculate volume tick (change)
      Num volumeTick = currentVolume.minus(previousVolume);
      
      // Calculate tick volume score: combines price movement and volume change
      // Higher values indicate strong tick activity, lower values indicate weak activity
      Num tickVolumeScore = priceTick.abs().multipliedBy(volumeTick.abs());
      
      return tickVolumeScore;
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
} 