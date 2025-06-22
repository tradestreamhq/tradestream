package com.verlumen.tradestream.strategies.volumebreakout;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.VolumeBreakoutParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class VolumeBreakoutStrategyFactory
    implements StrategyFactory<VolumeBreakoutParameters> {

  @Override
  public VolumeBreakoutParameters getDefaultParameters() {
    return VolumeBreakoutParameters.newBuilder().setVolumeMultiplier(2.0).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, VolumeBreakoutParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);

    // Calculate average volume over the last 20 periods
    SMAIndicator averageVolume = new SMAIndicator(volume, 20);

    // Volume breakout threshold (average volume * multiplier)
    VolumeBreakoutThreshold volumeThreshold =
        new VolumeBreakoutThreshold(volume, averageVolume, parameters.getVolumeMultiplier());

    // Price moving average for trend direction
    SMAIndicator priceMA = new SMAIndicator(closePrice, 10);

    // Entry rules: Volume breaks above threshold AND price is above moving average
    var entryRule =
        new OverIndicatorRule(volume, volumeThreshold)
            .and(new OverIndicatorRule(closePrice, priceMA));

    // Exit rules: Volume drops below threshold OR price crosses below moving average
    var exitRule =
        new UnderIndicatorRule(volume, volumeThreshold)
            .or(new CrossedDownIndicatorRule(closePrice, priceMA));

    return new org.ta4j.core.BaseStrategy("VOLUME_BREAKOUT", entryRule, exitRule, 20);
  }

  /**
   * Custom indicator that calculates volume breakout threshold. Threshold = average volume *
   * multiplier
   */
  private static class VolumeBreakoutThreshold extends CachedIndicator<Num> {
    private final VolumeIndicator volume;
    private final SMAIndicator averageVolume;
    private final double multiplier;

    public VolumeBreakoutThreshold(
        VolumeIndicator volume, SMAIndicator averageVolume, double multiplier) {
      super(volume);
      this.volume = volume;
      this.averageVolume = averageVolume;
      this.multiplier = multiplier;
    }

    @Override
    protected Num calculate(int index) {
      if (index < 20) {
        return numOf(0);
      }

      Num avgVol = averageVolume.getValue(index);
      return avgVol.multipliedBy(numOf(multiplier));
    }

    @Override
    public int getUnstableBars() {
      return 20;
    }
  }
}
