package com.verlumen.tradestream.strategies.stochasticema;

import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.StochasticEmaParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.StochasticOscillatorDIndicator;
import org.ta4j.core.indicators.StochasticOscillatorKIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

/**
 * Factory for creating Stochastic EMA strategies.
 *
 * <p>This strategy combines the Stochastic Oscillator with an Exponential Moving Average to
 * identify overbought/oversold conditions and trend direction.
 */
public class StochasticEmaStrategyFactory implements StrategyFactory<StochasticEmaParameters> {

  @Override
  public Strategy createStrategy(BarSeries barSeries, Any parameters) {
    try {
      StochasticEmaParameters params = parameters.unpack(StochasticEmaParameters.class);
      return createStrategy(barSeries, params);
    } catch (Exception e) {
      throw new IllegalArgumentException("Failed to unpack StochasticEmaParameters", e);
    }
  }

  public Strategy createStrategy(BarSeries barSeries, StochasticEmaParameters parameters) {
    // Create price indicator
    ClosePriceIndicator closePrice = new ClosePriceIndicator(barSeries);

    // Create Stochastic Oscillator K indicator
    StochasticOscillatorKIndicator stochasticK =
        new StochasticOscillatorKIndicator(barSeries, parameters.getStochasticKPeriod());

    // Create Stochastic Oscillator D indicator (uses only the K indicator)
    StochasticOscillatorDIndicator stochasticD = new StochasticOscillatorDIndicator(stochasticK);

    // Create EMA of Stochastic K
    EMAIndicator emaStochastic = new EMAIndicator(stochasticK, parameters.getEmaPeriod());

    // Entry rule: Stochastic K crosses above its EMA AND Stochastic K is below oversold threshold
    Rule entryRule =
        new CrossedUpIndicatorRule(stochasticK, emaStochastic)
            .and(new UnderIndicatorRule(stochasticK, parameters.getOversoldThreshold()));

    // Exit rule: Stochastic K crosses below its EMA OR Stochastic K is above overbought threshold
    Rule exitRule =
        new CrossedDownIndicatorRule(stochasticK, emaStochastic)
            .or(new OverIndicatorRule(stochasticK, parameters.getOverboughtThreshold()));

    return new BaseStrategy("STOCHASTIC_EMA", entryRule, exitRule);
  }

  @Override
  public StochasticEmaParameters getDefaultParameters() {
    return StochasticEmaParameters.newBuilder()
        .setEmaPeriod(14)
        .setStochasticKPeriod(14)
        .setStochasticDPeriod(3)
        .setOverboughtThreshold(80)
        .setOversoldThreshold(20)
        .build();
  }
}
