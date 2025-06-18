package com.verlumen.tradestream.strategies.atrtrailingstop;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.AtrTrailingStopParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.ATRIndicator;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.PreviousValueIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class AtrTrailingStopStrategyFactory
    implements StrategyFactory<AtrTrailingStopParameters> {

  /**
   * Custom indicator to calculate trailing stop: previousClose - (ATR * multiplier)
   */
  private static class TrailingStopIndicator extends CachedIndicator<Num> {
    private final PreviousValueIndicator previousClose;
    private final ATRIndicator atr;
    private final double multiplier;

    public TrailingStopIndicator(ClosePriceIndicator closePrice, ATRIndicator atr, double multiplier) {
      super(closePrice);
      this.previousClose = new PreviousValueIndicator(closePrice, 1);
      this.atr = atr;
      this.multiplier = multiplier;
    }

    @Override
    protected Num calculate(int index) {
      Num prevClose = previousClose.getValue(index);
      Num atrValue = atr.getValue(index);
      return prevClose.minus(atrValue.multipliedBy(numOf(multiplier)));
    }

    @Override
    public int getUnstableBars() {
      return Math.max(previousClose.getUnstableBars(), atr.getUnstableBars());
    }
  }

  @Override
  public Strategy createStrategy(BarSeries series, AtrTrailingStopParameters params) {
    checkArgument(params.getAtrPeriod() > 0, "ATR period must be positive");
    checkArgument(params.getMultiplier() > 0, "Multiplier must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    ATRIndicator atr = new ATRIndicator(series, params.getAtrPeriod());
    PreviousValueIndicator previousClose = new PreviousValueIndicator(closePrice, 1);

    // Create custom trailing stop indicator
    TrailingStopIndicator trailingStop = new TrailingStopIndicator(closePrice, atr, params.getMultiplier());

    // Entry rule: Simple momentum rule (price above previous close)
    Rule entryRule = new OverIndicatorRule(closePrice, previousClose);

    // Exit rule: Price falls below trailing stop level
    Rule exitRule = new UnderIndicatorRule(closePrice, trailingStop);

    return new BaseStrategy(
        String.format(
            "%s (ATR: %d, Mult: %.2f)",
            getStrategyType().name(), params.getAtrPeriod(), params.getMultiplier()),
        entryRule,
        exitRule,
        params.getAtrPeriod());
  }

  @Override
  public AtrTrailingStopParameters getDefaultParameters() {
    return AtrTrailingStopParameters.newBuilder()
        .setAtrPeriod(14) // Standard ATR period
        .setMultiplier(2.0) // Common multiplier
        .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.ATR_TRAILING_STOP;
  }
}
