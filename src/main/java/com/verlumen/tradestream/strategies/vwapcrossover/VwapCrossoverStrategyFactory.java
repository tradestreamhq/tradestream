package com.verlumen.tradestream.strategies.vwapcrossover;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.VwapCrossoverParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.volume.VWAPIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.volume.VWAPIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class VwapCrossoverStrategyFactory implements StrategyFactory<VwapCrossoverParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, VwapCrossoverParameters params) {
    checkArgument(params.getVwapPeriod() > 0, "VWAP period must be positive");
    checkArgument(params.getMovingAveragePeriod() > 0, "Moving average period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    VWAPIndicator vwap = new VWAPIndicator(series, params.getVwapPeriod());
    SMAIndicator movingAverage = new SMAIndicator(closePrice, params.getMovingAveragePeriod());

    // Entry rule: Price crosses above VWAP
    Rule entryRule = new CrossedUpIndicatorRule(closePrice, vwap);

    // Exit rule: Price crosses below VWAP
    Rule exitRule = new CrossedDownIndicatorRule(closePrice, vwap);

    return new BaseStrategy(
        String.format("%s (VWAP: %d, MA: %d)",
            StrategyType.VWAP_CROSSOVER.name(),
            params.getVwapPeriod(),
            params.getMovingAveragePeriod()),
        entryRule,
        exitRule,
        Math.max(params.getVwapPeriod(), params.getMovingAveragePeriod()));
  }

  @Override
  public VwapCrossoverParameters getDefaultParameters() {
    return VwapCrossoverParameters.newBuilder()
        .setVwapPeriod(20)           // Standard VWAP period
        .setMovingAveragePeriod(20)  // Standard moving average period
        .build();
  }
}
