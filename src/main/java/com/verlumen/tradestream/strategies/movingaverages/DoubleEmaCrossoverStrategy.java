package com.verlumen.tradestream.strategies.movingaverages;

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

public class DoubleEmaCrossoverStrategy implements StrategyFactory<DoubleEmaCrossoverParameters> {

  @Override
  public Strategy createStrategy(DoubleEmaCrossoverParameters params)
      throws InvalidProtocolBufferException {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(null);
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

  public static class Factory implements StrategyFactory<DoubleEmaCrossoverParameters>{
    @Override
    public Strategy createStrategy(DoubleEmaCrossoverParameters parameters) throws InvalidProtocolBufferException {
        return new DoubleEmaCrossoverStrategy().createStrategy(parameters);
    }

    @Override
    public StrategyType getStrategyType() {
        return StrategyType.DOUBLE_EMA_CROSSOVER;
    }
  }
}
