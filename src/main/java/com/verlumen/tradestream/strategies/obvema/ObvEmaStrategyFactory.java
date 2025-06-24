package com.verlumen.tradestream.strategies.obvema;

import com.verlumen.tradestream.strategies.ObvEmaParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class ObvEmaStrategyFactory implements StrategyFactory<ObvEmaParameters> {

  @Override
  public ObvEmaParameters getDefaultParameters() {
    return ObvEmaParameters.newBuilder().setEmaPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, ObvEmaParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);

    // Custom OBV (On Balance Volume) indicator
    OBVIndicator obv = new OBVIndicator(closePrice, volume);

    // EMA of OBV
    EMAIndicator obvEma = new EMAIndicator(obv, parameters.getEmaPeriod());

    // Entry rules: OBV crosses above its EMA (bullish) or below its EMA (bearish)
    var entryRule =
        new CrossedUpIndicatorRule(obv, obvEma).or(new CrossedDownIndicatorRule(obv, obvEma));

    // Exit rules: OBV crosses back to the EMA in the opposite direction
    var exitRule =
        new CrossedDownIndicatorRule(obv, obvEma).or(new CrossedUpIndicatorRule(obv, obvEma));

    return new org.ta4j.core.BaseStrategy(
        "OBV_EMA", entryRule, exitRule, parameters.getEmaPeriod());
  }

  /**
   * Custom On Balance Volume (OBV) indicator. OBV is a momentum indicator that uses volume flow to
   * predict changes in stock price.
   */
  private static class OBVIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final VolumeIndicator volume;

    public OBVIndicator(ClosePriceIndicator closePrice, VolumeIndicator volume) {
      super(closePrice);
      this.closePrice = closePrice;
      this.volume = volume;
    }

    @Override
    protected Num calculate(int index) {
      if (index == 0) {
        return volume.getValue(0);
      }

      Num currentClose = closePrice.getValue(index);
      Num previousClose = closePrice.getValue(index - 1);
      Num currentVolume = volume.getValue(index);

      if (currentClose.isGreaterThan(previousClose)) {
        // Price increased, add volume
        return getValue(index - 1).plus(currentVolume);
      } else if (currentClose.isLessThan(previousClose)) {
        // Price decreased, subtract volume
        return getValue(index - 1).minus(currentVolume);
      } else {
        // Price unchanged, keep previous OBV
        return getValue(index - 1);
      }
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
