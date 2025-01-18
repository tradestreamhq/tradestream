package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

public interface StrategyManager {
  /**
   * Creates a Ta4j Strategy object from the provided parameters.
   *
   * @param strategyType The type of strategy to create
   * @param barSeries The bar series to associate with the created strategy
   * @return The created Strategy object
   * @throws InvalidProtocolBufferException If there is an error unpacking the parameters
   */
  default Strategy createStrategy(StrategyType strategyType, BarSeries barSeries)
      throws InvalidProtocolBufferException {
    Any parameters = getStrategyFactory(strategyType).getDefaultParameters();
    return createStrategy(strategyType, barSeries, parameters);
  }

  /**
   * Creates a Ta4j Strategy object from the provided parameters.
   *
   * @param strategyType The type of strategy to create
   * @param barSeries The bar series to associate with the created strategy
   * @param strategyParameters The parameters for configuring the strategy 
   * @return The created Strategy object
   * @throws InvalidProtocolBufferException If there is an error unpacking the parameters
   */
  default Strategy createStrategy(StrategyType strategyType, BarSeries barSeries, Any parameters)
      throws InvalidProtocolBufferException {
    StrategyFactory<?> factory = factoryMap.get(strategyType);
    if (factory == null) {
      throw new IllegalArgumentException("Unsupported strategy type: " + strategyType);
    }

    return getStrategyFactory(strategyType).createStrategy(barSeries, parameters);
  }

  StrategyFactory<?> getStrategyFactory(StrategyType strategyType);

  /**
   * Returns an immutable list of all supported strategy types.
   *
   * @return List of available strategy types
   */
  ImmutableList<StrategyType> getStrategyTypes();
}
