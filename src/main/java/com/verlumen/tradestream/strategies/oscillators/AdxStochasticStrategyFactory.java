package com.verlumen.tradestream.strategies.oscillators;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.AdxStochasticParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.adx.AdxIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.StochasticOscillatorKIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

final class AdxStochasticStrategyFactory
    implements StrategyFactory<AdxStochasticParameters> {
  static AdxStochasticStrategyFactory create() {
    return new AdxStochasticStrategyFactory();
  }

  @Override
  public Strategy createStrategy(BarSeries series, AdxStochasticParameters params) {
    checkArgument(params.getAdxPeriod() > 0, "ADX period must be positive");
    checkArgument(params.getStochasticKPeriod() > 0, "Stochastic K period must be positive");
    checkArgument(params.getOverboughtThreshold() > 0, "Overbought threshold must be positive");
    checkArgument(params.getOversoldThreshold() > 0, "Oversold threshold must be positive");
    checkArgument(
        params.getOverboughtThreshold() > params.getOversoldThreshold(),
        "Overbought threshold must be greater than oversold threshold");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    HighPriceIndicator highPrice = new HighPriceIndicator(series);
    LowPriceIndicator lowPrice = new LowPriceIndicator(series);
    AdxIndicator adxIndicator = new AdxIndicator(highPrice, lowPrice, closePrice, params.getAdxPeriod());
    StochasticOscillatorKIndicator stochasticK = new StochasticOscillatorKIndicator(series, params.getStochasticKPeriod());

    // Entry rule: ADX above a threshold (e.g., 20) indicating a strong trend
    // and Stochastic Oscillator K below oversold threshold
    Rule entryRule =
        new OverIndicatorRule(adxIndicator, series.numOf(20))
            .and(new UnderIndicatorRule(stochasticK, series.numOf(params.getOversoldThreshold())));

    // Exit rule: ADX below a threshold (e.g., 20) indicating a weak trend
    // and Stochastic Oscillator K above overbought threshold
    Rule exitRule =
        new UnderIndicatorRule(adxIndicator, series.numOf(20))
            .and(new OverIndicatorRule(stochasticK, series.numOf(params.getOverboughtThreshold())));

    return new BaseStrategy(
        String.format(
            "%s (ADX-%d, StochasticK-%d)",
            getStrategyType().name(),
            params.getAdxPeriod(),
            params.getStochasticKPeriod()),
        entryRule,
        exitRule,
        params.getAdxPeriod()); // Unstable period is ADX period
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.ADX_STOCHASTIC;
  }

  private AdxStochasticStrategyFactory() {}
}
