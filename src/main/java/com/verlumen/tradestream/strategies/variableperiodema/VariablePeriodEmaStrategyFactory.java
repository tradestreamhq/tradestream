package com.verlumen.tradestream.strategies.variableperiodema;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.VariablePeriodEmaParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class VariablePeriodEmaStrategyFactory
    implements StrategyFactory<VariablePeriodEmaParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, VariablePeriodEmaParameters params)
      throws InvalidProtocolBufferException {
    checkArgument(params.getMinPeriod() > 0, "Min period must be positive");
    checkArgument(params.getMaxPeriod() > 0, "Max period must be positive");
    checkArgument(
        params.getMaxPeriod() > params.getMinPeriod(),
        "Max period must be greater than min period");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    // Use average of min and max periods for the EMA
    int emaPeriod = (params.getMinPeriod() + params.getMaxPeriod()) / 2;
    EMAIndicator ema = new EMAIndicator(closePrice, emaPeriod);

    // Entry rule: Price crosses above EMA
    Rule entryRule = new CrossedUpIndicatorRule(closePrice, ema);

    // Exit rule: Price crosses below EMA
    Rule exitRule = new CrossedDownIndicatorRule(closePrice, ema);

    return new BaseStrategy(
        String.format(
            "%s (%d-%d, avg=%d)",
            "VARIABLE_PERIOD_EMA", params.getMinPeriod(), params.getMaxPeriod(), emaPeriod),
        entryRule,
        exitRule,
        emaPeriod);
  }

  @Override
  public VariablePeriodEmaParameters getDefaultParameters() {
    return VariablePeriodEmaParameters.newBuilder().setMinPeriod(10).setMaxPeriod(30).build();
  }
}
