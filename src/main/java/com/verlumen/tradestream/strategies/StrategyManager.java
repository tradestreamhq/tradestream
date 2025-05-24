package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import java.io.Serializable;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

/**
 * Manages the creation and configuration of trading strategies for the TradeStream system.
 *
 * <p>This interface provides methods to create Ta4j {@link Strategy} instances based on a specified
 * {@link StrategyType} and {@link BarSeries}. It leverages a corresponding {@link StrategyFactory}
 * to supply both the strategy instance and its default configuration parameters.
 */
public interface StrategyManager extends Serializable {

  /**
   * Creates a new Ta4j {@link Strategy} instance for the specified strategy type and bar series,
   * using the default parameters.
   *
   * @param strategyType the type of strategy to create
   * @param barSeries the bar series to associate with the strategy
   * @return a new instance of a Ta4j {@link Strategy} configured with the default parameters
   * @throws InvalidProtocolBufferException if there is an error unpacking the default parameters
   */
  default Strategy createStrategy(BarSeries barSeries, StrategyType strategyType)
      throws InvalidProtocolBufferException {
    return createStrategy(barSeries, strategyType, getDefaultParameters(strategyType));
  }

  /**
   * Creates a new Ta4j {@link Strategy} instance for the specified strategy type and bar series,
   * using the provided configuration parameters.
   *
   * @param barSeries the bar series to associate with the strategy
   * @param strategyType the type of strategy to create
   * @param parameters the configuration parameters for the strategy, wrapped in an {@link Any}
   *     message
   * @return a new instance of a Ta4j {@link Strategy} configured with the provided parameters
   * @throws InvalidProtocolBufferException if there is an error unpacking the parameters
   */
  default Strategy createStrategy(BarSeries barSeries, StrategyType strategyType, Any parameters)
      throws InvalidProtocolBufferException {
    return getStrategyFactory(strategyType).createStrategy(barSeries, parameters);
  }

  /**
   * Retrieves the default configuration parameters for the specified strategy type.
   *
   * <p>This method obtains the default parameters from the associated {@link StrategyFactory} and
   * packs them into a protocol buffers {@link Any} message.
   *
   * @param strategyType the type of strategy for which to retrieve the default parameters
   * @return an {@link Any} message containing the default parameters for the given strategy type
   */
  default Any getDefaultParameters(StrategyType strategyType) {
    return Any.pack(getStrategyFactory(strategyType).getDefaultParameters());
  }

  /**
   * Retrieves the {@link StrategyFactory} corresponding to the specified strategy type.
   *
   * <p>The returned factory is responsible for creating instances of the strategy as well as
   * providing its default configuration parameters.
   *
   * @param strategyType the type of strategy for which to obtain the factory
   * @return the {@link StrategyFactory} associated with the given strategy type
   */
  StrategyFactory<?> getStrategyFactory(StrategyType strategyType);

  /**
   * Returns an immutable list of all supported strategy types.
   *
   * <p>This list includes every available {@link StrategyType} that can be used to create and
   * configure trading strategies via this manager.
   *
   * @return an immutable list of supported {@link StrategyType} instances
   */
  ImmutableList<StrategyType> getStrategyTypes();
}
