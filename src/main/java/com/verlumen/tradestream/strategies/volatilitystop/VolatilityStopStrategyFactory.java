package com.verlumen.tradestream.strategies.volatilitystop;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.VolatilityStopParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.ATRIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.PreviousValueIndicator;
import org.ta4j.core.indicators.helpers.TransformIndicator;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class VolatilityStopStrategyFactory implements StrategyFactory<VolatilityStopParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, VolatilityStopParameters params) {
    checkArgument(params.getAtrPeriod() > 0, "ATR period must be positive");
    checkArgument(params.getMultiplier() > 0, "Multiplier must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    ATRIndicator atr = new ATRIndicator(series, params.getAtrPeriod());
    PreviousValueIndicator previousClose = new PreviousValueIndicator(closePrice, 1);

    // Calculate volatility stop: previous close - (ATR * multiplier)
    TransformIndicator volatilityStop = TransformIndicator.multiply(atr, params.getMultiplier());
    TransformIndicator stopLevel = TransformIndicator.minus(previousClose, volatilityStop);

    // Entry rule: This is typically combined with other entry signals
    // For simplicity, we'll use a basic price momentum rule
    Rule entryRule = new UnderIndicatorRule(closePrice, previousClose);

    // Exit rule: Price falls below volatility stop level
    Rule exitRule = new UnderIndicatorRule(closePrice, stopLevel);

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
  public VolatilityStopParameters getDefaultParameters() {
    return VolatilityStopParameters.newBuilder()
        .setAtrPeriod(14)      // Standard ATR period
        .setMultiplier(2.0)    // Common multiplier for stop distance
        .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.VOLATILITY_STOP;
  }
}
