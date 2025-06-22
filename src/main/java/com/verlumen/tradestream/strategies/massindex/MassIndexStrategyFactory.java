package com.verlumen.tradestream.strategies.massindex;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.MassIndexParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

/**
 * Factory for creating Mass Index strategies.
 *
 * <p>The Mass Index is designed to identify trend reversals based on changes in the High-Low range.
 * It looks for a "reversal bulge" where the Mass Index rises above 27 and then falls below 26.5.
 */
public final class MassIndexStrategyFactory implements StrategyFactory<MassIndexParameters> {

  @Override
  public MassIndexParameters getDefaultParameters() {
    return MassIndexParameters.newBuilder()
        .setEmaPeriod(9)
        .setSumPeriod(25)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries barSeries, MassIndexParameters parameters) {
    checkArgument(parameters.getEmaPeriod() > 0, "EMA period must be positive");
    checkArgument(parameters.getSumPeriod() > 0, "Sum period must be positive");

    // Create the Mass Index indicator
    MassIndexIndicator massIndex = new MassIndexIndicator(barSeries, parameters);

    // Entry rule: Mass Index rises above 27 and then falls below 26.5 (reversal bulge)
    Rule entryRule = new CrossedDownIndicatorRule(massIndex, new ConstantIndicator(barSeries, 26.5));

    // Exit rule: Mass Index rises above 27 again or falls below 25
    Rule exitRule = new CrossedUpIndicatorRule(massIndex, new ConstantIndicator(barSeries, 27))
        .or(new CrossedDownIndicatorRule(massIndex, new ConstantIndicator(barSeries, 25)));

    return new BaseStrategy(entryRule, exitRule);
  }

  /**
   * Custom High-Low Range indicator.
   */
  private static class HighLowRangeIndicator extends CachedIndicator<org.ta4j.core.num.Num> {

    public HighLowRangeIndicator(BarSeries barSeries) {
      super(barSeries);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      org.ta4j.core.Bar bar = getBarSeries().getBar(index);
      return bar.getHighPrice().minus(bar.getLowPrice());
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }

  /**
   * Custom Mass Index indicator implementation.
   *
   * <p>The Mass Index is calculated as:
   * 1. High-Low range
   * 2. EMA of High-Low range
   * 3. Double EMA of High-Low range
   * 4. Sum of EMA/Double EMA ratios over the specified period
   */
  private static class MassIndexIndicator extends CachedIndicator<org.ta4j.core.num.Num> {

    private final HighLowRangeIndicator highLow;
    private final EMAIndicator ema;
    private final EMAIndicator doubleEma;
    private final SMAIndicator sumIndicator;
    private final int sumPeriod;

    public MassIndexIndicator(BarSeries barSeries, MassIndexParameters parameters) {
      super(barSeries);
      this.highLow = new HighLowRangeIndicator(barSeries);
      this.ema = new EMAIndicator(highLow, parameters.getEmaPeriod());
      this.doubleEma = new EMAIndicator(ema, parameters.getEmaPeriod());
      this.sumPeriod = parameters.getSumPeriod();
      
      // Create a ratio indicator and then sum it
      EmaRatioIndicator ratioIndicator = new EmaRatioIndicator(ema, doubleEma);
      this.sumIndicator = new SMAIndicator(ratioIndicator, sumPeriod);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      if (index < sumPeriod - 1) {
        return numOf(0);
      }
      return sumIndicator.getValue(index);
    }

    @Override
    public int getUnstableBars() {
      return sumPeriod + ema.getUnstableBars() * 2;
    }
  }

  /**
   * Indicator that calculates the ratio of EMA to Double EMA.
   */
  private static class EmaRatioIndicator extends CachedIndicator<org.ta4j.core.num.Num> {

    private final EMAIndicator ema;
    private final EMAIndicator doubleEma;

    public EmaRatioIndicator(EMAIndicator ema, EMAIndicator doubleEma) {
      super(ema.getBarSeries());
      this.ema = ema;
      this.doubleEma = doubleEma;
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      org.ta4j.core.num.Num emaValue = ema.getValue(index);
      org.ta4j.core.num.Num doubleEmaValue = doubleEma.getValue(index);
      
      if (doubleEmaValue.isZero()) {
        return numOf(0);
      }
      
      return emaValue.dividedBy(doubleEmaValue);
    }

    @Override
    public int getUnstableBars() {
      return Math.max(ema.getUnstableBars(), doubleEma.getUnstableBars());
    }
  }

  /**
   * Constant indicator for comparison.
   */
  private static class ConstantIndicator extends CachedIndicator<org.ta4j.core.num.Num> {

    private final org.ta4j.core.num.Num value;

    public ConstantIndicator(BarSeries barSeries, double value) {
      super(barSeries);
      this.value = numOf(value);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      return value;
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
} 