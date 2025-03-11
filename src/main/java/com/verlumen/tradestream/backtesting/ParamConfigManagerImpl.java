package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;
import static java.util.function.Function.identity;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.mu.util.stream.BiStream;
import com.verlumen.tradestream.strategies.StrategyType;
import java.io.Serializable;

final class ParamConfigManagerImpl implements ParamConfigManager {
  private final ImmutableMap<StrategyType, ParamConfig> configMap;

  @Inject
  ParamConfigManagerImpl(ImmutableList<ParamConfig> configs) {
    this.configMap = 
        BiStream.from(configs, ParamConfig::getStrategyType, identity())
            .collect(ImmutableMap::toImmutableMap);
  }

  @Override
  public ParamConfig getParamConfig(StrategyType strategyType) {
    checkArgument(configMap.containsKey(strategyType));
    return configMap.get(strategyType);
  }
}
