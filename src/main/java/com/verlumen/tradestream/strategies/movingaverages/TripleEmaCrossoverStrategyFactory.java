package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

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

public class TripleEmaCrossoverStrategyFactory
    implements StrategyFactory<TripleEmaCrossoverParameters> {
  static TripleEmaCrossoverStrategyFactory create() {
    return new TripleEmaCrossoverStrategyFactory();
  }

  @Override
  public Strategy createStrategy(BarSeries series, TripleEmaCrossoverParameters params) {
    checkArgument(params.getShortEmaPeriod() > 0, "Short EMA period must be positive");
    checkArgument(params.getMediumEmaPeriod() > 0, "Medium EMA period must be positive");
    checkArgument(params.getLongEmaPeriod() > 0, "Long EMA period must be positive");
    checkArgument(
        params.getMediumEmaPeriod() > params.getShortEmaPeriod(),
        "Medium EMA period must be greater than the short EMA period");
    checkArgument(
        params.getLongEmaPeriod() > params.getMediumEmaPeriod(),
        "Long EMA period must be greater than the medium EMA period");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEma = new EMAIndicator(closePrice, params.getShortEmaPeriod());
    EMAIndicator mediumEma = new EMAIndicator(closePrice, params.getMediumEmaPeriod());
    EMAIndicator longEma = new EMAIndicator(closePrice, params.getLongEmaPeriod());

    Rule entryRule =
        new CrossedUpIndicatorRule(shortEma, mediumEma)
            .or(new CrossedUpIndicatorRule(mediumEma, longEma));

    Rule exitRule =
        new CrossedDownIndicatorRule(shortEma, mediumEma)
            .or(new CrossedDownIndicatorRule(mediumEma, longEma));

    return new BaseStrategy(
        String.format(
            "%s (%d, %d, %d)",
            getStrategyType().name(),
            params.getShortEmaPeriod(),
            params.getMediumEmaPeriod(),
            params.getLongEmaPeriod()),
        entryRule,
        exitRule,
        params.getLongEmaPeriod());
  }

  @Override
  public TripleEmaCrossoverParameters getDefaultParameters() {
      return TripleEmaCrossoverParameters.newBuilder()
          .setShortEmaPeriod(10)   // Default short EMA period for quick responsiveness
          .setMediumEmaPeriod(20)  // Default medium EMA period for smoother trends
          .setLongEmaPeriod(50)    // Default long EMA period for overall trend
          .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.TRIPLE_EMA_CROSSOVER;
  }

  private TripleEmaCrossoverStrategyFactory() {}
}
