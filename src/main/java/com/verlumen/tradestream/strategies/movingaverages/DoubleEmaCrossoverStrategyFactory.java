package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public class DoubleEmaCrossoverStrategyFactory implements StrategyFactory<DoubleEmaCrossoverParameters> {
  @Inject
  DoubleEmaCrossoverStrategyFactory() {}

  @Override
  public Strategy createStrategy(BarSeries series, DoubleEmaCrossoverParameters params)
      throws InvalidProtocolBufferException {
    checkArgument(params.getShortEmaPeriod() > 0, "Short EMA period must be positive");
    checkArgument(params.getLongEmaPeriod() > 0, "Long EMA period must be positive");
    checkArgument(params.getLongEmaPeriod() > params.getShortEmaPeriod(),
        "Long EMA period must be greater than short EMA period");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEma = new EMAIndicator(closePrice, params.getShortEmaPeriod());
    EMAIndicator longEma = new EMAIndicator(closePrice, params.getLongEmaPeriod());

    // Entry rule: Short EMA crosses above Long EMA AND Short EMA > Long EMA
    CrossedUpIndicatorRule crossedUpRule = new CrossedUpIndicatorRule(shortEma, longEma);
    OverIndicatorRule overRule = new OverIndicatorRule(shortEma, longEma);
    
    // Exit rule: Short EMA crosses below Long EMA AND Short EMA < Long EMA  
    CrossedDownIndicatorRule crossedDownRule = new CrossedDownIndicatorRule(shortEma, longEma);
    UnderIndicatorRule underRule = new UnderIndicatorRule(shortEma, longEma);

    return createStrategy(
        crossedUpRule.and(overRule),
        crossedDownRule.and(underRule),
        params.getLongEmaPeriod()
    );
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.DOUBLE_EMA_CROSSOVER;
  }
}
