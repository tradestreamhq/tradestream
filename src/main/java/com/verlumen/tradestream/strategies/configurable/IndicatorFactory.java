package com.verlumen.tradestream.strategies.configurable;

import org.ta4j.core.BarSeries;
import org.ta4j.core.Indicator;
import org.ta4j.core.num.Num;

/** Functional interface for creating Ta4j indicators from configuration. */
@FunctionalInterface
public interface IndicatorFactory {
  /**
   * Creates an indicator with the given input and parameters.
   *
   * @param barSeries The bar series context
   * @param input The input indicator (usually close price or another indicator)
   * @param params The resolved parameters for this indicator
   * @return The created indicator
   */
  Indicator<Num> create(BarSeries barSeries, Indicator<Num> input, ResolvedParams params);
}
