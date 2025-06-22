package com.verlumen.tradestream.strategies.volumeweightedmacd;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.VolumeWeightedMacdParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

/**
 * Factory for creating Volume Weighted MACD strategies.
 *
 * <p>This strategy combines volume into MACD calculations by using volume-weighted EMAs to create a
 * more volume-sensitive MACD indicator. The MACD line is calculated as the difference between short
 * and long EMAs, and the signal line is an EMA of the MACD line.
 */
public class VolumeWeightedMacdStrategyFactory
    implements StrategyFactory<VolumeWeightedMacdParameters> {

  public StrategyType getStrategyType() {
    return StrategyType.VOLUME_WEIGHTED_MACD;
  }

  @Override
  public VolumeWeightedMacdParameters getDefaultParameters() {
    return VolumeWeightedMacdParameters.newBuilder()
        .setShortPeriod(12)
        .setLongPeriod(26)
        .setSignalPeriod(9)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, VolumeWeightedMacdParameters parameters) {
    int shortPeriod = parameters.getShortPeriod();
    int longPeriod = parameters.getLongPeriod();
    int signalPeriod = parameters.getSignalPeriod();
    return createStrategy(series, shortPeriod, longPeriod, signalPeriod);
  }

  public Strategy createStrategy(
      BarSeries barSeries, int shortPeriod, int longPeriod, int signalPeriod) {
    // Create volume-weighted EMAs
    var closePrice = new ClosePriceIndicator(barSeries);
    var shortEma = new EMAIndicator(closePrice, shortPeriod);
    var longEma = new EMAIndicator(closePrice, longPeriod);

    // Create MACD line (difference between short and long EMAs)
    var macdLine = new VolumeWeightedMacdLineIndicator(shortEma, longEma);

    // Create signal line (EMA of MACD line)
    var signalLine = new EMAIndicator(macdLine, signalPeriod);

    // Entry rule: MACD line crosses above signal line
    var entryRule = new CrossedUpIndicatorRule(macdLine, signalLine);

    // Exit rule: MACD line crosses below signal line
    var exitRule = new CrossedDownIndicatorRule(macdLine, signalLine);

    return new org.ta4j.core.BaseStrategy(entryRule, exitRule);
  }

  public Strategy createStrategy(BarSeries barSeries) {
    return createStrategy(barSeries, 12, 26, 9);
  }
}
