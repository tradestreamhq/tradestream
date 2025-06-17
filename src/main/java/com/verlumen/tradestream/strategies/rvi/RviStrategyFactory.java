package com.verlumen.tradestream.strategies.rvi;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.RviParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.OpenPriceIndicator;
import org.ta4j.core.indicators.helpers.TransformIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class RviStrategyFactory implements StrategyFactory<RviParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, RviParameters params) {
    checkArgument(params.getPeriod() > 0, "RVI period must be positive");

    // Calculate RVI components
    ClosePriceIndicator close = new ClosePriceIndicator(series);
    OpenPriceIndicator open = new OpenPriceIndicator(series);
    HighPriceIndicator high = new HighPriceIndicator(series);
    LowPriceIndicator low = new LowPriceIndicator(series);

    // RVI calculation: SMA((Close - Open) / (High - Low), period)
    // Simplified version using available indicators
    TransformIndicator numerator = TransformIndicator.minus(close, open);
    TransformIndicator denominator = TransformIndicator.minus(high, low);
    TransformIndicator rviRaw = TransformIndicator.divide(numerator, denominator);
    
    SMAIndicator rvi = new SMAIndicator(rviRaw, params.getPeriod());
    SMAIndicator rviSignal = new SMAIndicator(rvi, 4); // 4-period signal line

    // Entry rule: RVI crosses above signal line
    Rule entryRule = new CrossedUpIndicatorRule(rvi, rviSignal);

    // Exit rule: RVI crosses below signal line
    Rule exitRule = new CrossedDownIndicatorRule(rvi, rviSignal);

    return new BaseStrategy(
        String.format("%s (Period: %d)", getStrategyType().name(), params.getPeriod()),
        entryRule,
        exitRule,
        params.getPeriod());
  }

  @Override
  public RviParameters getDefaultParameters() {
    return RviParameters.newBuilder()
        .setPeriod(10)  // Standard RVI period
        .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.RVI;
  }
}
