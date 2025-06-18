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
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.PreviousValueIndicator;
import org.ta4j.core.indicators.helpers.TransformIndicator;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class AtrTrailingStopStrategyFactory
    implements StrategyFactory<AtrTrailingStopParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, AtrTrailingStopParameters params) {
    checkArgument(params.getAtrPeriod() > 0, "ATR period must be positive");
    checkArgument(params.getMultiplier() > 0, "Multiplier must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    ATRIndicator atr = new ATRIndicator(series, params.getAtrPeriod());
    PreviousValueIndicator previousClose = new PreviousValueIndicator(closePrice, 1);

    // Calculate trailing stop: previous close - (ATR * multiplier)
    // In a real implementation, the trailing stop would move only upward for long positions
    TransformIndicator atrMultiplied = TransformIndicator.multiply(atr, params.getMultiplier());
    TransformIndicator trailingStop = TransformIndicator.minus(previousClose, atrMultiplied);

    // Entry rule: Simple momentum rule (price above previous close)
    Rule entryRule = new UnderIndicatorRule(previousClose, closePrice);

    // Exit rule: Price falls below trailing stop level
    Rule exitRule = new UnderIndicatorRule(closePrice, trailingStop);

    return new BaseStrategy(
        String.format("%s (ATR: %d, Mult: %.2f)",
            getStrategyType().name(),
            params.getAtrPeriod(),
            params.getMultiplier()),
        entryRule,
        exitRule,
        params.getAtrPeriod());
  }

  @Override
  public AtrTrailingStopParameters getDefaultParameters() {
    return AtrTrailingStopParameters.newBuilder()
        .setAtrPeriod(14)      // Standard ATR period
        .setMultiplier(2.0)    // Common multiplier
        .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.ATR_TRAILING_STOP;
  }
}
