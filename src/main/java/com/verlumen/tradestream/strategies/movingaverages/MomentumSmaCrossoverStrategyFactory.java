package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class MomentumSmaCrossoverStrategyFactory
    implements StrategyFactory<MomentumSmaCrossoverParameters> {
  @Inject
  MomentumSmaCrossoverStrategyFactory() {}

  @Override
  public Strategy createStrategy(BarSeries series, MomentumSmaCrossoverParameters params)
      throws InvalidProtocolBufferException {
    checkArgument(params.getMomentumPeriod() > 0, "Momentum period must be positive");
    checkArgument(params.getSmaPeriod() > 0, "SMA period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    MomentumIndicator momentumIndicator = new MomentumIndicator(closePrice, params.getMomentumPeriod());
    SMAIndicator smaIndicator = new SMAIndicator(momentumIndicator, params.getSmaPeriod());

    Rule entryRule = new CrossedUpIndicatorRule(momentumIndicator, smaIndicator);
    Rule exitRule = new CrossedDownIndicatorRule(momentumIndicator, smaIndicator);
     return createStrategy(
        entryRule,
        exitRule,
        params.getSmaPeriod()
    );
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.MOMENTUM_SMA_CROSSOVER;
  }
}
