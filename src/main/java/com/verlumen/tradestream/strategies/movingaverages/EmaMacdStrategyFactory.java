package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.EmaMacdParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.MACDIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

final class EmaMacdStrategyFactory implements StrategyFactory<EmaMacdParameters> {
  static EmaMacdStrategyFactory create() {
    return new EmaMacdStrategyFactory();
  }

  private EmaMacdStrategyFactory() {}

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.EMA_MACD;
  }

  @Override
  public Strategy createStrategy(BarSeries series, EmaMacdParameters params)
      throws InvalidProtocolBufferException {
    checkArgument(params.getShortEmaPeriod() > 0, "Short EMA period must be positive");
    checkArgument(params.getLongEmaPeriod() > 0, "Long EMA period must be positive");
    checkArgument(params.getSignalPeriod() > 0, "Signal period must be positive");
    checkArgument(
        params.getLongEmaPeriod() > params.getShortEmaPeriod(),
        "Long EMA period must be greater than short EMA period");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    MACDIndicator macdIndicator =
        new MACDIndicator(closePrice, params.getShortEmaPeriod(), params.getLongEmaPeriod());
    EMAIndicator signalIndicator = new EMAIndicator(macdIndicator, params.getSignalPeriod());

    // Entry rule
    Rule entryRule = new CrossedUpIndicatorRule(macdIndicator, signalIndicator);

    // Exit rule - MACD crosses below Signal
    Rule exitRule = new CrossedDownIndicatorRule(macdIndicator, signalIndicator);

    String strategyName =
        String.format(
            "%s (Short EMA: %d, Long EMA: %d, Signal: %d)",
            getStrategyType().name(),
            params.getShortEmaPeriod(),
            params.getLongEmaPeriod(),
            params.getSignalPeriod());
    return new BaseStrategy(strategyName, entryRule, exitRule, params.getLongEmaPeriod());
  }

  @Override
  public EmaMacdParameters getDefaultParameters() {
    return EmaMacdParameters.newBuilder()
        .setShortEmaPeriod(12)
        .setLongEmaPeriod(26)
        .setSignalPeriod(9)
        .build();
  }
}
