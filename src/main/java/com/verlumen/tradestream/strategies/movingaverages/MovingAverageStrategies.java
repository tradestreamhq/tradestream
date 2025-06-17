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
      ImmutableList.of(
          MomentumSmaCrossoverStrategyFactory.create(),
<<<<<<< tradestreamhq-patch-12
          SmaEmaCrossoverStrategyFactory.create());
=======
          TripleEmaCrossoverStrategyFactory.create());
>>>>>>> develop

  // Prevent instantiation
  private MovingAverageStrategies() {}
}
