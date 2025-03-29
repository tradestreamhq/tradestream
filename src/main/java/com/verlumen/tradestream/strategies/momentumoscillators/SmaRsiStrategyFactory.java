package com.verlumen.tradestream.strategies.momentumoscillators;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.RSIIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

final class SmaRsiStrategyFactory implements StrategyFactory<SmaRsiParameters> {
  static SmaRsiStrategyFactory create() {
    return new SmaRsiStrategyFactory();
  }

  @Override
  public Strategy createStrategy(BarSeries series, SmaRsiParameters params) {
    checkArgument(params.getMovingAveragePeriod() > 0, "Moving average period must be positive");
    checkArgument(params.getRsiPeriod() > 0, "RSI period must be positive");
    checkArgument(params.getOverboughtThreshold() > 0, "Overbought threshold must be positive");
    checkArgument(params.getOversoldThreshold() > 0, "Oversold threshold must be positive");
    checkArgument(
        params.getOverboughtThreshold() > params.getOversoldThreshold(),
        "Overbought threshold must be greater than the oversold threshold");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    RSIIndicator rsiIndicator = new RSIIndicator(closePrice, params.getRsiPeriod());
    SMAIndicator smaIndicator = new SMAIndicator(rsiIndicator, params.getMovingAveragePeriod());

    Rule entryRule =
        new UnderIndicatorRule(rsiIndicator, params.getOversoldThreshold())
            .and(new UnderIndicatorRule(smaIndicator, params.getOversoldThreshold()));

    Rule exitRule =
        new OverIndicatorRule(rsiIndicator, params.getOverboughtThreshold())
            .and(new OverIndicatorRule(smaIndicator, params.getOverboughtThreshold()));

    String strategyName =
        String.format(
            "%s (RSI-%d SMA-%d)",
            getStrategyType().name(),
            params.getRsiPeriod(),
            params.getMovingAveragePeriod());
    return new BaseStrategy(strategyName, entryRule, exitRule, params.getRsiPeriod());
  }

  @Override
  public SmaRsiParameters getDefaultParameters() {
      return SmaRsiParameters.newBuilder()
          .setMovingAveragePeriod(14)      // Typical moving average period for smoothing RSI
          .setRsiPeriod(14)                // Common RSI calculation period
          .setOverboughtThreshold(70)      // Overbought threshold, often set at 70
          .setOversoldThreshold(30)        // Oversold threshold, often set at 30
          .build();
  }

  private SmaRsiStrategyFactory() {}

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.SMA_RSI;
  }
}
