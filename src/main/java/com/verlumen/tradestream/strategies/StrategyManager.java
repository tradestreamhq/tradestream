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
   * @param barSeries The bar series to associate with the created strategy
   * @param strategyType The type of strategy to create
   * @param strategyParameters The parameters for configuring the strategy 
   * @return The created Strategy object
   * @throws InvalidProtocolBufferException If there is an error unpacking the parameters
   */
  Strategy createStrategy(BarSeries barSeries, StrategyType strategyType, Any strategyParameters)
      throws InvalidProtocolBufferException;

  /**
   * Returns an immutable list of all supported strategy types.
   *
   * @return List of available strategy types
   */
  ImmutableList<StrategyType> getStrategyTypes();
}
