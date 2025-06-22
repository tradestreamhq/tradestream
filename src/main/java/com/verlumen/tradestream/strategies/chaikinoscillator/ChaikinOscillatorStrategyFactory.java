package com.verlumen.tradestream.strategies.chaikinoscillator;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.ChaikinOscillatorParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class ChaikinOscillatorStrategyFactory
    implements StrategyFactory<ChaikinOscillatorParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, ChaikinOscillatorParameters params) {
    checkArgument(params.getFastPeriod() > 0, "Fast period must be positive");
    checkArgument(params.getSlowPeriod() > 0, "Slow period must be positive");
    checkArgument(
        params.getSlowPeriod() > params.getFastPeriod(),
        "Slow period must be greater than fast period");

    ChaikinOscillatorIndicator chaikin =
        new ChaikinOscillatorIndicator(series, params.getFastPeriod(), params.getSlowPeriod());

    // Entry rule: Chaikin Oscillator crosses above zero
    Rule entryRule = new CrossedUpIndicatorRule(chaikin, series.numOf(0));

    // Exit rule: Chaikin Oscillator crosses below zero
    Rule exitRule = new CrossedDownIndicatorRule(chaikin, series.numOf(0));

    return new BaseStrategy(
        String.format(
            "%s (Fast: %d, Slow: %d)",
            StrategyType.CHAIKIN_OSCILLATOR.name(),
            params.getFastPeriod(),
            params.getSlowPeriod()),
        entryRule,
        exitRule,
        params.getSlowPeriod());
  }

  @Override
  public ChaikinOscillatorParameters getDefaultParameters() {
    return ChaikinOscillatorParameters.newBuilder()
        .setFastPeriod(3) // Standard Chaikin fast period
        .setSlowPeriod(10) // Standard Chaikin slow period
        .build();
  }

  /**
   * Custom Chaikin Oscillator indicator implementation.
   * 
   * The Chaikin Oscillator is calculated as:
   * 1. Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
   * 2. Money Flow Volume = Money Flow Multiplier × Volume
   * 3. Accumulation/Distribution Line = Sum of Money Flow Volume
   * 4. Chaikin Oscillator = EMA(ADL, fast) - EMA(ADL, slow)
   */
  private static class ChaikinOscillatorIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final EMAIndicator fastEma;
    private final EMAIndicator slowEma;
    private final ADLIndicator adl;

    public ChaikinOscillatorIndicator(BarSeries series, int fastPeriod, int slowPeriod) {
      super(series);
      this.adl = new ADLIndicator(series);
      this.fastEma = new EMAIndicator(adl, fastPeriod);
      this.slowEma = new EMAIndicator(adl, slowPeriod);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      return fastEma.getValue(index).minus(slowEma.getValue(index));
    }

    @Override
    public int getUnstableBars() {
      return Math.max(fastEma.getUnstableBars(), slowEma.getUnstableBars());
    }
  }

  /**
   * Accumulation/Distribution Line indicator.
   * ADL = Sum of Money Flow Volume
   */
  private static class ADLIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final MoneyFlowVolumeIndicator mfv;

    public ADLIndicator(BarSeries series) {
      super(series);
      this.mfv = new MoneyFlowVolumeIndicator(series);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      org.ta4j.core.num.Num adl = numOf(0);
      for (int i = 0; i <= index; i++) {
        adl = adl.plus(mfv.getValue(i));
      }
      return adl;
    }

    @Override
    public int getUnstableBars() {
      return 0; // ADL doesn't have unstable bars as it's a cumulative sum
    }
  }

  /**
   * Money Flow Volume indicator.
   * MFV = Money Flow Multiplier × Volume
   */
  private static class MoneyFlowVolumeIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final MoneyFlowMultiplierIndicator mfm;
    private final VolumeIndicator volume;

    public MoneyFlowVolumeIndicator(BarSeries series) {
      super(series);
      this.mfm = new MoneyFlowMultiplierIndicator(series);
      this.volume = new VolumeIndicator(series);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      return mfm.getValue(index).multipliedBy(volume.getValue(index));
    }

    @Override
    public int getUnstableBars() {
      return 0; // No unstable bars as it's just multiplication of current values
    }
  }

  /**
   * Money Flow Multiplier indicator.
   * MFM = ((Close - Low) - (High - Close)) / (High - Low)
   */
  private static class MoneyFlowMultiplierIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final ClosePriceIndicator close;
    private final HighPriceIndicator high;
    private final LowPriceIndicator low;

    public MoneyFlowMultiplierIndicator(BarSeries series) {
      super(series);
      this.close = new ClosePriceIndicator(series);
      this.high = new HighPriceIndicator(series);
      this.low = new LowPriceIndicator(series);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      org.ta4j.core.num.Num closePrice = close.getValue(index);
      org.ta4j.core.num.Num highPrice = high.getValue(index);
      org.ta4j.core.num.Num lowPrice = low.getValue(index);
      
      org.ta4j.core.num.Num highLow = highPrice.minus(lowPrice);
      
      // Avoid division by zero
      if (highLow.isZero()) {
        return numOf(0);
      }
      
      org.ta4j.core.num.Num closeLow = closePrice.minus(lowPrice);
      org.ta4j.core.num.Num highClose = highPrice.minus(closePrice);
      
      return closeLow.minus(highClose).dividedBy(highLow);
    }

    @Override
    public int getUnstableBars() {
      return 0; // No unstable bars as it's just calculation from current bar
    }
  }
}
