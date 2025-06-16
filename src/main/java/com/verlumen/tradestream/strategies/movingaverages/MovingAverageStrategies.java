package com.verlumen.tradestream.strategies.movingaverages;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.strategies.StrategyFactory;

/**
 * Provides a centralized collection of all available moving average-based strategy factories. This
 * class is immutable and thread-safe.
 */
public final class MovingAverageStrategies {
  /** An immutable list of all moving average strategy factories. */
  public static final ImmutableList<StrategyFactory<?>> ALL_FACTORIES =
      ImmutableList.of();

  // Prevent instantiation
  private MovingAverageStrategies() {}
}
// Remove unused import if DoubleEmaCrossoverStrategyFactory was the only thing from its package,
// or if it's no longer needed. The linter/compiler will catch this if missed.
