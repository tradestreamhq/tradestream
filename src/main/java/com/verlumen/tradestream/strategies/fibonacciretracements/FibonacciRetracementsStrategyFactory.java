package com.verlumen.tradestream.strategies.fibonacciretracements;

import com.verlumen.tradestream.strategies.FibonacciRetracementsParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class FibonacciRetracementsStrategyFactory
    implements StrategyFactory<FibonacciRetracementsParameters> {

  @Override
  public FibonacciRetracementsParameters getDefaultParameters() {
    return FibonacciRetracementsParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, FibonacciRetracementsParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator ema = new EMAIndicator(closePrice, parameters.getPeriod());

    // Entry rule: Price crosses above EMA (bullish signal)
    var entryRule = new CrossedUpIndicatorRule(closePrice, ema);

    // Exit rule: Price crosses below EMA (bearish signal)
    var exitRule = new CrossedDownIndicatorRule(closePrice, ema);

    return new org.ta4j.core.BaseStrategy(
        "Fibonacci Retracements Strategy", entryRule, exitRule, parameters.getPeriod());
  }
}
