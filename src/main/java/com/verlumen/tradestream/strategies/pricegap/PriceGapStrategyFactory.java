package com.verlumen.tradestream.strategies.pricegap;

import com.verlumen.tradestream.strategies.PriceGapParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class PriceGapStrategyFactory implements StrategyFactory<PriceGapParameters> {

  @Override
  public PriceGapParameters getDefaultParameters() {
    return PriceGapParameters.newBuilder().setPeriod(10).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, PriceGapParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator ema = new EMAIndicator(closePrice, parameters.getPeriod());

    // Entry rule: Price crosses above EMA (bullish signal)
    var entryRule = new CrossedUpIndicatorRule(closePrice, ema);

    // Exit rule: Price crosses below EMA (bearish signal)
    var exitRule = new CrossedDownIndicatorRule(closePrice, ema);

    return new org.ta4j.core.BaseStrategy(
        "Price Gap Strategy", entryRule, exitRule, parameters.getPeriod());
  }
}
