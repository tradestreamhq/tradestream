package com.verlumen.tradestream.strategies;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

interface StrategyFactory {
  /**
   * Creates a Ta4j Strategy object from the provided parameters
   *
   * @param strategyParameters the parameters for the strategy
   * @param series bar series for the strategy
   * @return Strategy object
   * @throws InvalidProtocolBufferException If there is an error when unpacking the `Any` type
   */
  Strategy createStrategy(Any strategyParameters, BarSeries series)
      throws InvalidProtocolBufferException;

  /**
   * Gets the `StrategyType` this factory handles.
   *
   * @return The StrategyType this factory handles.
   */
  StrategyType getStrategyType();
}
