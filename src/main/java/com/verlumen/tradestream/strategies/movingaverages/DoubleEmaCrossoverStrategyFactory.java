package com.verlumen.tradestream.strategies.movingaverages;

import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class DoubleEmaCrossoverStrategyFactory implements StrategyFactory<DoubleEmaCrossoverParameters> {
  @Inject
  DoubleEmaCrossoverStrategyFactory() {}

  @Override
  public Strategy createStrategy(BarSeries series, DoubleEmaCrossoverParameters params)
      throws InvalidProtocolBufferException {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEma = new EMAIndicator(closePrice, params.getShortEmaPeriod());
    EMAIndicator longEma = new EMAIndicator(closePrice, params.getLongEmaPeriod());

    return new BaseStrategy(
        "Double EMA Crossover",
        new CrossedUpIndicatorRule(shortEma, longEma),
        new CrossedDownIndicatorRule(shortEma, longEma));
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.DOUBLE_EMA_CROSSOVER;
  }
}
