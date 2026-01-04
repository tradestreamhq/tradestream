package com.verlumen.tradestream.strategies.configurable;

import java.util.Map;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Indicator;
import org.ta4j.core.Rule;
import org.ta4j.core.num.Num;

/** Functional interface for creating Ta4j rules from configuration. */
@FunctionalInterface
public interface RuleFactory {
  /**
   * Creates a rule with the given indicators and parameters.
   *
   * @param barSeries The bar series context
   * @param indicators Map of indicator ID to indicator instance
   * @param params The resolved parameters for this rule
   * @return The created rule
   */
  Rule create(BarSeries barSeries, Map<String, Indicator<Num>> indicators, ResolvedParams params);
}
