package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.strategies.momentumoscillators.MomentumOscillatorStrategies;
import com.verlumen.tradestream.strategies.movingaverages.MovingAverageStrategies;

/**
 * Provides a centralized collection of all available strategy factories across all categories. This
 * class aggregates factories from child packages (moving averages, momentumoscillators, etc.) and
 * is immutable and thread-safe.
 */
final class StrategyFactories {
  /** An immutable list of all strategy factories across all categories. */
  static final ImmutableList<StrategyFactory<?>> ALL_FACTORIES =
      ImmutableList.<StrategyFactory<?>>builder()
          .addAll(MovingAverageStrategies.ALL_FACTORIES)
          .addAll(MomentumOscillatorStrategies.ALL_FACTORIES)
          .build();

  // Prevent instantiation
  private StrategyFactories() {}
}
