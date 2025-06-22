package com.verlumen.tradestream.strategies.awesomeoscillator;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.AwesomeOscillatorParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.AwesomeOscillatorIndicator;
import org.ta4j.core.indicators.helpers.MedianPriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class AwesomeOscillatorStrategyFactory
    implements StrategyFactory<AwesomeOscillatorParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, AwesomeOscillatorParameters params) {
    checkArgument(params.getShortPeriod() > 0, "Short period must be positive");
    checkArgument(params.getLongPeriod() > 0, "Long period must be positive");
    checkArgument(
        params.getLongPeriod() > params.getShortPeriod(),
        "Long period must be greater than short period");

    // Create MedianPriceIndicator first, then use it for AwesomeOscillatorIndicator
    MedianPriceIndicator medianPrice = new MedianPriceIndicator(series);
    AwesomeOscillatorIndicator ao =
        new AwesomeOscillatorIndicator(
            medianPrice, params.getShortPeriod(), params.getLongPeriod());

    // Entry rule: AO crosses above zero
    Rule entryRule = new CrossedUpIndicatorRule(ao, series.numOf(0));

    // Exit rule: AO crosses below zero
    Rule exitRule = new CrossedDownIndicatorRule(ao, series.numOf(0));

    return new BaseStrategy(
        String.format(
            "%s (Short: %d, Long: %d)",
            StrategyType.AWESOME_OSCILLATOR.name(),
            params.getShortPeriod(),
            params.getLongPeriod()),
        entryRule,
        exitRule,
        params.getLongPeriod());
  }

  @Override
  public AwesomeOscillatorParameters getDefaultParameters() {
    return AwesomeOscillatorParameters.newBuilder()
        .setShortPeriod(5) // Standard AO short period
        .setLongPeriod(34) // Standard AO long period
        .build();
  }
}
