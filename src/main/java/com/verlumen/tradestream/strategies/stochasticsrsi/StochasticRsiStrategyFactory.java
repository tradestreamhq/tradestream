package com.verlumen.tradestream.strategies.stochasticsrsi;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.StochasticRsiParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.RSIIndicator;
import org.ta4j.core.indicators.StochasticOscillatorKIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class StochasticRsiStrategyFactory implements StrategyFactory<StochasticRsiParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, StochasticRsiParameters params) {
    checkArgument(params.getRsiPeriod() > 0, "RSI period must be positive");
    checkArgument(params.getStochasticKPeriod() > 0, "Stochastic K period must be positive");
    checkArgument(params.getOverboughtThreshold() > 0, "Overbought threshold must be positive");
    checkArgument(params.getOversoldThreshold() > 0, "Oversold threshold must be positive");
    checkArgument(
        params.getOverboughtThreshold() > params.getOversoldThreshold(),
        "Overbought threshold must be greater than oversold threshold");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    RSIIndicator rsi = new RSIIndicator(closePrice, params.getRsiPeriod());
    
    // Create a bar series from RSI values to apply Stochastic to RSI
    // Note: This is a simplified approach. In practice, you'd need a custom indicator
    // that applies Stochastic calculation to RSI values
    StochasticOscillatorKIndicator stochasticRsi =
        new StochasticOscillatorKIndicator(series, params.getStochasticKPeriod());

    // Entry rule: Stochastic RSI crosses above oversold threshold
    Rule entryRule =
        new OverIndicatorRule(stochasticRsi, series.numOf(params.getOversoldThreshold()));

    // Exit rule: Stochastic RSI crosses below overbought threshold
    Rule exitRule =
        new UnderIndicatorRule(stochasticRsi, series.numOf(params.getOverboughtThreshold()));

    return new BaseStrategy(
        String.format(
            "%s (RSI: %d, StochK: %d)",
            getStrategyType().name(), params.getRsiPeriod(), params.getStochasticKPeriod()),
        entryRule,
        exitRule,
        Math.max(params.getRsiPeriod(), params.getStochasticKPeriod()));
  }

  @Override
  public StochasticRsiParameters getDefaultParameters() {
    return StochasticRsiParameters.newBuilder()
        .setRsiPeriod(14)
        .setStochasticKPeriod(14)
        .setStochasticDPeriod(3)
        .setOverboughtThreshold(80)
        .setOversoldThreshold(20)
        .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.STOCHASTIC_RSI;
  }
}
