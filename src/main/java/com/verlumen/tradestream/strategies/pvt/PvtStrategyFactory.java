package com.verlumen.tradestream.strategies.pvt;

import com.verlumen.tradestream.strategies.PvtParameters;
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

public final class PvtStrategyFactory implements StrategyFactory<PvtParameters> {

  @Override
  public PvtParameters getDefaultParameters() {
    return PvtParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, PvtParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);

    // Calculate PVT (Price Volume Trend)
    PvtIndicator pvt = new PvtIndicator(closePrice, volume);

    // Calculate SMA of PVT for signal line
    SMAIndicator pvtSMA = new SMAIndicator(pvt, parameters.getPeriod());

    // Entry rules: PVT crosses above its SMA
    var entryRule = new CrossedUpIndicatorRule(pvt, pvtSMA);

    // Exit rules: PVT crosses below its SMA
    var exitRule = new CrossedDownIndicatorRule(pvt, pvtSMA);

    return new org.ta4j.core.BaseStrategy("PVT", entryRule, exitRule, parameters.getPeriod());
  }

  /**
   * Custom indicator that calculates Price Volume Trend (PVT). PVT = Previous PVT + Volume ×
   * ((Close - Previous Close) / Previous Close)
   */
  private static class PvtIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final VolumeIndicator volume;

    public PvtIndicator(ClosePriceIndicator closePrice, VolumeIndicator volume) {
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

      // Calculate PVT contribution for this period
      Num pvtContribution = currentVolume.multipliedBy(priceChangePercent);

      // Add to previous PVT value
      Num previousPvt = getValue(index - 1);
      return previousPvt.plus(pvtContribution);
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
