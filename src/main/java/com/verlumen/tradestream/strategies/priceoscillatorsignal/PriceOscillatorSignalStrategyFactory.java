package com.verlumen.tradestream.strategies.priceoscillatorsignal;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.PriceOscillatorSignalParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class PriceOscillatorSignalStrategyFactory
    implements StrategyFactory<PriceOscillatorSignalParameters> {

  @Override
  public PriceOscillatorSignalParameters getDefaultParameters() {
    return PriceOscillatorSignalParameters.newBuilder()
        .setFastPeriod(10)
        .setSlowPeriod(20)
        .setSignalPeriod(9)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, PriceOscillatorSignalParameters parameters) {
    checkArgument(
        parameters.getFastPeriod() < parameters.getSlowPeriod(),
        "Fast period must be less than slow period");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);

    // Create the Price Oscillator indicator
    PriceOscillatorIndicator priceOscillator = new PriceOscillatorIndicator(series, parameters);

    // Create the Signal Line indicator (EMA of the Price Oscillator)
    SignalLineIndicator signalLine =
        new SignalLineIndicator(priceOscillator, parameters.getSignalPeriod());

    // Entry rule: Buy when Price Oscillator crosses above Signal Line
    Rule entryRule = new CrossedUpIndicatorRule(priceOscillator, signalLine);

    // Exit rule: Sell when Price Oscillator crosses below Signal Line
    Rule exitRule = new CrossedDownIndicatorRule(priceOscillator, signalLine);

    return new BaseStrategy("Price Oscillator Signal", entryRule, exitRule);
  }

  /**
   * Custom Price Oscillator indicator that calculates the difference between fast and slow moving
   * averages.
   */
  private static class PriceOscillatorIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final PriceOscillatorSignalParameters parameters;
    private final ClosePriceIndicator closePrice;

    public PriceOscillatorIndicator(BarSeries series, PriceOscillatorSignalParameters parameters) {
      super(series);
      this.parameters = parameters;
      this.closePrice = new ClosePriceIndicator(series);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      // Calculate fast and slow EMAs
      EMAIndicator fastEma = new EMAIndicator(closePrice, parameters.getFastPeriod());
      EMAIndicator slowEma = new EMAIndicator(closePrice, parameters.getSlowPeriod());

      org.ta4j.core.num.Num fastEmaValue = fastEma.getValue(index);
      org.ta4j.core.num.Num slowEmaValue = slowEma.getValue(index);

      // Price Oscillator = Fast EMA - Slow EMA
      return fastEmaValue.minus(slowEmaValue);
    }

    @Override
    public int getUnstableBars() {
      return Math.max(parameters.getFastPeriod(), parameters.getSlowPeriod());
    }
  }

  /** Signal Line indicator that calculates EMA of the Price Oscillator. */
  private static class SignalLineIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final PriceOscillatorIndicator priceOscillator;
    private final int signalPeriod;

    public SignalLineIndicator(PriceOscillatorIndicator priceOscillator, int signalPeriod) {
      super(priceOscillator.getBarSeries());
      this.priceOscillator = priceOscillator;
      this.signalPeriod = signalPeriod;
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      // Calculate EMA of the Price Oscillator
      EMAIndicator signalEma = new EMAIndicator(priceOscillator, signalPeriod);
      return signalEma.getValue(index);
    }

    @Override
    public int getUnstableBars() {
      return signalPeriod;
    }
  }
}
