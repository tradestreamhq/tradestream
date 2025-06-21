package com.verlumen.tradestream.strategies.macdcrossover;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.MacdCrossoverParameters;
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

public final class MacdCrossoverStrategyFactory
    implements StrategyFactory<MacdCrossoverParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, MacdCrossoverParameters params) {
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

    // Entry rule: MACD crosses above Signal Line
    Rule entryRule = new CrossedUpIndicatorRule(macdIndicator, signalIndicator);

    // Exit rule: MACD crosses below Signal Line
    Rule exitRule = new CrossedDownIndicatorRule(macdIndicator, signalIndicator);

    return new BaseStrategy(
        String.format(
            "%s (%d, %d, %d)",
            getStrategyType().name(),
            params.getShortEmaPeriod(),
            params.getLongEmaPeriod(),
            params.getSignalPeriod()),
        entryRule,
        exitRule,
        params.getLongEmaPeriod());
  }

  @Override
  public MacdCrossoverParameters getDefaultParameters() {
    return MacdCrossoverParameters.newBuilder()
        .setShortEmaPeriod(12)
        .setLongEmaPeriod(26)
        .setSignalPeriod(9)
        .build();
  }
}
