package com.verlumen.tradestream.strategies.cmfzeroline;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.CmfZeroLineParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.ChaikinMoneyFlowIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class CmfZeroLineStrategyFactory implements StrategyFactory<CmfZeroLineParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, CmfZeroLineParameters params) {
    checkArgument(params.getPeriod() > 0, "Period must be positive");

    ChaikinMoneyFlowIndicator cmf = new ChaikinMoneyFlowIndicator(series, params.getPeriod());

    // Entry rule: CMF crosses above zero
    Rule entryRule = new CrossedUpIndicatorRule(cmf, series.numOf(0));

    // Exit rule: CMF crosses below zero
    Rule exitRule = new CrossedDownIndicatorRule(cmf, series.numOf(0));

    return new BaseStrategy(
        String.format("%s (Period: %d)", StrategyType.CMF_ZERO_LINE.name(), params.getPeriod()),
        entryRule,
        exitRule,
        params.getPeriod());
  }

  @Override
  public CmfZeroLineParameters getDefaultParameters() {
    return CmfZeroLineParameters.newBuilder()
        .setPeriod(20) // Standard CMF period
        .build();
  }
}
