package com.verlumen.tradestream.strategies;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import com.verlumen.tradestream.strategies.StrategyType;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

interface StrategyFactory<T extends Message> {
  /**
   * Creates a Ta4j Strategy object from the provided parameters
   *
   * @param strategyParameters the parameters for the strategy
   * @param series bar series for the strategy
   * @return Strategy object
   * @throws InvalidProtocolBufferException If there is an error when unpacking the `Any` type
   */
  Strategy createStrategy(T strategyParameters, BarSeries series)
      throws InvalidProtocolBufferException;

  /**
   * Gets the `StrategyType` this factory handles.
   *
   * @return The StrategyType this factory handles.
   */
  StrategyType getStrategyType();

  /**
   * Returns the Class that this strategy unpacks the parameters into
   *
   * @return the Class that this factory unpacks `Any` into.
   */
  default Class<T> getParameterClass(){
    Type genericSuperclass = getClass().getGenericInterfaces()[0];
        ParameterizedType parameterizedType = (ParameterizedType) genericSuperclass;
        Type actualTypeArgument = parameterizedType.getActualTypeArguments()[0];
      return (Class<T>) actualTypeArgument;
  }
}
