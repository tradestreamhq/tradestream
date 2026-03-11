package com.verlumen.tradestream.strategies.gannswing;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.GannSwingParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.HighestValueIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.LowestValueIndicator;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class GannSwingStrategyFactory implements StrategyFactory<GannSwingParameters> {
  @Override
  public GannSwingParameters getDefaultParameters() {
    return GannSwingParameters.newBuilder().setGannPeriod(14).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, GannSwingParameters parameters) {
    checkArgument(parameters.getGannPeriod() > 0, "Gann period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);

    // Swing high: highest high over the Gann period
    HighPriceIndicator highPrice = new HighPriceIndicator(series);
    HighestValueIndicator swingHigh =
        new HighestValueIndicator(highPrice, parameters.getGannPeriod());

    // Swing low: lowest low over the Gann period
    LowPriceIndicator lowPrice = new LowPriceIndicator(series);
    LowestValueIndicator swingLow = new LowestValueIndicator(lowPrice, parameters.getGannPeriod());

    // Entry: price breaks above swing high (bullish breakout)
    Rule entryRule = new OverIndicatorRule(closePrice, swingHigh);

    // Exit: price breaks below swing low (bearish breakdown)
    Rule exitRule = new UnderIndicatorRule(closePrice, swingLow);

    return new BaseStrategy(
        String.format("%s (Period: %d)", "GANN_SWING", parameters.getGannPeriod()),
        entryRule,
        exitRule,
        parameters.getGannPeriod());
  }
}
