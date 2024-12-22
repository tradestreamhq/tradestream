package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.TripleEmaCrossoverParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OrRule;

public class TripleEmaCrossoverStrategyFactory
    implements StrategyFactory<TripleEmaCrossoverParameters> {
  @Inject
  TripleEmaCrossoverStrategyFactory() {}

  @Override
  public Strategy createStrategy(BarSeries series, TripleEmaCrossoverParameters params)
      throws InvalidProtocolBufferException {
      checkArgument(params.getShortEmaPeriod() > 0, "Short EMA period must be positive");
      checkArgument(params.getMediumEmaPeriod() > 0, "Medium EMA period must be positive");
      checkArgument(params.getLongEmaPeriod() > 0, "Long EMA period must be positive");
       checkArgument(params.getMediumEmaPeriod() > params.getShortEmaPeriod(),
          "Medium EMA period must be greater than the short EMA period");
     checkArgument(params.getLongEmaPeriod() > params.getMediumEmaPeriod(),
          "Long EMA period must be greater than the medium EMA period");
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEma = new EMAIndicator(closePrice, params.getShortEmaPeriod());
    EMAIndicator mediumEma = new EMAIndicator(closePrice, params.getMediumEmaPeriod());
    EMAIndicator longEma = new EMAIndicator(closePrice, params.getLongEmaPeriod());

    return new BaseStrategy(
        String.format("%s (%d, %d, %d)",
            getStrategyType().name(),
            params.getShortEmaPeriod(),
            params.getMediumEmaPeriod(),
            params.getLongEmaPeriod()),
        new OrRule(
            new CrossedUpIndicatorRule(shortEma, mediumEma),
            new CrossedUpIndicatorRule(mediumEma, longEma)),
        new OrRule(
            new CrossedDownIndicatorRule(shortEma, mediumEma),
            new CrossedDownIndicatorRule(mediumEma, longEma)),
        params.getLongEmaPeriod()
    );
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.TRIPLE_EMA_CROSSOVER;
  }
}
