package com.verlumen.tradestream.strategies.vwapmeanreversion;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.VwapMeanReversionParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.indicators.volume.VWAPIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class VwapMeanReversionStrategyFactory
    implements StrategyFactory<VwapMeanReversionParameters> {

  @Override
  public VwapMeanReversionParameters getDefaultParameters() {
    return VwapMeanReversionParameters.newBuilder()
        .setVwapPeriod(20)
        .setMovingAveragePeriod(20)
        .setDeviationMultiplier(2.0)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, VwapMeanReversionParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);

    // VWAP indicator
    VWAPIndicator vwap = new VWAPIndicator(series, parameters.getVwapPeriod());

    // Moving average
    SMAIndicator sma = new SMAIndicator(closePrice, parameters.getMovingAveragePeriod());

    // Upper and lower bands based on deviation
    VwapUpperBandIndicator upperBand =
        new VwapUpperBandIndicator(vwap, sma, parameters.getDeviationMultiplier());
    VwapLowerBandIndicator lowerBand =
        new VwapLowerBandIndicator(vwap, sma, parameters.getDeviationMultiplier());

    // Entry rules: price crosses above upper band (short) or below lower band (long)
    var entryRule =
        new CrossedUpIndicatorRule(closePrice, upperBand)
            .or(new CrossedDownIndicatorRule(closePrice, lowerBand));

    // Exit rules: price crosses back to the mean (VWAP or SMA)
    var exitRule =
        new CrossedDownIndicatorRule(closePrice, vwap)
            .or(new CrossedUpIndicatorRule(closePrice, vwap))
            .or(new CrossedDownIndicatorRule(closePrice, sma))
            .or(new CrossedUpIndicatorRule(closePrice, sma));

    return new org.ta4j.core.BaseStrategy(
        "VWAP_MEAN_REVERSION", entryRule, exitRule, parameters.getVwapPeriod());
  }

  // Custom indicator for upper band
  private static class VwapUpperBandIndicator extends CachedIndicator<Num> {
    private final VWAPIndicator vwap;
    private final SMAIndicator sma;
    private final double deviationMultiplier;

    public VwapUpperBandIndicator(
        VWAPIndicator vwap, SMAIndicator sma, double deviationMultiplier) {
      super(vwap.getBarSeries());
      this.vwap = vwap;
      this.sma = sma;
      this.deviationMultiplier = deviationMultiplier;
    }

    @Override
    protected Num calculate(int index) {
      Num vwapValue = vwap.getValue(index);
      Num smaValue = sma.getValue(index);
      Num deviation =
          vwapValue.minus(smaValue).abs().multipliedBy(vwapValue.numOf(deviationMultiplier));
      return vwapValue.plus(deviation);
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }

  // Custom indicator for lower band
  private static class VwapLowerBandIndicator extends CachedIndicator<Num> {
    private final VWAPIndicator vwap;
    private final SMAIndicator sma;
    private final double deviationMultiplier;

    public VwapLowerBandIndicator(
        VWAPIndicator vwap, SMAIndicator sma, double deviationMultiplier) {
      super(vwap.getBarSeries());
      this.vwap = vwap;
      this.sma = sma;
      this.deviationMultiplier = deviationMultiplier;
    }

    @Override
    protected Num calculate(int index) {
      Num vwapValue = vwap.getValue(index);
      Num smaValue = sma.getValue(index);
      Num deviation =
          vwapValue.minus(smaValue).abs().multipliedBy(vwapValue.numOf(deviationMultiplier));
      return vwapValue.minus(deviation);
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
