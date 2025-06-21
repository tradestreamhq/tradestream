package com.verlumen.tradestream.strategies.chaikinoscillator;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.ChaikinOscillatorParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.ChaikinOscillatorIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class ChaikinOscillatorStrategyFactory
    implements StrategyFactory<ChaikinOscillatorParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, ChaikinOscillatorParameters params) {
    checkArgument(params.getFastPeriod() > 0, "Fast period must be positive");
    checkArgument(params.getSlowPeriod() > 0, "Slow period must be positive");
    checkArgument(
        params.getSlowPeriod() > params.getFastPeriod(),
        "Slow period must be greater than fast period");

    ChaikinOscillatorIndicator chaikin =
        new ChaikinOscillatorIndicator(series, params.getFastPeriod(), params.getSlowPeriod());

    // Entry rule: Chaikin Oscillator crosses above zero
    Rule entryRule = new CrossedUpIndicatorRule(chaikin, series.numOf(0));

    // Exit rule: Chaikin Oscillator crosses below zero
    Rule exitRule = new CrossedDownIndicatorRule(chaikin, series.numOf(0));

    return new BaseStrategy(
        String.format(
            "%s (Fast: %d, Slow: %d)",
            StrategyType.CHAIKIN_OSCILLATOR.name(),
            params.getFastPeriod(),
            params.getSlowPeriod()),
        entryRule,
        exitRule,
        params.getSlowPeriod());
  }

  @Override
  public ChaikinOscillatorParameters getDefaultParameters() {
    return ChaikinOscillatorParameters.newBuilder()
        .setFastPeriod(3) // Standard Chaikin fast period
        .setSlowPeriod(10) // Standard Chaikin slow period
        .build();
  }
}
