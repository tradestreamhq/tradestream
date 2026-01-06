package com.verlumen.tradestream.strategies.momentumpinball;

import com.verlumen.tradestream.strategies.MomentumPinballParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.ta4j.MomentumIndicator;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

/**
 * Factory for creating Momentum Pinball strategies.
 *
 * <p>This strategy combines short term and long term momentum indicators. It enters when long
 * momentum is positive and short momentum crosses above zero, and exits when long momentum is
 * negative and short momentum crosses below zero.
 */
public class MomentumPinballStrategyFactory implements StrategyFactory<MomentumPinballParameters> {

  private final MomentumPinballParamConfig paramConfig;

  public MomentumPinballStrategyFactory() {
    this.paramConfig = new MomentumPinballParamConfig();
  }

  @Override
  public MomentumPinballParameters getDefaultParameters() {
    return MomentumPinballParameters.newBuilder().setShortPeriod(10).setLongPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, MomentumPinballParameters parameters) {
    int shortPeriod = parameters.getShortPeriod();
    int longPeriod = parameters.getLongPeriod();
    return createStrategy(series, shortPeriod, longPeriod);
  }

  private Strategy createStrategy(BarSeries barSeries, int shortPeriod, int longPeriod) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(barSeries);

    // Create momentum indicators
    MomentumIndicator shortMomentum = new MomentumIndicator(closePrice, shortPeriod);
    MomentumIndicator longMomentum = new MomentumIndicator(closePrice, longPeriod);

    // Entry rule: Long momentum is positive AND short momentum crosses above zero
    var entryRule =
        new OverIndicatorRule(longMomentum, barSeries.numOf(0))
            .and(new CrossedUpIndicatorRule(shortMomentum, 0));

    // Exit rule: Long momentum is negative AND short momentum crosses below zero
    var exitRule =
        new UnderIndicatorRule(longMomentum, barSeries.numOf(0))
            .and(new CrossedDownIndicatorRule(shortMomentum, 0));

    return new org.ta4j.core.BaseStrategy(entryRule, exitRule);
  }
}
