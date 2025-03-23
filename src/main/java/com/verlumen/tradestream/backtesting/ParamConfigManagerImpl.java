package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;
import static java.util.function.Function.identity;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.mu.util.stream.BiStream;
import com.verlumen.tradestream.strategies.StrategyConstants;
import com.verlumen.tradestream.strategies.StrategyType;
import java.io.Serializable;

/**
 * Implementation of {@link ParamConfigManager} that manages parameter configurations for various strategies.
 * 
 * <p>This class uses an immutable map to associate each {@link StrategyType} with its corresponding 
 * {@link ParamConfig}. It is designed to be instantiated via dependency injection (using Guice), 
 * ensuring that the configuration list is properly provided at construction time.
 */
final class ParamConfigManagerImpl implements ParamConfigManager {
  private final ImmutableMap<StrategyType, ParamConfig> configMap;

  @Inject
  ParamConfigManagerImpl(ImmutableList<ParamConfig> configs) {
    // Create an immutable map from strategy type to its corresponding configuration.
    this.configMap = 
        BiStream.from(configs, ParamConfig::getStrategyType, identity())
            .filterKeys(StrategyConstants.supportedStrategyTypes::containsKey)
            .collect(ImmutableMap::toImmutableMap);
  }

  /**
   * Retrieves the parameter configuration for the given strategy type.
   *
   * @param strategyType the {@link StrategyType} for which to obtain the configuration
   * @return the {@link ParamConfig} associated with the specified strategy type
   * @throws IllegalArgumentException if no configuration exists for the provided strategy type
   */
  @Override
  public ParamConfig getParamConfig(StrategyType strategyType) {
    // Ensure the map contains a configuration for the requested strategy type.
    // Provide a descriptive error message if the configuration is missing.
    checkArgument(configMap.containsKey(strategyType),
        "No parameter configuration found for strategy type: " + strategyType);
    return configMap.get(strategyType);
  }
}
