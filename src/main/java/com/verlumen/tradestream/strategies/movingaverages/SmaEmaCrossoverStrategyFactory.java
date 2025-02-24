package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

final class SmaEmaCrossoverStrategyFactory implements StrategyFactory<SmaEmaCrossoverParameters> {
  static SmaEmaCrossoverStrategyFactory create() {
    return new SmaEmaCrossoverStrategyFactory();
  }

  @Override
  public Strategy createStrategy(BarSeries series, SmaEmaCrossoverParameters params)
      throws InvalidProtocolBufferException {
    checkArgument(params.getSmaPeriod() > 0, "SMA period must be positive");
    checkArgument(params.getEmaPeriod() > 0, "EMA period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    SMAIndicator smaIndicator = new SMAIndicator(closePrice, params.getSmaPeriod());
    EMAIndicator emaIndicator = new EMAIndicator(closePrice, params.getEmaPeriod());

    Rule entryRule = new CrossedUpIndicatorRule(smaIndicator, emaIndicator);
    Rule exitRule = new CrossedDownIndicatorRule(smaIndicator, emaIndicator);
    String strategyName = String.format(
      "%s (SMA-%d EMA-%d)", getStrategyType().name(), params.getSmaPeriod(), params.getEmaPeriod());
    return new BaseStrategy(
        strategyName,
        entryRule,
        exitRule,
        params.getEmaPeriod()
      );
  }

  @Override
  public SmaEmaCrossoverParameters getDefaultParameters() {
      return SmaEmaCrossoverParameters.newBuilder()
          .setSmaPeriod(20) // Default SMA period, typically used as a short-term trend
          .setEmaPeriod(50) // Default EMA period, commonly used for medium-term trend
          .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.SMA_EMA_CROSSOVER;
  }

  private SmaEmaCrossoverStrategyFactory() {}
}
