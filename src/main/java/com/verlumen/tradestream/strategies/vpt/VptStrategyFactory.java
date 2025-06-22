package com.verlumen.tradestream.strategies.vpt;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.VptParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class VptStrategyFactory implements StrategyFactory<VptParameters> {

  @Override
  public VptParameters getDefaultParameters() {
    return VptParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, VptParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);

    // Calculate VPT (Volume Price Trend)
    VptIndicator vpt = new VptIndicator(closePrice, volume);

    // Calculate SMA of VPT for signal line
    SMAIndicator vptSMA = new SMAIndicator(vpt, parameters.getPeriod());

    // Entry rules: VPT crosses above its SMA
    var entryRule = new CrossedUpIndicatorRule(vpt, vptSMA);

    // Exit rules: VPT crosses below its SMA
    var exitRule = new CrossedDownIndicatorRule(vpt, vptSMA);

    return new org.ta4j.core.BaseStrategy("VPT", entryRule, exitRule, parameters.getPeriod());
  }

  /**
   * Custom indicator that calculates Volume Price Trend (VPT). VPT = Previous VPT + Volume ×
   * ((Close - Previous Close) / Previous Close)
   */
  private static class VptIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final VolumeIndicator volume;

    public VptIndicator(ClosePriceIndicator closePrice, VolumeIndicator volume) {
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
      Num previousClose = closePrice.getValue(index - 1);
      Num currentVolume = volume.getValue(index);

      // Calculate price change percentage
      Num priceChangePercent = currentClose.minus(previousClose).dividedBy(previousClose);

      // Calculate VPT contribution for this period
      Num vptContribution = currentVolume.multipliedBy(priceChangePercent);

      // Add to previous VPT value
      Num previousVpt = getValue(index - 1);
      return previousVpt.plus(vptContribution);
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
