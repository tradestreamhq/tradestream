package com.verlumen.tradestream.strategies;

import com.google.protobuf.Any;
import java.io.Serializable;
import static com.google.common.base.Preconditions.checkNotNull;

/**
 * Immutable record of a strategy's parameters and performance score.
 */
record StrategyRecord(StrategyType strategyType, Any parameters, double score)
    implements Serializable {
  static StrategyRecord create(StrategyType strategyType, Any parameters) {
      new StrategyRecord(strategyType, parameters, Double.NEGATIVE_INFINITY);    
  }

  StrategyRecord {
    checkNotNull(strategyType, "Strategy strategyType cannot be null");
  }
}
