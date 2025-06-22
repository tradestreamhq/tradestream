package com.verlumen.tradestream.strategies.cmfzeroline;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.CmfZeroLineParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class CmfZeroLineStrategyFactory implements StrategyFactory<CmfZeroLineParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, CmfZeroLineParameters params) {
    checkArgument(params.getPeriod() > 0, "Period must be positive");

    ChaikinMoneyFlowIndicator cmf = new ChaikinMoneyFlowIndicator(series, params.getPeriod());

    // Entry rule: CMF crosses above zero
    Rule entryRule = new CrossedUpIndicatorRule(cmf, series.numOf(0));

    // Exit rule: CMF crosses below zero
    Rule exitRule = new CrossedDownIndicatorRule(cmf, series.numOf(0));

    return new BaseStrategy(
        String.format("%s (Period: %d)", StrategyType.CMF_ZERO_LINE.name(), params.getPeriod()),
        entryRule,
        exitRule,
        params.getPeriod());
  }

  @Override
  public CmfZeroLineParameters getDefaultParameters() {
    return CmfZeroLineParameters.newBuilder()
        .setPeriod(20) // Standard CMF period
        .build();
  }

  /**
   * Custom Chaikin Money Flow (CMF) indicator implementation.
   *
   * <p>The Chaikin Money Flow is calculated as: 1. Money Flow Multiplier = ((Close - Low) - (High -
   * Close)) / (High - Low) 2. Money Flow Volume = Money Flow Multiplier × Volume 3. CMF = Sum of
   * Money Flow Volume over period / Sum of Volume over period
   */
  private static class ChaikinMoneyFlowIndicator extends CachedIndicator<Num> {
    private final int period;
    private final ClosePriceIndicator closePrice;
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final VolumeIndicator volume;

    public ChaikinMoneyFlowIndicator(BarSeries series, int period) {
      super(series);
      this.period = period;
      this.closePrice = new ClosePriceIndicator(series);
      this.highPrice = new HighPriceIndicator(series);
      this.lowPrice = new LowPriceIndicator(series);
      this.volume = new VolumeIndicator(series);
    }

    @Override
    protected Num calculate(int index) {
      if (index < period - 1) {
        return numOf(0);
      }

      Num sumMoneyFlowVolume = numOf(0);
      Num sumVolume = numOf(0);

      // Calculate over the specified period
      for (int i = index - period + 1; i <= index; i++) {
        Num close = closePrice.getValue(i);
        Num high = highPrice.getValue(i);
        Num low = lowPrice.getValue(i);
        Num vol = volume.getValue(i);

        // Calculate Money Flow Multiplier
        Num highLow = high.minus(low);
        if (highLow.isZero()) {
          // Avoid division by zero - use 0 as multiplier
          sumMoneyFlowVolume = sumMoneyFlowVolume.plus(numOf(0));
        } else {
          Num closeLow = close.minus(low);
          Num highClose = high.minus(close);
          Num moneyFlowMultiplier = closeLow.minus(highClose).dividedBy(highLow);
          
          // Calculate Money Flow Volume
          Num moneyFlowVolume = moneyFlowMultiplier.multipliedBy(vol);
          sumMoneyFlowVolume = sumMoneyFlowVolume.plus(moneyFlowVolume);
        }
        
        sumVolume = sumVolume.plus(vol);
      }

      // Calculate CMF
      if (sumVolume.isZero()) {
        return numOf(0);
      }
      
      return sumMoneyFlowVolume.dividedBy(sumVolume);
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }
}
